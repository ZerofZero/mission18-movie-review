"""데이터베이스 조작 함수.

라우터가 직접 SQLAlchemy 를 다루지 않도록 조회와 저장 로직을 분리했습니다.
데이터베이스 종류를 교체하더라도 이 모듈만 수정하면 됩니다.
"""

from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app import models, schemas

SortOption = Literal["latest", "rating", "title"]


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------

class DuplicateMovieError(Exception):
    """이미 등록된 영화를 다시 등록하려 할 때 발생합니다."""


class MovieNotFoundError(Exception):
    """대상 영화를 찾을 수 없을 때 발생합니다."""


# ---------------------------------------------------------------------------
# 내부 도우미
# ---------------------------------------------------------------------------

def _movie_with_stats_query() -> Select:
    """영화와 함께 리뷰 개수, 감성 평점 평균을 조회하는 질의를 만듭니다."""
    return (
        select(
            models.Movie,
            func.count(models.Review.id).label("review_count"),
            func.avg(models.Review.sentiment_score).label("sentiment_rating"),
        )
        .outerjoin(models.Review, models.Review.movie_id == models.Movie.id)
        .group_by(models.Movie.id)
    )


def _attach_stats(movie: models.Movie, review_count: int, rating: float | None):
    """조회한 통계 값을 영화 객체에 부여합니다."""
    movie.review_count = review_count or 0
    movie.sentiment_rating = round(rating, 2) if rating is not None else None
    return movie


def _attach_movie_title(review: models.Review) -> models.Review:
    """리뷰 객체에 영화 제목을 부여합니다."""
    review.movie_title = review.movie.title if review.movie else None
    return review


# ---------------------------------------------------------------------------
# 영화
# ---------------------------------------------------------------------------

def _apply_movie_filters(stmt: Select, q: str | None, genre: str | None) -> Select:
    """제목과 장르 조건을 질의에 적용합니다."""
    if q:
        stmt = stmt.where(models.Movie.title.ilike(f"%{q}%"))
    if genre:
        stmt = stmt.where(models.Movie.genre.ilike(f"%{genre}%"))
    return stmt


def count_filtered_movies(
    db: Session, q: str | None = None, genre: str | None = None
) -> int:
    """조건에 맞는 영화의 전체 개수를 반환합니다."""
    stmt = _apply_movie_filters(select(func.count(models.Movie.id)), q, genre)
    return db.execute(stmt).scalar_one()


def list_movies(
    db: Session,
    q: str | None = None,
    genre: str | None = None,
    sort: SortOption = "latest",
    limit: int | None = None,
    offset: int = 0,
) -> list[models.Movie]:
    """조건에 맞는 영화 목록을 조회합니다."""
    stmt = _apply_movie_filters(_movie_with_stats_query(), q, genre)

    if sort == "title":
        stmt = stmt.order_by(models.Movie.title.asc())
    elif sort == "rating":
        # 평점이 없는 영화가 뒤로 가도록 없는 값을 -1 로 대체합니다.
        stmt = stmt.order_by(
            func.coalesce(func.avg(models.Review.sentiment_score), -1).desc(),
            models.Movie.created_at.desc(),
        )
    else:
        stmt = stmt.order_by(models.Movie.created_at.desc(), models.Movie.id.desc())

    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)

    rows = db.execute(stmt).all()
    return [_attach_stats(row[0], row[1], row[2]) for row in rows]


def get_movie(db: Session, movie_id: int) -> models.Movie | None:
    """번호로 영화 한 편을 조회합니다."""
    stmt = _movie_with_stats_query().where(models.Movie.id == movie_id)
    row = db.execute(stmt).first()
    if row is None or row[0] is None:
        return None
    return _attach_stats(row[0], row[1], row[2])


def list_genres(db: Session) -> list[str]:
    """등록된 영화들의 장르 목록을 중복 없이 조회합니다."""
    rows = db.execute(
        select(models.Movie.genre).where(models.Movie.genre.is_not(None)).distinct()
    ).all()

    genres: set[str] = set()
    for (value,) in rows:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                genres.add(cleaned)
    return sorted(genres)


def find_duplicate_movie(
    db: Session, movie_in: schemas.MovieCreate
) -> models.Movie | None:
    """중복 등록에 해당하는 기존 영화를 찾습니다."""
    if movie_in.tmdb_id is not None:
        existing = db.execute(
            select(models.Movie).where(models.Movie.tmdb_id == movie_in.tmdb_id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    return db.execute(
        select(models.Movie).where(
            models.Movie.title == movie_in.title,
            models.Movie.release_date == movie_in.release_date,
        )
    ).scalar_one_or_none()


def create_movie(db: Session, movie_in: schemas.MovieCreate) -> models.Movie:
    """영화를 등록합니다.

    같은 영화가 이미 있으면 DuplicateMovieError 를 발생시킵니다.
    """
    if find_duplicate_movie(db, movie_in) is not None:
        raise DuplicateMovieError(f"이미 등록된 영화입니다: {movie_in.title}")

    movie = models.Movie(**movie_in.model_dump())
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return _attach_stats(movie, 0, None)


def delete_movie(db: Session, movie_id: int) -> bool:
    """영화를 삭제합니다. 연결된 리뷰도 함께 삭제됩니다."""
    movie = db.get(models.Movie, movie_id)
    if movie is None:
        return False

    db.delete(movie)
    db.commit()
    return True


def count_movies(db: Session) -> int:
    """등록된 영화 개수를 반환합니다."""
    return db.execute(select(func.count(models.Movie.id))).scalar_one()


# ---------------------------------------------------------------------------
# 리뷰
# ---------------------------------------------------------------------------

def list_recent_reviews(db: Session, limit: int = 10) -> list[models.Review]:
    """전체 리뷰를 최신순으로 조회합니다."""
    stmt = (
        select(models.Review)
        .options(joinedload(models.Review.movie))
        .order_by(models.Review.created_at.desc(), models.Review.id.desc())
        .limit(limit)
    )
    reviews = db.execute(stmt).scalars().all()
    return [_attach_movie_title(review) for review in reviews]


def list_movie_reviews(
    db: Session, movie_id: int, limit: int | None = None
) -> list[models.Review]:
    """특정 영화의 리뷰를 최신순으로 조회합니다."""
    stmt = (
        select(models.Review)
        .options(joinedload(models.Review.movie))
        .where(models.Review.movie_id == movie_id)
        .order_by(models.Review.created_at.desc(), models.Review.id.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    reviews = db.execute(stmt).scalars().all()
    return [_attach_movie_title(review) for review in reviews]


def get_review(db: Session, review_id: int) -> models.Review | None:
    """번호로 리뷰 한 건을 조회합니다."""
    review = db.get(models.Review, review_id)
    if review is None:
        return None
    return _attach_movie_title(review)


def create_review(
    db: Session,
    review_in: schemas.ReviewCreate,
    sentiment: schemas.SentimentResult | None = None,
) -> models.Review:
    """리뷰를 등록합니다.

    감성 분석 결과가 주어지면 함께 저장합니다.
    대상 영화가 없으면 MovieNotFoundError 를 발생시킵니다.
    """
    movie = db.get(models.Movie, review_in.movie_id)
    if movie is None:
        raise MovieNotFoundError(f"영화를 찾을 수 없습니다: {review_in.movie_id}")

    review = models.Review(
        movie_id=review_in.movie_id,
        author_name=review_in.author_name,
        content=review_in.content,
    )

    if sentiment is not None:
        review.sentiment_label = sentiment.label
        review.prob_negative = sentiment.prob_negative
        review.prob_neutral = sentiment.prob_neutral
        review.prob_positive = sentiment.prob_positive
        review.sentiment_score = sentiment.score

    db.add(review)
    db.commit()
    db.refresh(review)

    review.movie_title = movie.title
    return review


def delete_review(db: Session, review_id: int) -> bool:
    """리뷰를 삭제합니다."""
    review = db.get(models.Review, review_id)
    if review is None:
        return False

    db.delete(review)
    db.commit()
    return True


def count_reviews(db: Session) -> int:
    """등록된 리뷰 개수를 반환합니다."""
    return db.execute(select(func.count(models.Review.id))).scalar_one()


# ---------------------------------------------------------------------------
# 평점
# ---------------------------------------------------------------------------

def get_movie_rating(db: Session, movie_id: int) -> schemas.MovieRating | None:
    """영화의 감성 분석 평점과 감성 분포를 계산합니다."""
    movie = db.get(models.Movie, movie_id)
    if movie is None:
        return None

    stats = db.execute(
        select(
            func.count(models.Review.id),
            func.avg(models.Review.sentiment_score),
        ).where(models.Review.movie_id == movie_id)
    ).one()

    review_count = stats[0] or 0
    average = stats[1]

    distribution_rows = db.execute(
        select(models.Review.sentiment_label, func.count(models.Review.id))
        .where(models.Review.movie_id == movie_id)
        .group_by(models.Review.sentiment_label)
    ).all()

    counts = {label: count for label, count in distribution_rows}
    distribution = schemas.SentimentDistribution(
        negative=counts.get("부정", 0),
        neutral=counts.get("중립", 0),
        positive=counts.get("긍정", 0),
    )

    return schemas.MovieRating(
        movie_id=movie.id,
        movie_title=movie.title,
        review_count=review_count,
        sentiment_rating=round(average, 2) if average is not None else None,
        tmdb_vote_average=movie.tmdb_vote_average,
        distribution=distribution,
    )