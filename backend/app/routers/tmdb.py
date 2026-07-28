"""TMDB 연동 API 라우터.

영화 등록 시 제목, 개봉일, 감독, 장르, 포스터 주소를 자동으로 채우기 위해
TMDB 를 조회합니다. 인증 정보는 서버에만 두고 프론트엔드에는 노출하지 않습니다.
"""

import logging
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app import schemas
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tmdb", tags=["TMDB 연동"])

REQUEST_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# 내부 도우미
# ---------------------------------------------------------------------------

def _ensure_configured() -> None:
    """TMDB 인증 정보가 설정되어 있는지 확인합니다."""
    if not settings.tmdb_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TMDB 인증 정보가 서버에 설정되어 있지 않습니다.",
        )


def _tmdb_get(path: str, params: dict) -> dict:
    """TMDB API 를 호출하고 응답 본문을 반환합니다."""
    merged = {"language": settings.TMDB_LANGUAGE}
    merged.update(settings.tmdb_auth_params)
    merged.update(params)

    url = f"{settings.TMDB_BASE_URL}{path}"

    try:
        response = httpx.get(
            url,
            params=merged,
            headers=settings.tmdb_headers,
            timeout=REQUEST_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="TMDB 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.",
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("TMDB 요청에 실패했습니다: %s", url)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB 에 연결할 수 없습니다.",
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="TMDB 인증에 실패했습니다. 서버의 인증 정보를 확인해주세요.",
        )
    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TMDB 에서 해당 자료를 찾을 수 없습니다.",
        )
    if response.status_code >= 400:
        logger.error(
            "TMDB 오류 응답: %s %s", response.status_code, response.text[:200]
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TMDB 요청이 실패했습니다. 상태 코드 {response.status_code}",
        )

    return response.json()


def _parse_date(value: str | None) -> date | None:
    """TMDB 의 날짜 문자열을 날짜로 변환합니다.

    TMDB 는 개봉일이 미정인 경우 빈 문자열을 반환하므로 별도로 처리합니다.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _poster_url(poster_path: str | None) -> str | None:
    """포스터 경로를 전체 주소로 변환합니다."""
    if not poster_path:
        return None
    return f"{settings.TMDB_IMAGE_BASE_URL}{poster_path}"


def _to_search_item(item: dict) -> schemas.TmdbSearchItem:
    """TMDB 검색 결과 항목을 응답 형식으로 변환합니다."""
    return schemas.TmdbSearchItem(
        tmdb_id=item["id"],
        title=item.get("title") or item.get("original_title") or "제목 없음",
        original_title=item.get("original_title"),
        release_date=_parse_date(item.get("release_date")),
        poster_url=_poster_url(item.get("poster_path")),
        vote_average=item.get("vote_average"),
        overview=item.get("overview") or None,
    )


def _extract_director(credits: dict) -> str | None:
    """제작진 정보에서 감독 이름을 추출합니다.

    공동 연출인 경우 쉼표로 이어 붙입니다.
    """
    crew = credits.get("crew") or []
    directors = [
        member.get("name")
        for member in crew
        if member.get("job") == "Director" and member.get("name")
    ]
    return ", ".join(directors) if directors else None


def _extract_genre(detail: dict) -> str | None:
    """장르 목록을 쉼표로 이어 붙인 문자열로 변환합니다."""
    genres = [g.get("name") for g in (detail.get("genres") or []) if g.get("name")]
    return ", ".join(genres) if genres else None


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------

@router.get(
    "/search",
    response_model=list[schemas.TmdbSearchItem],
    summary="TMDB 영화 검색",
    description=(
        "제목으로 TMDB 에서 영화를 검색합니다. "
        "영화 등록 화면에서 입력 항목을 자동으로 채우기 위해 사용합니다. "
        "감독과 장르는 이 응답에 포함되지 않으며 상세 조회에서 확인할 수 있습니다."
    ),
    responses={
        502: {"description": "TMDB 요청에 실패했습니다."},
        503: {"description": "TMDB 인증 정보가 설정되어 있지 않습니다."},
        504: {"description": "TMDB 응답이 지연되었습니다."},
    },
)
def search_movies(
    query: str = Query(
        min_length=1,
        description="검색할 영화 제목입니다.",
        examples=["기생충"],
    ),
    page: int = Query(
        default=1,
        ge=1,
        le=500,
        description="검색 결과 페이지 번호입니다.",
    ),
):
    """TMDB 검색 결과를 반환합니다."""
    _ensure_configured()

    data = _tmdb_get("/search/movie", {"query": query, "page": page})
    results = data.get("results") or []
    return [_to_search_item(item) for item in results]


@router.get(
    "/movie/{tmdb_id}",
    response_model=schemas.TmdbMovieDetail,
    summary="TMDB 영화 상세 조회",
    description=(
        "TMDB 영화 번호로 상세 정보를 조회합니다. "
        "검색 결과에 없는 감독과 장르를 함께 반환하므로, "
        "영화 등록에 필요한 모든 항목을 이 응답으로 채울 수 있습니다."
    ),
    responses={
        404: {"description": "TMDB 에 해당 영화가 없습니다."},
        502: {"description": "TMDB 요청에 실패했습니다."},
        503: {"description": "TMDB 인증 정보가 설정되어 있지 않습니다."},
        504: {"description": "TMDB 응답이 지연되었습니다."},
    },
)
def get_movie_detail(tmdb_id: int):
    """TMDB 영화 상세 정보를 반환합니다."""
    _ensure_configured()

    detail = _tmdb_get(
        f"/movie/{tmdb_id}", {"append_to_response": "credits"}
    )

    base = _to_search_item(detail)
    return schemas.TmdbMovieDetail(
        **base.model_dump(),
        director=_extract_director(detail.get("credits") or {}),
        genre=_extract_genre(detail),
    )