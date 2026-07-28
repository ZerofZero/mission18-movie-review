"""2-class 한국어 감성 모델 후보 일괄 검증 스크립트.

공개된 2-class 모델 여러 개를 동일한 기준으로 평가합니다.
중립 리뷰를 제외한 시드 리뷰로 일치율을 측정하고,
현재 모델이 반어적 표현에서 실패한 문장들의 판정을 함께 확인합니다.

라벨 순서가 공개되지 않은 모델이 많으므로 가능한 대응을 모두 시도하고
가장 높은 일치율을 채택합니다. 비교 대상에게 유리한 방식입니다.

사용법
    python test_binary_models.py
"""

import json
import sys
from itertools import permutations
from pathlib import Path

REVIEWS_PATH = Path(__file__).resolve().parent / "data" / "seed_reviews.json"

BINARY_LABELS = ("부정", "긍정")

CANDIDATES = [
    "WhitePeak/bert-base-cased-Korean-sentiment",
    "sangrimlee/bert-base-multilingual-cased-nsmc",
    "Copycats/koelectra-base-v3-generalized-sentiment-analysis",
    "matthewburke/korean_sentiment",
    "daekeun-ml/koelectra-small-v3-nsmc",
    "monologg/koelectra-base-finetuned-nsmc",
]

# 현재 모델이 반어적 표현 때문에 틀린 문장들입니다.
# 이 문장들을 맞히는지가 결합 여부를 판단하는 핵심 기준입니다.
KEY_SENTENCES = [
    ("마지막 재회 장면에서는 눈물을 참기가 어려웠습니다.", "긍정"),
    ("음향과 촬영이 만들어내는 불안한 분위기가 대단했습니다.", "긍정"),
    ("불친절하지만 그만큼 곱씹을 거리가 많은 작품입니다.", "긍정"),
    ("결말의 여운이 오래 남아서 한동안 다른 영화가 눈에 들어오지 않았습니다.", "긍정"),
]


# ---------------------------------------------------------------------------
# 준비
# ---------------------------------------------------------------------------

def require_torch():
    """PyTorch 가 설치되어 있는지 확인합니다."""
    try:
        import torch  # noqa: F401
    except ImportError:
        print("이 스크립트는 PyTorch 가 필요합니다. pip install torch 로 설치해주세요.")
        sys.exit(1)


def load_binary_reviews() -> tuple[list[str], list[str]]:
    """중립을 제외한 시드 리뷰를 반환합니다."""
    groups = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    texts, labels = [], []

    for group in groups:
        for item in group["reviews"]:
            if item["expected"] in BINARY_LABELS:
                texts.append(item["content"])
                labels.append(item["expected"])

    return texts, labels


# ---------------------------------------------------------------------------
# 추론
# ---------------------------------------------------------------------------

def predict_indices(model_name: str, texts: list[str]) -> tuple[list[int], dict]:
    """모델을 적재해 문장별 최대 확률 인덱스를 반환합니다."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()

    if model.config.num_labels != 2:
        raise ValueError(
            f"2-class 모델이 아닙니다. 출력 개수 {model.config.num_labels}"
        )

    indices: list[int] = []
    for start in range(0, len(texts), 32):
        chunk = texts[start : start + 32]
        encoded = tokenizer(
            chunk, padding=True, truncation=True, max_length=128, return_tensors="pt"
        )
        with torch.no_grad():
            logits = model(**encoded).logits
        indices.extend(logits.argmax(dim=-1).tolist())

    return indices, model.config.id2label


def best_mapping(
    indices: list[int], expected: list[str]
) -> tuple[dict[int, str], list[str], float]:
    """가능한 대응 중 일치율이 가장 높은 것을 찾습니다."""
    best = (None, None, -1)

    for perm in permutations(BINARY_LABELS):
        mapping = {index: label for index, label in enumerate(perm)}
        predictions = [mapping[i] for i in indices]
        matched = sum(1 for e, p in zip(expected, predictions) if e == p)
        if matched > best[2]:
            best = (mapping, predictions, matched)

    mapping, predictions, matched = best
    return mapping, predictions, matched / len(expected) * 100


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    require_torch()

    texts, expected = load_binary_reviews()
    key_texts = [text for text, _ in KEY_SENTENCES]
    key_expected = [label for _, label in KEY_SENTENCES]

    # 현재 모델의 기준 성능을 먼저 구합니다.
    from app.sentiment.analyzer import analyzer

    if not analyzer.load():
        print("미션 16 모델을 적재하지 못했습니다.")
        sys.exit(1)

    current = [r.label for r in analyzer.predict_batch(texts)]
    current_accuracy = (
        sum(1 for e, p in zip(expected, current) if e == p) / len(expected) * 100
    )
    current_key = [r.label for r in analyzer.predict_batch(key_texts)]

    print(f"중립을 제외한 평가 대상 {len(texts)}건")
    print(f"미션 16 모델 기준 일치율 {current_accuracy:.1f}퍼센트")
    print()

    results = []

    for name in CANDIDATES:
        print("=" * 70)
        print(name)
        print("=" * 70)

        try:
            indices, id2label = predict_indices(name, texts)
        except Exception as exc:
            message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            print(f"  건너뜁니다: {message}")
            print()
            continue

        mapping, predictions, accuracy = best_mapping(indices, expected)

        print(f"  라벨 정보      : {id2label}")
        print(f"  채택한 대응    : {mapping}")
        print(f"  일치율         : {accuracy:.1f}퍼센트")

        key_indices, _ = predict_indices(name, key_texts)
        key_predictions = [mapping[i] for i in key_indices]
        key_matched = sum(
            1 for e, p in zip(key_expected, key_predictions) if e == p
        )

        print(f"  반어 문장 정답 : {key_matched} / {len(KEY_SENTENCES)}")
        for (sentence, label), prediction in zip(KEY_SENTENCES, key_predictions):
            mark = "정답" if label == prediction else "오답"
            print(f"    [{mark}] {prediction}  {sentence}")

        results.append((name, accuracy, key_matched))
        print()

    # -----------------------------------------------------------------------
    # 요약
    # -----------------------------------------------------------------------
    print("=" * 70)
    print("요약")
    print("=" * 70)

    key_matched_current = sum(
        1 for e, p in zip(key_expected, current_key) if e == p
    )
    print(
        f"{'미션 16 KR-ELECTRA':50} {current_accuracy:6.1f}퍼센트  "
        f"반어 {key_matched_current}/{len(KEY_SENTENCES)}"
    )

    for name, accuracy, key_matched in sorted(
        results, key=lambda row: row[1], reverse=True
    ):
        print(
            f"{name[:50]:50} {accuracy:6.1f}퍼센트  "
            f"반어 {key_matched}/{len(KEY_SENTENCES)}"
        )

    if not results:
        print("사용 가능한 모델이 없었습니다.")


if __name__ == "__main__":
    main()