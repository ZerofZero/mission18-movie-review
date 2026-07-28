"""프론트엔드 설정 모듈.

백엔드 주소와 화면 구성에 필요한 상수를 정의합니다.
백엔드 주소는 Streamlit Cloud 배포 시 secrets 로 주입할 수 있도록
여러 경로에서 순서대로 찾습니다.
"""

import os

import streamlit as st

# ---------------------------------------------------------------------------
# 백엔드 주소
#
# 다음 순서로 값을 찾습니다.
#   1. Streamlit secrets 의 BACKEND_URL
#   2. 환경 변수 BACKEND_URL
#   3. 로컬 개발용 기본값
# ---------------------------------------------------------------------------

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def _resolve_backend_url() -> str:
    """백엔드 주소를 결정합니다."""
    try:
        value = st.secrets.get("BACKEND_URL")
        if value:
            return str(value).rstrip("/")
    except Exception:
        # secrets.toml 이 없는 환경에서는 조회 자체가 실패할 수 있습니다.
        pass

    value = os.environ.get("BACKEND_URL")
    if value:
        return value.rstrip("/")

    return DEFAULT_BACKEND_URL


BACKEND_URL = _resolve_backend_url()

# 백엔드가 잠들어 있다가 깨어나는 경우를 고려해 넉넉하게 설정합니다.
REQUEST_TIMEOUT = 30.0

# 목록 조회 결과를 캐시에 유지하는 시간입니다.
CACHE_TTL_SECONDS = 60


# ---------------------------------------------------------------------------
# 화면 구성
# ---------------------------------------------------------------------------

PAGE_TITLE = "영화 리뷰 감성 분석"

# 영화 목록을 표시할 때 한 줄에 배치할 카드 개수입니다.
GRID_COLUMNS = 4

# 최근 리뷰 화면에서 기본으로 보여줄 리뷰 개수입니다.
RECENT_REVIEW_LIMIT = 10

# 포스터가 없는 영화에 사용할 대체 이미지입니다.
PLACEHOLDER_POSTER = (
    "https://placehold.co/500x750/2E86AB/FFFFFF/png?text=No+Poster"
)


# ---------------------------------------------------------------------------
# 감성 표시
# ---------------------------------------------------------------------------

SENTIMENT_COLORS = {
    "긍정": "#2E86AB",
    "중립": "#F4A261",
    "부정": "#E05C4B",
}

SORT_OPTIONS = {
    "최근 등록순": "latest",
    "감성 평점순": "rating",
    "제목순": "title",
}

# 영화 목록을 한 번에 불러올 개수입니다.
MOVIE_PAGE_SIZE = 20