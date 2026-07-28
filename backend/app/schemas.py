"""요청 및 응답 스키마 정의.

FastAPI 가 입력을 검증하고 응답을 직렬화하는 데 사용하는 Pydantic 모델입니다.
이 클래스들의 필드 설명은 자동 생성되는 API 문서에 그대로 표시됩니다.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SentimentLabel = Literal["부정", "중립", "긍정"]


# ---------------------------------------------------------------------------
# 감성 분석
# ---------------------------------------------------------------------------

class SentimentResult(BaseModel):
    """감성 분석 결과."""

    label: SentimentLabel = Field(description="감성 판정 결과")
    prob_negative: float = Field(description="부정 확률", ge=0.0, le=1.0)
    prob_neutral: float = Field(description="중립 확률", ge=0.0, le=1.0)
    prob_positive: float = Field(description="긍정 확률", ge=0.0, le=1.0)
    score: float = Field(
        description="확률 가중 평균으로 계산한 점수. 1점에서 5점 사이입니다.",
        ge=1.0,
        le=5.0,
    )


class SentimentAnalyzeRequest(BaseModel):
    """감성 분석 요청."""

    text: str = Field(
        description="분석할 한국어 문장",
        min_length=1,
        max_length=2000,
        examples=["연출이 촘촘하고 배우들의 연기가 인상적이었습니다."],
    )


class SentimentAnalyzeResponse(BaseModel):
    """감성 분석 응답."""

    text: str = Field(description="분석 대상 문장")
    result: SentimentResult = Field(description="분석 결과")


# ---------------------------------------------------------------------------
# 영화
# ---------------------------------------------------------------------------

class MovieBase(BaseModel):
    """영화의 공통 입력 필드."""

    title: str = Field(
        description="영화 제목",
        min_length=1,
        max_length=200,
        examples=["기생충"],
    )
    release_date: date | None = Field(
        default=None,
        description="개봉일",
        examples=["2019-05-30"],
    )
    director: str | None = Field(
        default=None,
        description="감독",
        max_length=100,
        examples=["봉준호"],
    )
    genre: str | None = Field(
        default=None,
        description="장르. 여러 개인 경우 쉼표로 구분합니다.",
        max_length=100,
        examples=["드라마, 스릴러"],
    )
    poster_url: str | None = Field(
        default=None,
        description="포스터 이미지 주소",
        examples=["https://image.tmdb.org/t/p/w500/example.jpg"],
    )


class MovieCreate(MovieBase):
    """영화 등록 요청."""

    tmdb_id: int | None = Field(
        default=None,
        description="TMDB 영화 번호. 직접 입력한 영화는 비워 둡니다.",
        examples=[496243],
    )
    tmdb_vote_average: float | None = Field(
        default=None,
        description="TMDB 평점. 10점 만점입니다.",
        ge=0.0,
        le=10.0,
        examples=[8.5],
    )


class MovieRead(MovieBase):
    """영화 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="영화 번호")
    tmdb_id: int | None = Field(default=None, description="TMDB 영화 번호")
    tmdb_vote_average: float | None = Field(
        default=None, description="TMDB 평점. 10점 만점입니다."
    )
    created_at: datetime = Field(description="등록 시각")

    review_count: int = Field(default=0, description="등록된 리뷰 개수")
    sentiment_rating: float | None = Field(
        default=None,
        description="감성 분석 평점. 5점 만점이며 리뷰가 없으면 비어 있습니다.",
    )


class MoviePage(BaseModel):
    """영화 목록 조회 응답.

    목록을 나누어 전달하기 위해 전체 개수와 다음 자료의 존재 여부를 함께 제공합니다.
    """

    items: list[MovieRead] = Field(description="조회된 영화 목록")
    total: int = Field(description="조건에 맞는 전체 영화 개수")
    limit: int = Field(description="한 번에 요청한 개수")
    offset: int = Field(description="건너뛴 개수")
    has_more: bool = Field(description="더 불러올 자료가 있는지 여부")


# ---------------------------------------------------------------------------
# 리뷰
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    """리뷰 등록 요청."""

    movie_id: int = Field(description="리뷰를 등록할 영화 번호", examples=[1])
    author_name: str = Field(
        description="작성자 이름",
        min_length=1,
        max_length=50,
        examples=["황지우"],
    )
    content: str = Field(
        description="리뷰 내용. 한국어로 작성해야 합니다.",
        min_length=1,
        max_length=2000,
        examples=["후반부 전개가 조금 늘어지지만 전체적으로 완성도가 높습니다."],
    )


class ReviewRead(BaseModel):
    """리뷰 조회 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="리뷰 번호")
    movie_id: int = Field(description="영화 번호")
    movie_title: str | None = Field(default=None, description="영화 제목")
    author_name: str = Field(description="작성자 이름")
    content: str = Field(description="리뷰 내용")

    sentiment_label: SentimentLabel | None = Field(
        default=None, description="감성 판정 결과"
    )
    prob_negative: float | None = Field(default=None, description="부정 확률")
    prob_neutral: float | None = Field(default=None, description="중립 확률")
    prob_positive: float | None = Field(default=None, description="긍정 확률")
    sentiment_score: float | None = Field(
        default=None, description="감성 점수. 1점에서 5점 사이입니다."
    )

    created_at: datetime = Field(description="등록 시각")


# ---------------------------------------------------------------------------
# 평점
# ---------------------------------------------------------------------------

class SentimentDistribution(BaseModel):
    """감성 판정 결과별 리뷰 개수."""

    negative: int = Field(default=0, description="부정으로 판정된 리뷰 개수")
    neutral: int = Field(default=0, description="중립으로 판정된 리뷰 개수")
    positive: int = Field(default=0, description="긍정으로 판정된 리뷰 개수")


class MovieRating(BaseModel):
    """영화별 감성 분석 평점."""

    movie_id: int = Field(description="영화 번호")
    movie_title: str = Field(description="영화 제목")
    review_count: int = Field(description="집계에 사용된 리뷰 개수")
    sentiment_rating: float | None = Field(
        default=None,
        description="감성 점수의 평균. 5점 만점이며 리뷰가 없으면 비어 있습니다.",
    )
    tmdb_vote_average: float | None = Field(
        default=None, description="TMDB 평점. 10점 만점입니다."
    )
    distribution: SentimentDistribution = Field(description="감성별 리뷰 분포")


# ---------------------------------------------------------------------------
# TMDB 연동
# ---------------------------------------------------------------------------

class TmdbSearchItem(BaseModel):
    """TMDB 검색 결과 항목."""

    tmdb_id: int = Field(description="TMDB 영화 번호")
    title: str = Field(description="한국어 제목")
    original_title: str | None = Field(default=None, description="원제")
    release_date: date | None = Field(default=None, description="개봉일")
    poster_url: str | None = Field(default=None, description="포스터 이미지 주소")
    vote_average: float | None = Field(default=None, description="TMDB 평점")
    overview: str | None = Field(default=None, description="줄거리 요약")


class TmdbMovieDetail(TmdbSearchItem):
    """TMDB 영화 상세 정보."""

    director: str | None = Field(default=None, description="감독")
    genre: str | None = Field(default=None, description="장르. 쉼표로 구분됩니다.")


# ---------------------------------------------------------------------------
# 기타
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """서버 상태 응답."""

    status: str = Field(description="서버 상태", examples=["ok"])
    app_version: str = Field(description="애플리케이션 버전")
    model_loaded: bool = Field(description="감성 분석 모델의 적재 여부")
    binary_model_loaded: bool = Field(description="보조 감성 분석 모델의 적재 여부")
    tmdb_configured: bool = Field(description="TMDB 인증 정보의 설정 여부")
    movie_count: int = Field(description="등록된 영화 개수")
    review_count: int = Field(description="등록된 리뷰 개수")

    model_config = ConfigDict(protected_namespaces=())


class MessageResponse(BaseModel):
    """단순 메시지 응답."""

    detail: str = Field(description="처리 결과 메시지")