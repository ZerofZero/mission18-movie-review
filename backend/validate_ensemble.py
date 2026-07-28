"""3-class 모델과 2-class 모델의 결합 규칙 검증 스크립트.

미션 16 모델은 중립 판정에 강하고, NSMC 로 학습한 2-class 모델은
영화 리뷰의 반어적 표현에 강합니다. 두 모델을 결합해 각자의 강점을
살릴 수 있는지 시드 리뷰 60건으로 검증합니다.

검증하는 규칙
    기준선  현재 모델 단독
    규칙 A  중립 확률은 3-class 를 따르고, 나머지 확률을 2-class 로 배분
    규칙 B  3-class 가 중립이면 중립, 아니면 2-class 판정을 채택

사용법
    python validate_ensemble.py
"""

import json
import sys
from collections import Counter
from itertools import permutations
from pathlib import Path

import numpy as np

REVIEWS_PATH = Path(__file__).resolve().parent / "data" / "seed_reviews.json"

LABELS = ("부정", "중립", "긍정")
BINARY_LABELS = ("부정", "긍정")
LABEL_WEIGHTS = np.array([1.0, 3.0, 5.0], dtype=np.float32)

BINARY_CANDIDATES = [
    "daekeun-ml/koelectra-small-v3-nsmc",
    "sangrimlee/bert-base-multilingual-cased-nsmc",
    "matthewburke/korean_sentiment",
]


# ---------------------------------------------------------------------------
# 준비
# ---------------------------------------------------------------------------

def require_torch():
    try:
        import torch  # noqa: F401
    except ImportError:
        print("이 스크립트는 PyTorch 가 필요합니다. pip install torch 로 설치해주세요.")
        sys.exit(1)


def load_reviews() -> list[dict]:
    groups = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    return [
        {"title": group["title"], **item}
        for group in groups
        for item in group["reviews"]
    ]


# ---------------------------------------------------------------------------
# 2-class 모델
# ---------------------------------------------------------------------------

class BinaryModel:
    """2-class 모델의 확률과 라벨 대응을 관리합니다."""

    def __init__(self, model_name: str) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.name = model_name
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

        if self.model.config.num_labels != 2:
            raise ValueError("2-class 모델이 아닙니다.")

        # 부정과 긍정이 각각 어느 인덱스인지는 뒤에서 결정합니다.
        self.negative_index = 0
        self.positive_index = 1

    def probabilities(self, texts: list[str]) -> np.ndarray:
        """문장별 확률 분포를 반환합니다."""
        rows = []
        for start in range(0, len(texts), 32):
            chunk = texts[start : start + 32]
            encoded = self.tokenizer(
                chunk,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt",
            )
            with self.torch.no_grad():
                logits = self.model(**encoded).logits
            rows.append(self.torch.softmax(logits, dim=-1).numpy())
        return np.concatenate(rows, axis=0)

    def calibrate(self, texts: list[str], expected: list[str]) -> float:
        """긍정과 부정의 인덱스를 결정하고 그때의 일치율을 반환합니다."""
        probabilities = self.probabilities(texts)
        indices = probabilities.argmax(axis=1)

        best_score = -1
        for perm in permutations(BINARY_LABELS):
            mapping = {i: label for i, label in enumerate(perm)}
            predictions = [mapping[int(i)] for i in indices]
            score = sum(1 for e, p in zip(expected, predictions) if e == p)
            if score > best_score:
                best_score = score
                self.negative_index = perm.index("부정")
                self.positive_index = perm.index("긍정")

        return best_score / len(expected) * 100

    def negative_positive(self, texts: list[str]) -> np.ndarray:
        """부정과 긍정 확률을 순서대로 담은 배열을 반환합니다."""
        probabilities = self.probabilities(texts)
        return np.stack(
            [
                probabilities[:, self.negative_index],
                probabilities[:, self.positive_index],
            ],
            axis=1,
        )


# ---------------------------------------------------------------------------
# 결합 규칙
# ---------------------------------------------------------------------------

def rule_a(three: np.ndarray, two: np.ndarray) -> np.ndarray:
    """중립 확률은 유지하고 나머지를 2-class 비율로 배분합니다."""
    neutral = three[:, 1]
    remainder = 1.0 - neutral
    negative = remainder * two[:, 0]
    positive = remainder * two[:, 1]
    return np.stack([negative, neutral, positive], axis=1)


def rule_b(three: np.ndarray, two: np.ndarray) -> np.ndarray:
    """3-class 가 중립이면 유지하고, 아니면 2-class 판정을 따릅니다."""
    combined = three.copy()

    for index in range(len(three)):
        if int(three[index].argmax()) == 1:
            continue
        neutral = three[index, 1]
        remainder = 1.0 - neutral
        combined[index] = [
            remainder * two[index, 0],
            neutral,
            remainder * two[index, 1],
        ]

    return combined


def to_labels(probabilities: np.ndarray) -> list[str]:
    """확률 분포를 감성 판정으로 변환합니다."""
    return [LABELS[int(row.argmax())] for row in probabilities]


def to_scores(probabilities: np.ndarray) -> np.ndarray:
    """확률 분포를 1점에서 5점 사이의 점수로 변환합니다."""
    return probabilities @ LABEL_WEIGHTS


# ---------------------------------------------------------------------------
# 평가
# ---------------------------------------------------------------------------

def accuracy(expected: list[str], predicted: list[str]) -> float:
    matched = sum(1 for e, p in zip(expected, predicted) if e == p)
    return matched / len(expected) * 100


def print_confusion(name: str, expected: list[str], predicted: list[str]) -> None:
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


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    require_torch()

    reviews = load_reviews()
    texts = [item["content"] for item in reviews]
    expected = [item["expected"] for item in reviews]

    binary_pairs = [
        (text, label)
        for text, label in zip(texts, expected)
        if label in BINARY_LABELS
    ]
    binary_texts = [text for text, _ in binary_pairs]
    binary_expected = [label for _, label in binary_pairs]

    # -----------------------------------------------------------------------
    # 기준선
    # -----------------------------------------------------------------------
    from app.sentiment.analyzer import analyzer

    if not analyzer.load():
        print("미션 16 모델을 적재하지 못했습니다.")
        sys.exit(1)

    base_results = analyzer.predict_batch(texts)
    three = np.array(
        [
            [r.prob_negative, r.prob_neutral, r.prob_positive]
            for r in base_results
        ],
        dtype=np.float32,
    )
    base_labels = [r.label for r in base_results]
    base_accuracy = accuracy(expected, base_labels)

    print(f"평가 대상 {len(texts)}건")
    print(f"기준선 미션 16 모델 단독 : {base_accuracy:.1f}퍼센트")
    print()

    # -----------------------------------------------------------------------
    # 각 2-class 모델과 결합
    # -----------------------------------------------------------------------
    summary = []
    best = None

    for name in BINARY_CANDIDATES:
        print("=" * 70)
        print(name)
        print("=" * 70)

        try:
            model = BinaryModel(name)
            binary_accuracy = model.calibrate(binary_texts, binary_expected)
            two = model.negative_positive(texts)
        except Exception as exc:
            message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            print(f"  건너뜁니다: {message}")
            print()
            continue

        print(f"  중립 제외 {len(binary_texts)}건 단독 일치율 : {binary_accuracy:.1f}퍼센트")

        for rule_name, rule in (("규칙 A", rule_a), ("규칙 B", rule_b)):
            combined = rule(three, two)
            labels = to_labels(combined)
            score = accuracy(expected, labels)
            print(f"  {rule_name} 결합 일치율 : {score:.1f}퍼센트")

            summary.append((name, rule_name, score))
            if best is None or score > best[0]:
                best = (score, name, rule_name, labels, combined)

        print()

    if best is None:
        print("사용 가능한 모델이 없었습니다.")
        return

    # -----------------------------------------------------------------------
    # 최적 조합 상세
    # -----------------------------------------------------------------------
    best_score, best_name, best_rule, best_labels, best_probs = best

    print("=" * 70)
    print("요약")
    print("=" * 70)
    print(f"{'기준선 (미션 16 단독)':45} {base_accuracy:6.1f}퍼센트")
    for name, rule_name, score in sorted(summary, key=lambda r: r[2], reverse=True):
        print(f"{name[:38]:38} {rule_name:6} {score:6.1f}퍼센트")

    print()
    print(f"최적 조합 : {best_name} + {best_rule} ({best_score:.1f}퍼센트)")

    print_confusion("기준선", expected, base_labels)
    print_confusion("최적 조합", expected, best_labels)

    # -----------------------------------------------------------------------
    # 개선된 문장과 나빠진 문장
    # -----------------------------------------------------------------------
    improved, worsened = [], []

    for index, item in enumerate(reviews):
        before = base_labels[index] == expected[index]
        after = best_labels[index] == expected[index]
        if not before and after:
            improved.append(index)
        elif before and not after:
            worsened.append(index)

    scores = to_scores(best_probs)

    print()
    print("=" * 70)
    print(f"개선된 문장 {len(improved)}건")
    print("=" * 70)
    for index in improved:
        item = reviews[index]
        print(
            f"{item['title']:6} 의도 {item['expected']} / "
            f"기준선 {base_labels[index]} / 결합 {best_labels[index]} "
            f"({scores[index]:.2f})"
        )
        print(f"       {item['content']}")

    print()
    print("=" * 70)
    print(f"나빠진 문장 {len(worsened)}건")
    print("=" * 70)
    for index in worsened:
        item = reviews[index]
        print(
            f"{item['title']:6} 의도 {item['expected']} / "
            f"기준선 {base_labels[index]} / 결합 {best_labels[index]} "
            f"({scores[index]:.2f})"
        )
        print(f"       {item['content']}")

    if not worsened:
        print("없습니다.")


if __name__ == "__main__":
    main()