"""영화 관련 API 라우터."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import verify_admin_key

router = APIRouter(prefix="/movies", tags=["영화"])


@router.get(
    "",
    response_model=schemas.MoviePage,
    summary="영화 목록 조회",
    description=(
        "등록된 영화 목록을 조회합니다. "
        "제목 검색, 장르 필터, 정렬 조건을 함께 지정할 수 있습니다. "
        "목록은 limit 과 offset 으로 나누어 받을 수 있으며, "
        "응답에는 전체 개수와 다음 자료의 존재 여부가 함께 포함됩니다. "
        "각 영화에는 리뷰 개수와 감성 분석 평점이 함께 반환됩니다."
    ),
)
def read_movies(
    q: str | None = Query(
        default=None,
        description="제목에 포함된 문자열로 검색합니다.",
        examples=["기생"],
    ),
    genre: str | None = Query(
        default=None,
        description="장르로 필터링합니다.",
        examples=["드라마"],
    ),
    sort: Literal["latest", "rating", "title"] = Query(
        default="latest",
        description=(
            "정렬 기준입니다. "
            "latest 는 최근 등록순, rating 은 감성 평점 높은순, title 은 제목순입니다."
        ),
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=200,
        description="한 번에 가져올 영화 개수입니다.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="건너뛸 영화 개수입니다.",
    ),
    db: Session = Depends(get_db),
):
    """조건에 맞는 영화 목록을 반환합니다."""
    items = crud.list_movies(
        db, q=q, genre=genre, sort=sort, limit=limit, offset=offset
    )
    total = crud.count_filtered_movies(db, q=q, genre=genre)

    return schemas.MoviePage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get(
    "/genres",
    response_model=list[str],
    summary="장르 목록 조회",
    description=(
        "등록된 영화들에 사용된 장르를 중복 없이 반환합니다. "
        "화면의 장르 선택 항목을 구성하는 데 사용합니다."
    ),
)
def read_genres(db: Session = Depends(get_db)):
    """사용 중인 장르 목록을 반환합니다."""
    return crud.list_genres(db)


@router.get(
    "/{movie_id}",
    response_model=schemas.MovieRead,
    summary="영화 상세 조회",
    description="영화 번호로 한 편의 상세 정보를 조회합니다.",
    responses={404: {"description": "해당 번호의 영화가 없습니다."}},
)
def read_movie(movie_id: int, db: Session = Depends(get_db)):
    """번호로 영화 한 편을 반환합니다."""
    movie = crud.get_movie(db, movie_id)
    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: {movie_id}",
        )
    return movie


@router.get(
    "/{movie_id}/reviews",
    response_model=list[schemas.ReviewRead],
    summary="특정 영화의 리뷰 조회",
    description="지정한 영화에 등록된 리뷰를 최신순으로 조회합니다.",
    responses={404: {"description": "해당 번호의 영화가 없습니다."}},
)
def read_movie_reviews(
    movie_id: int,
    limit: int | None = Query(
        default=None,
        ge=1,
        le=200,
        description="반환할 최대 리뷰 개수입니다. 지정하지 않으면 전체를 반환합니다.",
    ),
    db: Session = Depends(get_db),
):
    """특정 영화의 리뷰 목록을 반환합니다."""
    if crud.get_movie(db, movie_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: {movie_id}",
        )
    return crud.list_movie_reviews(db, movie_id, limit=limit)


@router.get(
    "/{movie_id}/rating",
    response_model=schemas.MovieRating,
    summary="영화 평점 조회",
    description=(
        "리뷰 감성 분석 점수의 평균을 계산해 반환합니다. "
        "감성 점수는 부정에 1점, 중립에 3점, 긍정에 5점의 가중치를 두고 "
        "각 리뷰의 확률 분포로 가중 평균한 값입니다. "
        "TMDB 평점과 감성별 리뷰 분포도 함께 제공합니다."
    ),
    responses={404: {"description": "해당 번호의 영화가 없습니다."}},
)
def read_movie_rating(movie_id: int, db: Session = Depends(get_db)):
    """영화의 감성 분석 평점을 반환합니다."""
    rating = crud.get_movie_rating(db, movie_id)
    if rating is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: {movie_id}",
        )
    return rating


@router.post(
    "",
    response_model=schemas.MovieRead,
    status_code=status.HTTP_201_CREATED,
    summary="영화 등록",
    description=(
        "새로운 영화를 등록합니다. "
        "제목과 개봉일이 모두 같은 영화가 이미 있거나 같은 TMDB 번호가 등록되어 있으면 "
        "409 응답을 반환합니다."
    ),
    responses={409: {"description": "이미 등록된 영화입니다."}},
)
def create_movie(
    movie_in: schemas.MovieCreate,
    db: Session = Depends(get_db),
):
    """영화를 등록하고 등록된 정보를 반환합니다."""
    try:
        return crud.create_movie(db, movie_in)
    except crud.DuplicateMovieError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="영화 삭제",
    description=(
        "영화를 삭제합니다. 해당 영화에 등록된 리뷰도 함께 삭제됩니다. "
        "요청 시 X-Admin-Key 헤더에 관리자 키를 포함해야 합니다."
    ),
    responses={
        204: {"description": "삭제되었습니다."},
        403: {"description": "관리자 키가 올바르지 않습니다."},
        404: {"description": "해당 번호의 영화가 없습니다."},
    },
    dependencies=[Depends(verify_admin_key)],
)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    """영화를 삭제합니다."""
    if not crud.delete_movie(db, movie_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: {movie_id}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)