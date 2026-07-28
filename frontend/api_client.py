"""백엔드 호출 모듈.

화면 코드가 직접 HTTP 요청을 다루지 않도록 백엔드 API 호출을 함수로 감쌌습니다.
백엔드 주소가 바뀌더라도 config 의 값만 수정하면 됩니다.
"""

from typing import Any

import requests
import streamlit as st

from config import BACKEND_URL, CACHE_TTL_SECONDS, REQUEST_TIMEOUT


class ApiError(Exception):
    """백엔드 호출이 실패했을 때 발생합니다."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# 공통 요청
# ---------------------------------------------------------------------------

def _request(method: str, path: str, **kwargs: Any) -> Any:
    """백엔드에 요청을 보내고 응답 본문을 반환합니다."""
    url = f"{BACKEND_URL}{path}"

    try:
        response = requests.request(
            method, url, timeout=REQUEST_TIMEOUT, **kwargs
        )
    except requests.Timeout as exc:
        raise ApiError(
            "백엔드 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."
        ) from exc
    except requests.ConnectionError as exc:
        raise ApiError(
            f"백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요. ({BACKEND_URL})"
        ) from exc
    except requests.RequestException as exc:
        raise ApiError(f"요청 중 오류가 발생했습니다: {exc}") from exc

    if response.status_code == 204:
        return None

    if response.status_code >= 400:
        raise ApiError(_extract_detail(response), response.status_code)

    if not response.content:
        return None

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("백엔드 응답을 해석할 수 없습니다.") from exc


def _extract_detail(response: requests.Response) -> str:
    """오류 응답에서 사람이 읽을 수 있는 메시지를 추출합니다."""
    try:
        payload = response.json()
    except ValueError:
        return f"요청이 실패했습니다. 상태 코드 {response.status_code}"

    detail = payload.get("detail")

    if isinstance(detail, str):
        return detail

    # 입력 검증 오류는 항목별 목록으로 전달됩니다.
    if isinstance(detail, list) and detail:
        messages = []
        for item in detail:
            location = item.get("loc") or []
            field = location[-1] if location else "입력값"
            messages.append(f"{field}: {item.get('msg', '올바르지 않습니다')}")
        return " / ".join(messages)

    return f"요청이 실패했습니다. 상태 코드 {response.status_code}"


def clear_caches() -> None:
    """조회 결과 캐시를 모두 비웁니다. 등록이나 삭제 후에 호출합니다."""
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# 상태 확인
# ---------------------------------------------------------------------------

def get_health() -> dict:
    """백엔드 상태를 조회합니다."""
    return _request("GET", "/health")


# ---------------------------------------------------------------------------
# 영화
# ---------------------------------------------------------------------------

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def list_movies(
    q: str | None = None,
    genre: str | None = None,
    sort: str = "latest",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """영화 목록을 나누어 조회합니다.

    반환값에는 목록과 함께 전체 개수, 다음 자료의 존재 여부가 포함됩니다.
    """
    params: dict[str, Any] = {"sort": sort, "limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if genre:
        params["genre"] = genre
    return _request("GET", "/movies", params=params)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_movie(movie_id: int) -> dict:
    """영화 한 편을 조회합니다."""
    return _request("GET", f"/movies/{movie_id}")


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def list_genres() -> list[str]:
    """등록된 장르 목록을 조회합니다."""
    return _request("GET", "/movies/genres")


def create_movie(payload: dict) -> dict:
    """영화를 등록합니다."""
    return _request("POST", "/movies", json=payload)


def delete_movie(movie_id: int, admin_key: str) -> None:
    """영화를 삭제합니다."""
    _request(
        "DELETE",
        f"/movies/{movie_id}",
        headers={"X-Admin-Key": admin_key},
    )


# ---------------------------------------------------------------------------
# 리뷰
# ---------------------------------------------------------------------------

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def list_recent_reviews(limit: int = 10) -> list[dict]:
    """전체 리뷰를 최신순으로 조회합니다."""
    return _request("GET", "/reviews", params={"limit": limit})


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def list_movie_reviews(movie_id: int, limit: int | None = None) -> list[dict]:
    """특정 영화의 리뷰를 조회합니다."""
    params = {"limit": limit} if limit else None
    return _request("GET", f"/movies/{movie_id}/reviews", params=params)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_movie_rating(movie_id: int) -> dict:
    """영화의 감성 분석 평점을 조회합니다."""
    return _request("GET", f"/movies/{movie_id}/rating")


def create_review(movie_id: int, author_name: str, content: str) -> dict:
    """리뷰를 등록합니다."""
    return _request(
        "POST",
        "/reviews",
        json={
            "movie_id": movie_id,
            "author_name": author_name,
            "content": content,
        },
    )


def delete_review(review_id: int, admin_key: str) -> None:
    """리뷰를 삭제합니다."""
    _request(
        "DELETE",
        f"/reviews/{review_id}",
        headers={"X-Admin-Key": admin_key},
    )


# ---------------------------------------------------------------------------
# 감성 분석
# ---------------------------------------------------------------------------

def analyze_sentiment(text: str) -> dict:
    """문장의 감성을 분석합니다. 결과는 저장되지 않습니다."""
    return _request("POST", "/sentiment/analyze", json={"text": text})


# ---------------------------------------------------------------------------
# TMDB 연동
# ---------------------------------------------------------------------------

@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def search_tmdb(query: str) -> list[dict]:
    """TMDB 에서 영화를 검색합니다."""
    return _request("GET", "/tmdb/search", params={"query": query})


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_tmdb_detail(tmdb_id: int) -> dict:
    """TMDB 영화 상세 정보를 조회합니다."""
    return _request("GET", f"/tmdb/movie/{tmdb_id}")