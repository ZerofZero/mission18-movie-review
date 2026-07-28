"""감성 분석 모델 비교 스크립트.

현재 사용 중인 미션 16 모델과 공개된 다른 한국어 감성 분석 모델을
동일한 시드 리뷰 60건으로 비교합니다.

공개 모델은 출력 인덱스와 감성의 대응이 모델 카드에 명시되지 않은 경우가 많습니다.
이 스크립트는 가능한 모든 대응을 시도해 가장 높은 일치율을 채택합니다.
비교 대상 모델에 유리한 방식이므로, 그럼에도 성능이 낮다면 판단 근거가 분명해집니다.

사용법
    pip install torch
    python compare_models.py

주의
    모델을 내려받는 데 1GB 정도의 저장 공간이 필요합니다.
"""

import json
import sys
from collections import Counter
from itertools import permutations
from pathlib import Path

REVIEWS_PATH = Path(__file__).resolve().parent / "data" / "seed_reviews.json"

LABELS = ("부정", "중립", "긍정")

# 3-class 비교 대상입니다.
THREE_CLASS_CANDIDATES = [
    "alsgyu/sentiment-analysis-fine-tuned-model",
]

# 영화 리뷰 도메인 2-class 비교 대상입니다.
# 접근이 제한된 저장소가 있어 여러 후보를 순서대로 시도합니다.
TWO_CLASS_CANDIDATES = [
    "WhitePeak/bert-base-cased-Korean-sentiment",
    "sangrimlee/bert-base-multilingual-cased-nsmc",
    "Copycats/koelectra-base-v3-generalized-sentiment-analysis",
    "matthewburke/korean_sentiment",
]


# ---------------------------------------------------------------------------
# 준비
# ---------------------------------------------------------------------------

def require_torch():
    """PyTorch 가 설치되어 있는지 확인합니다."""
    try:
        import torch  # noqa: F401
    except ImportError:
        print("이 스크립트는 PyTorch 가 필요합니다. 아래 명령으로 설치해주세요.")
        print("    pip install torch")
        sys.exit(1)


def load_reviews() -> list[dict]:
    """시드 리뷰를 평탄화해 반환합니다."""
    groups = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    return [
        {"title": group["title"], **item}
        for group in groups
        for item in group["reviews"]
    ]


# ---------------------------------------------------------------------------
# 공개 모델 추론기
# ---------------------------------------------------------------------------

class HuggingFaceClassifier:
    """transformers 모델을 불러와 출력 인덱스를 반환합니다."""

    def __init__(self, model_name: str) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.name = model_name
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

        self.id2label = self.model.config.id2label
        self.num_labels = self.model.config.num_labels

    def predict_indices(self, texts: list[str], batch_size: int = 32) -> list[int]:
        """문장별 최대 확률 인덱스를 반환합니다."""
        indices: list[int] = []

        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            encoded = self.tokenizer(
                chunk,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            with self.torch.no_grad():
                logits = self.model(**encoded).logits
            indices.extend(logits.argmax(dim=-1).tolist())

        return indices


def load_first_available(candidates: list[str]) -> "HuggingFaceClassifier | None":
    """후보 중 접근 가능한 첫 번째 모델을 적재합니다."""
    for name in candidates:
        print(f"모델을 적재합니다: {name}")
        try:
            classifier = HuggingFaceClassifier(name)
        except Exception as exc:
            message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            print(f"  건너뜁니다: {message}")
            continue

        print(f"  적재 성공. 라벨 정보: {classifier.id2label}")
        return classifier

    print("  사용 가능한 모델을 찾지 못했습니다.")
    return None


# ---------------------------------------------------------------------------
# 라벨 대응 탐색
# ---------------------------------------------------------------------------

def find_best_mapping(
    indices: list[int], expected: list[str], labels: tuple[str, ...]
) -> tuple[dict[int, str], list[str], float]:
    """가능한 모든 인덱스 대응 중 일치율이 가장 높은 것을 찾습니다."""
    best_mapping: dict[int, str] = {}
    best_predictions: list[str] = []
    best_score = -1.0

    for perm in permutations(labels):
        mapping = {index: label for index, label in enumerate(perm)}
        predictions = [mapping.get(i, "알수없음") for i in indices]
        score = sum(1 for e, p in zip(expected, predictions) if e == p)

        if score > best_score:
            best_score = score
            best_mapping = mapping
            best_predictions = predictions

    accuracy = best_score / len(expected) * 100 if expected else 0.0
    return best_mapping, best_predictions, accuracy


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def print_confusion(name: str, expected: list[str], predicted: list[str]) -> None:
    """혼동 행렬과 라벨별 일치율을 출력합니다."""
    matrix = {label: Counter() for label in LABELS}
    for exp, pred in zip(expected, predicted):
        matrix[exp][pred] += 1

    print()
    print(f"[{name}] 혼동 행렬 (행: 의도한 감성, 열: 모델 예측)")
    print("-" * 60)
    print(f"{'':8}" + "".join(f"{label:>8}" for label in LABELS) + f"{'합계':>8}")
    for label in LABELS:
        row = matrix[label]
        total = sum(row.values())
        line = f"{label:8}" + "".join(f"{row[target]:>8}" for target in LABELS)
        print(line + f"{total:>8}")

    print()
    print(f"[{name}] 의도한 감성별 일치율")
    print("-" * 60)
    for label in LABELS:
        row = matrix[label]
        total = sum(row.values())
        if total:
            print(
                f"{label:8} {row[label]:3} / {total:3}  "
                f"{row[label] / total * 100:5.1f}퍼센트"
            )


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    require_torch()

    reviews = load_reviews()
    texts = [item["content"] for item in reviews]
    expected = [item["expected"] for item in reviews]

    # -----------------------------------------------------------------------
    # 1. 현재 사용 중인 모델
    # -----------------------------------------------------------------------
    from app.sentiment.analyzer import analyzer

    if not analyzer.load():
        print("미션 16 모델을 적재하지 못했습니다.")
        sys.exit(1)

    current = [r.label for r in analyzer.predict_batch(texts)]
    current_accuracy = (
        sum(1 for e, p in zip(expected, current) if e == p) / len(expected) * 100
    )

    # -----------------------------------------------------------------------
    # 2. 3-class 비교 모델
    # -----------------------------------------------------------------------
    print()
    three_class = load_first_available(THREE_CLASS_CANDIDATES)

    other = None
    other_accuracy = None

    if three_class is not None:
        indices = three_class.predict_indices(texts)
        mapping, other, other_accuracy = find_best_mapping(indices, expected, LABELS)
        print(f"  가장 유리한 인덱스 대응: {mapping}")

    # -----------------------------------------------------------------------
    # 3. 결과 비교
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("전체 비교")
    print("=" * 60)
    print(f"미션 16 KR-ELECTRA : {current_accuracy:5.1f}퍼센트")
    if other_accuracy is not None:
        print(f"{three_class.name[:30]:30} : {other_accuracy:5.1f}퍼센트")

    print_confusion("미션 16", expected, current)
    if other is not None:
        print_confusion("비교 모델", expected, other)

    # -----------------------------------------------------------------------
    # 4. 영화 도메인 2-class 모델
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("영화 리뷰 도메인 2-class 모델")
    print("=" * 60)

    binary_labels = ("부정", "긍정")

    # 중립을 제외한 문장만으로 평가합니다.
    binary_pairs = [
        (text, label)
        for text, label in zip(texts, expected)
        if label in binary_labels
    ]
    binary_texts = [text for text, _ in binary_pairs]
    binary_expected = [label for _, label in binary_pairs]

    two_class = load_first_available(TWO_CLASS_CANDIDATES)
    binary_predictions = None

    if two_class is not None:
        indices = two_class.predict_indices(binary_texts)
        mapping, binary_predictions, binary_accuracy = find_best_mapping(
            indices, binary_expected, binary_labels
        )
        print(f"  가장 유리한 인덱스 대응: {mapping}")
        print()
        print(
            f"중립을 제외한 {len(binary_texts)}건 기준 일치율 "
            f"{binary_accuracy:5.1f}퍼센트"
        )

        current_binary = [
            label
            for label, exp in zip(current, expected)
            if exp in binary_labels
        ]
        current_binary_accuracy = (
            sum(1 for e, p in zip(binary_expected, current_binary) if e == p)
            / len(binary_expected)
            * 100
        )
        print(f"같은 기준에서 미션 16 모델    {current_binary_accuracy:5.1f}퍼센트")

    # -----------------------------------------------------------------------
    # 5. 현재 모델이 틀린 문장
    # -----------------------------------------------------------------------
    problem_indices = [
        index
        for index, (exp, pred) in enumerate(zip(expected, current))
        if exp != pred
    ]

    print()
    print("=" * 60)
    print("현재 모델이 틀린 문장에 대한 판정 비교")
    print("=" * 60)
    print()

    binary_lookup = {}
    if binary_predictions is not None:
        binary_lookup = dict(zip(binary_texts, binary_predictions))

    for index in problem_indices:
        item = reviews[index]
        line = f"의도 {item['expected']} / 미션16 {current[index]}"
        if other is not None:
            line += f" / 비교모델 {other[index]}"
        if item["content"] in binary_lookup:
            line += f" / 영화도메인 {binary_lookup[item['content']]}"
        print(f"{item['title']:6} {line}")
        print(f"       {item['content']}")

    # -----------------------------------------------------------------------
    # 6. 요약
    # -----------------------------------------------------------------------
    print()
    print("=" * 60)
    print("요약")
    print("=" * 60)
    print(f"현재 모델이 틀린 문장 : {len(problem_indices)}건")

    if other is not None:
        corrected = sum(
            1 for index in problem_indices if other[index] == expected[index]
        )
        print(f"비교 모델이 바로잡은 문장 : {corrected}건")


if __name__ == "__main__":
    main()