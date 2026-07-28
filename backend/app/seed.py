"""시드 데이터 삽입 모듈.

data 폴더의 JSON 파일을 읽어 영화와 리뷰를 데이터베이스에 넣습니다.
리뷰는 삽입 시점에 감성 분석을 수행해 결과를 함께 저장합니다.

이 모듈은 애플리케이션 기동 시 자동으로 호출되며, 데이터가 이미 있으면
아무 작업도 하지 않습니다. 배포 환경에서 컨테이너가 다시 시작되어
데이터베이스가 초기화되더라도 동일한 화면을 보여주기 위한 구조입니다.
"""

import json
import logging
from datetime import date, timedelta
from itertools import zip_longest
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.config import BASE_DIR
from app.database import SessionLocal
from app.models import now_kst
from app.sentiment.analyzer import analyzer

logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "data"
MOVIES_PATH = DATA_DIR / "seed_movies.json"
REVIEWS_PATH = DATA_DIR / "seed_reviews.json"

# 리뷰 사이의 등록 시각 간격입니다. 60건이 약 30일에 걸쳐 분포하게 됩니다.
REVIEW_TIME_GAP = timedelta(hours=12)


# ---------------------------------------------------------------------------
# 파일 읽기
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> list | None:
    """JSON 파일을 읽습니다. 파일이 없으면 None 을 반환합니다."""
    if not path.exists():
        logger.warning("시드 파일을 찾을 수 없습니다: %s", path)
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("시드 파일을 읽을 수 없습니다: %s", path)
        return None


def _parse_date(value: str | None) -> date | None:
    """문자열을 날짜로 변환합니다."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 삽입
# ---------------------------------------------------------------------------

def _insert_movies(db: Session, records: list[dict]) -> dict[int, int]:
    """영화를 삽입하고 TMDB 번호와 내부 번호의 대응표를 반환합니다."""
    movies = [
        models.Movie(
            tmdb_id=record.get("tmdb_id"),
            title=record["title"],
            release_date=_parse_date(record.get("release_date")),
            director=record.get("director"),
            genre=record.get("genre"),
            poster_url=record.get("poster_url"),
            tmdb_vote_average=record.get("tmdb_vote_average"),
        )
        for record in records
    ]

    db.add_all(movies)
    db.commit()

    for movie in movies:
        db.refresh(movie)

    logger.info("영화 %d편을 삽입했습니다.", len(movies))
    return {movie.tmdb_id: movie.id for movie in movies if movie.tmdb_id is not None}


def _build_review_order(
    groups: list[dict], id_map: dict[int, int]
) -> list[tuple[int, dict]]:
    """리뷰를 영화별로 번갈아 배치합니다.

    같은 영화의 리뷰가 한꺼번에 몰리면 최근 리뷰 화면이 한 영화로만 채워지므로,
    영화를 순환하며 하나씩 배치해 여러 영화가 고르게 나타나도록 합니다.
    """
    per_movie: list[list[tuple[int, dict]]] = []

    for group in groups:
        movie_id = id_map.get(group.get("tmdb_id"))
        if movie_id is None:
            logger.warning(
                "리뷰 대상 영화를 찾을 수 없어 건너뜁니다: %s", group.get("title")
            )
            continue
        per_movie.append([(movie_id, item) for item in group.get("reviews", [])])

    if not per_movie:
        return []

    return [
        entry
        for row in zip_longest(*per_movie)
        for entry in row
        if entry is not None
    ]


def _insert_reviews(
    db: Session, groups: list[dict], id_map: dict[int, int]
) -> tuple[int, int, int]:
    """리뷰를 삽입합니다.

    반환값은 삽입한 리뷰 수, 감성 분석에 성공한 수, 의도한 감성과 일치한 수입니다.
    """
    flat = _build_review_order(groups, id_map)
    if not flat:
        return 0, 0, 0

    texts = [item["content"] for _, item in flat]

    results = None
    if analyzer.is_loaded:
        try:
            results = analyzer.predict_batch(texts)
        except Exception:
            logger.exception("시드 리뷰의 감성 분석에 실패했습니다.")
    else:
        logger.warning(
            "감성 분석 모델이 적재되지 않아 리뷰를 분석 결과 없이 저장합니다."
        )

    # 목록의 앞쪽이 가장 최근 리뷰가 되도록 시각을 거슬러 올라가며 부여합니다.
    base_time = now_kst()

    reviews = []
    matched = 0

    for index, (movie_id, item) in enumerate(flat):
        review = models.Review(
            movie_id=movie_id,
            author_name=item["author_name"],
            content=item["content"],
            created_at=base_time - REVIEW_TIME_GAP * index,
        )

        if results is not None:
            sentiment = results[index]
            review.sentiment_label = sentiment.label
            review.prob_negative = sentiment.prob_negative
            review.prob_neutral = sentiment.prob_neutral
            review.prob_positive = sentiment.prob_positive
            review.sentiment_score = sentiment.score

            if item.get("expected") == sentiment.label:
                matched += 1

        reviews.append(review)

    db.add_all(reviews)
    db.commit()

    analyzed = len(reviews) if results is not None else 0
    logger.info("리뷰 %d건을 삽입했습니다.", len(reviews))
    return len(reviews), analyzed, matched


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def seed_database(force: bool = False) -> None:
    """시드 데이터를 삽입합니다.

    데이터베이스에 영화가 이미 있으면 아무 작업도 하지 않습니다.
    force 를 True 로 지정하면 기존 데이터를 모두 지우고 다시 삽입합니다.
    """
    db = SessionLocal()

    try:
        existing = db.query(models.Movie).count()

        if existing > 0 and not force:
            logger.info("이미 데이터가 있어 시드 삽입을 건너뜁니다. 영화 %d편", existing)
            return

        if force and existing > 0:
            db.query(models.Review).delete()
            db.query(models.Movie).delete()
            db.commit()
            logger.info("기존 데이터를 삭제했습니다.")

        movie_records = _load_json(MOVIES_PATH)
        if not movie_records:
            logger.warning("삽입할 영화 자료가 없어 시드 작업을 중단합니다.")
            return

        id_map = _insert_movies(db, movie_records)

        review_groups = _load_json(REVIEWS_PATH)
        if not review_groups:
            logger.info("리뷰 자료가 없어 영화만 삽입했습니다.")
            return

        total, analyzed, matched = _insert_reviews(db, review_groups, id_map)

        if analyzed:
            accuracy = matched / analyzed * 100
            logger.info(
                "감성 분석 결과가 의도한 감성과 %d건 일치했습니다. 전체 %d건 중 %.1f퍼센트",
                matched,
                analyzed,
                accuracy,
            )

    except Exception:
        db.rollback()
        logger.exception("시드 삽입 중 오류가 발생했습니다.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.database import create_tables

    create_tables()
    analyzer.load()
    seed_database(force=True)