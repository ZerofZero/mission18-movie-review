"""감성 분석 모듈.

두 개의 모델을 결합해 리뷰의 감성을 판정합니다.

주 모델
    미션 16에서 변환한 KR-ELECTRA 기반 3-class 분류 모델입니다.
    쇼핑몰과 SNS 리뷰로 학습되었으며 중립 판정에 강점이 있습니다.

보조 모델
    NSMC 로 학습한 KoELECTRA-small 기반 2-class 분류 모델입니다.
    영화 리뷰 도메인이라 반어적 표현의 긍정과 부정 구분에 강점이 있습니다.

결합 규칙
    주 모델이 중립으로 판정한 문장은 그대로 둡니다.
    긍정이나 부정으로 판정한 문장은 중립 확률을 유지한 채
    나머지 확률을 보조 모델의 비율로 다시 배분합니다.
    확률의 합이 1로 유지되므로 점수 계산식은 그대로 사용합니다.

두 모델 모두 ONNX Runtime 으로 추론하며 PyTorch 에 의존하지 않습니다.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from app.config import settings
from app.schemas import SentimentResult

logger = logging.getLogger(__name__)

# 모델 출력 인덱스와 감성 라벨의 대응입니다.
# 미션 16 의 mission_16_kr_electra_config.json 에 기록된 순서를 따릅니다.
LABEL_NAMES: tuple[str, str, str] = ("부정", "중립", "긍정")

# 감성 점수를 계산할 때 각 라벨에 부여하는 가중치입니다.
LABEL_WEIGHTS = np.array([1.0, 3.0, 5.0], dtype=np.float32)

NEUTRAL_INDEX = 1


# ---------------------------------------------------------------------------
# 한국어 판별
# ---------------------------------------------------------------------------

def korean_ratio(text: str) -> float:
    """문자열에서 한글이 차지하는 비율을 계산합니다.

    공백과 문장 부호는 분모에서 제외하여, 문장 부호가 많은 짧은 문장이
    불리하게 판정되지 않도록 합니다.
    """
    meaningful = [ch for ch in text if ch.isalnum()]
    if not meaningful:
        return 0.0

    hangul = sum(1 for ch in meaningful if "\uac00" <= ch <= "\ud7a3")
    return hangul / len(meaningful)


def is_korean(text: str, threshold: float | None = None) -> bool:
    """문자열이 한국어로 작성되었는지 판정합니다."""
    limit = settings.KOREAN_RATIO_THRESHOLD if threshold is None else threshold
    return korean_ratio(text) >= limit


# ---------------------------------------------------------------------------
# 내부 도우미
# ---------------------------------------------------------------------------

def _softmax(logits: np.ndarray) -> np.ndarray:
    """행 단위로 소프트맥스를 적용합니다."""
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=-1, keepdims=True)


class _OnnxModel:
    """ONNX 세션과 토크나이저를 한 쌍으로 관리합니다."""

    def __init__(self, session, tokenizer, input_names: list[str]) -> None:
        self.session = session
        self.tokenizer = tokenizer
        self.input_names = input_names

    def probabilities(self, texts: list[str], max_length: int) -> np.ndarray:
        """문장별 확률 분포를 반환합니다."""
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )

        # 모델이 요구하는 입력만 전달합니다.
        # ELECTRA 토크나이저는 token_type_ids 를 생성하지만
        # 변환된 그래프는 이를 입력으로 받지 않습니다.
        feeds = {
            name: encoded[name].astype(np.int64)
            for name in self.input_names
            if name in encoded
        }

        outputs = self.session.run(None, feeds)
        return _softmax(np.asarray(outputs[0], dtype=np.float32))


def _load_onnx_model(model_dir, model_path) -> _OnnxModel:
    """지정한 경로의 ONNX 모델과 토크나이저를 적재합니다."""
    import onnxruntime as ort
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = (
        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    )
    session = ort.InferenceSession(
        str(model_path),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )

    input_names = [item.name for item in session.get_inputs()]
    return _OnnxModel(session, tokenizer, input_names)


# ---------------------------------------------------------------------------
# 추론기
# ---------------------------------------------------------------------------

class SentimentAnalyzer:
    """두 모델을 결합해 감성 판정을 수행합니다."""

    def __init__(self) -> None:
        self._main: _OnnxModel | None = None
        self._binary: _OnnxModel | None = None
        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # 상태
    # -----------------------------------------------------------------------
    @property
    def is_loaded(self) -> bool:
        """주 모델이 적재되었는지 여부."""
        return self._main is not None

    @property
    def binary_loaded(self) -> bool:
        """보조 모델이 적재되었는지 여부."""
        return self._binary is not None

    # -----------------------------------------------------------------------
    # 적재
    # -----------------------------------------------------------------------
    def load(self) -> bool:
        """모델을 적재합니다.

        주 모델 적재에 실패하면 False 를 반환합니다.
        보조 모델은 없어도 동작하며, 이 경우 3-class 모델 단독으로 판정합니다.
        """
        if not self.is_loaded:
            self._main = self._load_main()

        if self._main is not None and not self.binary_loaded:
            self._binary = self._load_binary()

        return self.is_loaded

    def _load_main(self) -> _OnnxModel | None:
        """주 모델을 적재합니다."""
        model_path = settings.model_file_path

        if not model_path.exists():
            logger.warning("주 모델 파일을 찾을 수 없습니다: %s", model_path)
            return None

        try:
            logger.info("주 모델을 적재합니다: %s", model_path.name)
            model = _load_onnx_model(settings.model_dir_path, model_path)
            logger.info("주 모델 적재 완료. 입력: %s", model.input_names)
            return model
        except Exception:
            logger.exception("주 모델 적재에 실패했습니다.")
            return None

    def _load_binary(self) -> _OnnxModel | None:
        """보조 모델을 적재합니다."""
        model_path = settings.binary_model_file_path

        if model_path is None:
            logger.info("보조 모델이 설정되어 있지 않아 3-class 모델만 사용합니다.")
            return None

        if not model_path.exists():
            logger.warning("보조 모델 파일을 찾을 수 없습니다: %s", model_path)
            return None

        try:
            logger.info("보조 모델을 적재합니다: %s", model_path.name)
            model = _load_onnx_model(settings.binary_model_dir_path, model_path)
            logger.info("보조 모델 적재 완료. 입력: %s", model.input_names)
            return model
        except Exception:
            logger.exception("보조 모델 적재에 실패했습니다.")
            return None

    # -----------------------------------------------------------------------
    # 결합
    # -----------------------------------------------------------------------
    def _combine(self, main_probs: np.ndarray, binary_probs: np.ndarray) -> np.ndarray:
        """두 모델의 확률을 결합합니다.

        주 모델이 중립으로 판정한 문장은 그대로 두고,
        나머지 문장만 보조 모델의 비율로 다시 배분합니다.
        """
        negative_index = settings.BINARY_NEGATIVE_INDEX
        positive_index = 1 - negative_index

        combined = main_probs.copy()
        predicted = main_probs.argmax(axis=1)

        for row in range(len(combined)):
            if predicted[row] == NEUTRAL_INDEX:
                continue

            neutral = float(main_probs[row, NEUTRAL_INDEX])
            remainder = 1.0 - neutral

            combined[row, 0] = remainder * binary_probs[row, negative_index]
            combined[row, 1] = neutral
            combined[row, 2] = remainder * binary_probs[row, positive_index]

        return combined

    # -----------------------------------------------------------------------
    # 추론
    # -----------------------------------------------------------------------
    def predict(self, text: str) -> SentimentResult:
        """문장 하나를 분석합니다."""
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list[str]) -> list[SentimentResult]:
        """여러 문장을 한 번에 분석합니다.

        시드 데이터 삽입처럼 다량의 문장을 처리할 때 사용합니다.
        """
        if not self.is_loaded:
            raise RuntimeError("감성 분석 모델이 적재되지 않았습니다.")
        if not texts:
            return []

        max_length = settings.MODEL_MAX_LENGTH

        # ONNX Runtime 세션은 스레드 안전하지만, 사용량이 많지 않으므로
        # 순차 실행을 보장해 메모리 사용을 예측 가능하게 유지합니다.
        with self._lock:
            probabilities = self._main.probabilities(texts, max_length)

            if self._binary is not None:
                binary_probabilities = self._binary.probabilities(texts, max_length)
                probabilities = self._combine(probabilities, binary_probabilities)

        results: list[SentimentResult] = []
        for row in probabilities:
            index = int(np.argmax(row))
            score = float(np.dot(row, LABEL_WEIGHTS))
            results.append(
                SentimentResult(
                    label=LABEL_NAMES[index],
                    prob_negative=round(float(row[0]), 4),
                    prob_neutral=round(float(row[1]), 4),
                    prob_positive=round(float(row[2]), 4),
                    score=round(score, 4),
                )
            )
        return results


# 애플리케이션 전역에서 사용하는 단일 인스턴스입니다.
analyzer = SentimentAnalyzer()