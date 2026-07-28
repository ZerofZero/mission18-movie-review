"""ORM 모델 정의.

영화, 리뷰, 사용자 세 개의 테이블을 정의합니다.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """한국 표준시 기준 현재 시각을 반환합니다.

    SQLite 는 시간대 정보를 보존하지 않으므로 시간대를 제거한 값으로 저장합니다.
    저장된 값은 항상 한국 표준시 기준으로 해석합니다.
    """
    return datetime.now(KST).replace(tzinfo=None)


class Movie(Base):
    """영화 정보."""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # TMDB 에서 가져온 영화는 이 값을 가집니다. 직접 입력한 영화는 비어 있습니다.
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    director: Mapped[str | None] = mapped_column(String(100), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    poster_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # TMDB 자체 평점입니다. 10점 만점이며 감성 분석 평점과는 별개입니다.
    tmdb_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_kst
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # 제목과 개봉일이 모두 같은 영화의 중복 등록을 막습니다.
        UniqueConstraint("title", "release_date", name="uq_movie_title_release_date"),
    )

    def __repr__(self) -> str:
        return f"<Movie id={self.id} title={self.title!r}>"


class User(Base):
    """사용자 정보.

    로그인 기능은 후순위 구현 대상이며, 현재는 스키마만 정의되어 있습니다.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_kst
    )

    reviews: Mapped[list["Review"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Review(Base):
    """리뷰 및 감성 분석 결과."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )

    # 로그인 기능 도입 전에는 비어 있습니다.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # 작성 시점의 표시용 이름입니다. 사용자가 이름을 바꾸어도 유지됩니다.
    author_name: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 감성 분석 결과입니다. 분석에 실패한 경우 비어 있을 수 있습니다.
    sentiment_label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prob_negative: Mapped[float | None] = mapped_column(Float, nullable=True)
    prob_neutral: Mapped[float | None] = mapped_column(Float, nullable=True)
    prob_positive: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 확률 가중 평균으로 계산한 1 에서 5 사이의 점수입니다.
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=now_kst
    )

    movie: Mapped["Movie"] = relationship(back_populates="reviews")
    user: Mapped["User | None"] = relationship(back_populates="reviews")

    __table_args__ = (
        # 영화별 리뷰 조회와 최근 리뷰 조회를 위한 인덱스입니다.
        Index("ix_review_movie_created", "movie_id", "created_at"),
        Index("ix_review_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} movie_id={self.movie_id} label={self.sentiment_label!r}>"