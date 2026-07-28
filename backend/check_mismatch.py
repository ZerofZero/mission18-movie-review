"""시드 리뷰의 의도한 감성과 모델 예측을 비교하는 확인 스크립트.

도메인 전이 성능을 점검하고 보고서에 사용할 수치를 정리하기 위한 도구입니다.

사용법
    python check_mismatch.py
"""

import json
from pathlib import Path

from app.sentiment.analyzer import analyzer

LABELS = ("부정", "중립", "긍정")
REVIEWS_PATH = Path(__file__).resolve().parent / "data" / "seed_reviews.json"


def main() -> None:
    if not analyzer.load():
        print("모델을 적재하지 못했습니다.")
        return

    groups = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    flat = [(group["title"], item) for group in groups for item in group["reviews"]]
    predictions = analyzer.predict_batch([item["content"] for _, item in flat])

    # -----------------------------------------------------------------------
    # 불일치 목록
    # -----------------------------------------------------------------------
    mismatches = [
        (title, item, pred)
        for (title, item), pred in zip(flat, predictions)
        if item["expected"] != pred.label
    ]

    print("불일치 목록")
    print("-" * 100)
    for title, item, pred in mismatches:
        print(f"{title:6} 의도 {item['expected']} / 예측 {pred.label} ({pred.score:.2f})")
        print(f"       {item['content']}")
    print()

    # -----------------------------------------------------------------------
    # 혼동 행렬
    # -----------------------------------------------------------------------
    matrix = {expected: dict.fromkeys(LABELS, 0) for expected in LABELS}
    for (_, item), pred in zip(flat, predictions):
        matrix[item["expected"]][pred.label] += 1

    print("혼동 행렬 (행: 의도한 감성, 열: 모델 예측)")
    print("-" * 100)
    header = f"{'':8}" + "".join(f"{label:>8}" for label in LABELS) + f"{'합계':>8}"
    print(header)
    for expected in LABELS:
        row = matrix[expected]
        total = sum(row.values())
        line = f"{expected:8}" + "".join(f"{row[label]:>8}" for label in LABELS)
        print(line + f"{total:>8}")
    print()

    # -----------------------------------------------------------------------
    # 라벨별 정확도
    # -----------------------------------------------------------------------
    print("의도한 감성별 일치율")
    print("-" * 100)
    for expected in LABELS:
        row = matrix[expected]
        total = sum(row.values())
        if total == 0:
            continue
        correct = row[expected]
        print(f"{expected:8} {correct:3} / {total:3}  {correct / total * 100:5.1f}퍼센트")

    total_all = len(flat)
    correct_all = total_all - len(mismatches)
    print()
    print(f"전체 일치율 {correct_all} / {total_all}  {correct_all / total_all * 100:.1f}퍼센트")


if __name__ == "__main__":
    main()