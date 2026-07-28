"""영화 리뷰 감성 분석 서비스의 화면 구성.

백엔드 API 를 호출해 영화와 리뷰를 조회하고 등록합니다.
데이터는 모두 백엔드에서 관리하며, 이 화면은 별도의 저장 기능을 사용하지 않습니다.
"""

from datetime import date, datetime

import streamlit as st

import api_client as api
from api_client import ApiError
from config import (
    GRID_COLUMNS,
    MOVIE_PAGE_SIZE,
    PAGE_TITLE,
    PLACEHOLDER_POSTER,
    RECENT_REVIEW_LIMIT,
    SENTIMENT_COLORS,
    SORT_OPTIONS,
)

st.set_page_config(page_title=PAGE_TITLE, layout="wide")


# ---------------------------------------------------------------------------
# 공통 도우미
# ---------------------------------------------------------------------------

def format_datetime(value: str | None) -> str:
    """등록 시각 문자열을 보기 좋은 형태로 바꿉니다."""
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def format_date(value: str | None) -> str:
    """개봉일 문자열을 보기 좋은 형태로 바꿉니다."""
    if not value:
        return "정보 없음"
    return value


def parse_date(value: str | None) -> date | None:
    """문자열을 날짜로 변환합니다."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def release_year(value: str | None) -> str:
    """개봉일에서 연도만 추출합니다."""
    if not value or len(value) < 4:
        return "연도 미상"
    return value[:4]


def sentiment_badge(label: str | None) -> str:
    """감성 판정을 색상이 적용된 표시로 변환합니다."""
    if not label:
        return "<span style='color:#888888'>미분석</span>"
    color = SENTIMENT_COLORS.get(label, "#888888")
    return (
        f"<span style='background-color:{color};color:white;"
        f"padding:2px 10px;border-radius:10px;font-size:0.85em'>{label}</span>"
    )


def render_error(exc: ApiError) -> None:
    """API 오류를 화면에 표시합니다."""
    if exc.status_code == 409:
        st.warning(exc.message)
    elif exc.status_code == 400:
        st.warning(exc.message)
    elif exc.status_code == 503:
        st.warning(exc.message)
    else:
        st.error(exc.message)


def render_sentiment_detail(result: dict) -> None:
    """감성 분석 결과의 확률 분포와 점수를 표시합니다."""
    # 감성 분석 응답과 리뷰 등록 응답의 항목 이름이 달라 두 경우를 모두 처리합니다.
    label = result.get("label") or result.get("sentiment_label")
    score = result.get("score")
    if score is None:
        score = result.get("sentiment_score")

    left, right = st.columns([1, 2])

    with left:
        st.markdown(sentiment_badge(label), unsafe_allow_html=True)
        st.metric("감성 점수", f"{score:.2f} / 5.00" if score is not None else "없음")

    with right:
        for key, name in (
            ("prob_positive", "긍정"),
            ("prob_neutral", "중립"),
            ("prob_negative", "부정"),
        ):
            value = float(result.get(key) or 0)
            st.progress(value, text=f"{name} {value * 100:.1f}퍼센트")


# ---------------------------------------------------------------------------
# 사이드바
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    """서버 상태와 서비스 정보를 표시합니다."""
    with st.sidebar:
        st.subheader("서버 상태")

        try:
            health = api.get_health()
        except ApiError as exc:
            st.error(exc.message)
            st.caption("백엔드를 실행한 뒤 새로고침해주세요.")
            return

        st.write(f"등록된 영화 {health.get('movie_count', 0)}편")
        st.write(f"등록된 리뷰 {health.get('review_count', 0)}건")

        st.divider()
        st.caption(
            "감성 분석 모델 "
            + ("사용 가능" if health.get("model_loaded") else "사용 불가")
        )
        st.caption(
            "TMDB 연동 "
            + ("설정됨" if health.get("tmdb_configured") else "설정되지 않음")
        )

        st.divider()
        st.caption("영화 정보와 포스터 이미지는 TMDB 에서 제공받았습니다.")
        st.caption("리뷰 작성자는 별명으로 표시되며 개인정보를 수집하지 않습니다.")


# ---------------------------------------------------------------------------
# 탭 1. 영화 목록
# ---------------------------------------------------------------------------

def render_movie_card(movie: dict) -> None:
    """영화 카드 하나를 그립니다."""
    st.image(movie.get("poster_url") or PLACEHOLDER_POSTER, use_container_width=True)
    st.markdown(f"**{movie['title']}**")
    st.caption(f"{release_year(movie.get('release_date'))} · {movie.get('director') or '감독 미상'}")

    tmdb_score = movie.get("tmdb_vote_average")
    rating = movie.get("sentiment_rating")
    count = movie.get("review_count", 0)

    st.caption(f"TMDB {tmdb_score:.1f} / 10" if tmdb_score else "TMDB 평점 없음")
    if rating is not None:
        st.caption(f"감성 {rating:.2f} / 5 · 리뷰 {count}건")
    else:
        st.caption("리뷰 없음")

    if st.button("상세 보기", key=f"detail_{movie['id']}", use_container_width=True):
        st.session_state["selected_movie_id"] = movie["id"]
        st.rerun()


def render_movie_detail(movie_id: int) -> None:
    """선택한 영화의 상세 정보와 리뷰를 표시합니다."""
    try:
        movie = api.get_movie(movie_id)
        rating = api.get_movie_rating(movie_id)
        reviews = api.list_movie_reviews(movie_id)
    except ApiError as exc:
        render_error(exc)
        return

    st.divider()

    header, close = st.columns([5, 1])
    with header:
        st.subheader(movie["title"])
    with close:
        if st.button("닫기", use_container_width=True):
            st.session_state.pop("selected_movie_id", None)
            st.rerun()

    poster_col, info_col = st.columns([1, 3])

    with poster_col:
        st.image(movie.get("poster_url") or PLACEHOLDER_POSTER, use_container_width=True)

    with info_col:
        st.write(f"**개봉일** {format_date(movie.get('release_date'))}")
        st.write(f"**감독** {movie.get('director') or '정보 없음'}")
        st.write(f"**장르** {movie.get('genre') or '정보 없음'}")
        if movie.get("poster_url"):
            st.write(f"**포스터 주소** {movie['poster_url']}")

        metric_cols = st.columns(3)
        tmdb_score = movie.get("tmdb_vote_average")
        metric_cols[0].metric(
            "TMDB 평점", f"{tmdb_score:.1f} / 10" if tmdb_score else "없음"
        )
        sentiment_rating = rating.get("sentiment_rating")
        metric_cols[1].metric(
            "감성 분석 평점",
            f"{sentiment_rating:.2f} / 5" if sentiment_rating is not None else "없음",
        )
        metric_cols[2].metric("리뷰 개수", f"{rating.get('review_count', 0)}건")

        distribution = rating.get("distribution") or {}
        st.caption(
            f"긍정 {distribution.get('positive', 0)}건 · "
            f"중립 {distribution.get('neutral', 0)}건 · "
            f"부정 {distribution.get('negative', 0)}건"
        )

    st.markdown("#### 리뷰")

    if not reviews:
        st.info("아직 등록된 리뷰가 없습니다.")
        return

    for review in reviews:
        with st.container(border=True):
            top_left, top_right = st.columns([4, 1])
            with top_left:
                st.markdown(f"**{review['author_name']}**")
                st.caption(format_datetime(review.get("created_at")))
            with top_right:
                st.markdown(
                    sentiment_badge(review.get("sentiment_label")),
                    unsafe_allow_html=True,
                )
                score = review.get("sentiment_score")
                if score is not None:
                    st.caption(f"{score:.2f} / 5")
            st.write(review["content"])


def render_movie_list_tab() -> None:
    """영화 목록 화면을 그립니다."""
    st.subheader("영화 목록")

    filter_cols = st.columns([3, 2, 2])

    with filter_cols[0]:
        query = st.text_input("제목 검색", placeholder="영화 제목의 일부를 입력하세요")

    with filter_cols[1]:
        try:
            genres = api.list_genres()
        except ApiError:
            genres = []
        genre = st.selectbox("장르", ["전체"] + genres)

    with filter_cols[2]:
        sort_label = st.selectbox("정렬", list(SORT_OPTIONS.keys()))

    # 검색 조건이 바뀌면 처음부터 다시 불러옵니다.
    condition = (query, genre, sort_label)
    if st.session_state.get("movie_condition") != condition:
        st.session_state["movie_condition"] = condition
        st.session_state["movie_loaded"] = MOVIE_PAGE_SIZE

    loaded = st.session_state.get("movie_loaded", MOVIE_PAGE_SIZE)

    try:
        page = api.list_movies(
            q=query or None,
            genre=None if genre == "전체" else genre,
            sort=SORT_OPTIONS[sort_label],
            limit=loaded,
            offset=0,
        )
    except ApiError as exc:
        render_error(exc)
        return

    movies = page.get("items", [])
    total = page.get("total", 0)

    st.caption(f"전체 {total}편 중 {len(movies)}편을 표시하고 있습니다.")

    # 선택한 영화의 상세 정보를 목록보다 먼저 표시합니다.
    # 목록이 길면 아래쪽에 그렸을 때 화면에서 보이지 않기 때문입니다.
    selected = st.session_state.get("selected_movie_id")
    if selected:
        render_movie_detail(selected)
        st.divider()

    if not movies:
        st.info("조건에 맞는 영화가 없습니다.")
        return

    for start in range(0, len(movies), GRID_COLUMNS):
        row = movies[start : start + GRID_COLUMNS]
        columns = st.columns(GRID_COLUMNS)
        for column, movie in zip(columns, row):
            with column:
                render_movie_card(movie)

    if page.get("has_more"):
        st.divider()
        if st.button(
            f"더 보기 ({len(movies)} / {total})",
            use_container_width=True,
            key="load_more_movies",
        ):
            st.session_state["movie_loaded"] = loaded + MOVIE_PAGE_SIZE
            st.rerun()


# ---------------------------------------------------------------------------
# 탭 2. 영화 추가
# ---------------------------------------------------------------------------

def apply_tmdb_selection(tmdb_id: int) -> None:
    """TMDB 상세 정보를 입력 항목에 반영합니다."""
    try:
        detail = api.get_tmdb_detail(tmdb_id)
    except ApiError as exc:
        render_error(exc)
        return

    st.session_state["mv_title"] = detail.get("title") or ""
    st.session_state["mv_release_date"] = parse_date(detail.get("release_date"))
    st.session_state["mv_director"] = detail.get("director") or ""
    st.session_state["mv_genre"] = detail.get("genre") or ""
    st.session_state["mv_poster_url"] = detail.get("poster_url") or ""
    st.session_state["mv_tmdb_id"] = detail.get("tmdb_id")
    st.session_state["mv_vote_average"] = detail.get("vote_average")
    st.rerun()


def render_movie_add_tab() -> None:
    """영화 추가 화면을 그립니다."""
    st.session_state.setdefault("mv_release_date", None)
    st.subheader("영화 추가")
    st.caption(
        "TMDB 에서 검색해 입력 항목을 자동으로 채울 수 있습니다. "
        "검색 없이 직접 입력해도 됩니다."
    )

    search_cols = st.columns([4, 1])
    with search_cols[0]:
        keyword = st.text_input("TMDB 검색", placeholder="영화 제목을 입력하세요")
    with search_cols[1]:
        st.write("")
        do_search = st.button("검색", use_container_width=True)

    if do_search and keyword:
        try:
            st.session_state["tmdb_results"] = api.search_tmdb(keyword)
        except ApiError as exc:
            render_error(exc)
            st.session_state["tmdb_results"] = []

    results = st.session_state.get("tmdb_results") or []

    if results:
        st.caption(f"검색 결과 {len(results)}건 중 상위 항목입니다.")
        for item in results[:6]:
            with st.container(border=True):
                columns = st.columns([1, 4, 1])
                with columns[0]:
                    st.image(
                        item.get("poster_url") or PLACEHOLDER_POSTER,
                        use_container_width=True,
                    )
                with columns[1]:
                    st.markdown(f"**{item['title']}**")
                    st.caption(
                        f"{format_date(item.get('release_date'))} · "
                        f"TMDB {item.get('vote_average') or 0:.1f}"
                    )
                    overview = item.get("overview")
                    if overview:
                        st.caption(overview[:120] + ("..." if len(overview) > 120 else ""))
                with columns[2]:
                    st.write("")
                    if st.button(
                        "선택", key=f"pick_{item['tmdb_id']}", use_container_width=True
                    ):
                        apply_tmdb_selection(item["tmdb_id"])

    st.divider()
    st.markdown("#### 등록 정보")

    with st.form("movie_form"):
        title = st.text_input("제목", key="mv_title")
        release_value = st.date_input(
            "개봉일",
            key="mv_release_date",
            format="YYYY-MM-DD",
        )
        director = st.text_input("감독", key="mv_director")
        genre = st.text_input(
            "장르", key="mv_genre", placeholder="여러 개인 경우 쉼표로 구분합니다"
        )
        poster_url = st.text_input("포스터 주소", key="mv_poster_url")

        submitted = st.form_submit_button("등록", use_container_width=True)

    if not submitted:
        return

    if not title.strip():
        st.warning("제목을 입력해주세요.")
        return

    payload = {
        "title": title.strip(),
        "release_date": release_value.isoformat() if release_value else None,
        "director": director.strip() or None,
        "genre": genre.strip() or None,
        "poster_url": poster_url.strip() or None,
        "tmdb_id": st.session_state.get("mv_tmdb_id"),
        "tmdb_vote_average": st.session_state.get("mv_vote_average"),
    }

    try:
        created = api.create_movie(payload)
    except ApiError as exc:
        render_error(exc)
        return

    api.clear_caches()
    st.success(f"{created['title']} 을 등록했습니다. 영화 번호는 {created['id']} 입니다.")
    if created.get("poster_url"):
        st.image(created["poster_url"], width=200)


# ---------------------------------------------------------------------------
# 탭 3. 리뷰 작성
# ---------------------------------------------------------------------------

def render_review_write_tab() -> None:
    """리뷰 작성 화면을 그립니다."""
    st.subheader("리뷰 작성")
    st.caption("감성 분석 모델이 한국어 전용이므로 리뷰는 한국어로 작성해야 합니다.")

    try:
        movies = api.list_movies(sort="title", limit=200).get("items", [])
    except ApiError as exc:
        render_error(exc)
        return

    if not movies:
        st.info("먼저 영화를 등록해주세요.")
        return

    options = {
        f"{movie['title']} ({release_year(movie.get('release_date'))})": movie["id"]
        for movie in movies
    }

    with st.form("review_form"):
        selected_label = st.selectbox("영화 선택", list(options.keys()))
        author_name = st.text_input(
            "닉네임", max_chars=50, placeholder="실명 대신 별명을 입력해주세요"
        )
        content = st.text_area(
            "리뷰 내용",
            height=140,
            max_chars=2000,
            placeholder="영화에 대한 감상을 한국어로 작성해주세요",
        )
        submitted = st.form_submit_button("등록", use_container_width=True)

    if not submitted:
        return

    if not author_name.strip():
        st.warning("닉네임을 입력해주세요.")
        return

    if not content.strip():
        st.warning("리뷰 내용을 입력해주세요.")
        return

    with st.spinner("리뷰를 등록하고 감성을 분석하고 있습니다."):
        try:
            created = api.create_review(
                movie_id=options[selected_label],
                author_name=author_name.strip(),
                content=content.strip(),
            )
        except ApiError as exc:
            render_error(exc)
            return

    api.clear_caches()
    st.success("리뷰를 등록했습니다.")

    st.markdown("#### 감성 분석 결과")
    with st.container(border=True):
        st.write(created["content"])
        render_sentiment_detail(created)


# ---------------------------------------------------------------------------
# 탭 4. 최근 리뷰
# ---------------------------------------------------------------------------

def render_recent_review_tab() -> None:
    """최근 리뷰 화면을 그립니다."""
    st.subheader("최근 리뷰")

    limit = st.slider(
        "표시할 리뷰 개수", min_value=5, max_value=50, value=RECENT_REVIEW_LIMIT, step=5
    )

    try:
        reviews = api.list_recent_reviews(limit=limit)
    except ApiError as exc:
        render_error(exc)
        return

    if not reviews:
        st.info("등록된 리뷰가 없습니다.")
        return

    header = st.columns([1, 2, 2, 5, 1, 1])
    for column, text in zip(
        header, ["영화 ID", "영화 제목", "등록일", "리뷰 내용", "감성", "점수"]
    ):
        column.markdown(f"**{text}**")

    st.divider()

    for review in reviews:
        row = st.columns([1, 2, 2, 5, 1, 1])
        row[0].write(review["movie_id"])
        row[1].write(review.get("movie_title") or "-")
        row[2].write(format_datetime(review.get("created_at")))
        row[3].write(review["content"])
        row[4].markdown(
            sentiment_badge(review.get("sentiment_label")), unsafe_allow_html=True
        )
        score = review.get("sentiment_score")
        row[5].write(f"{score:.2f}" if score is not None else "-")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------

def main() -> None:
    st.title(PAGE_TITLE)
    st.caption(
        "영화 정보와 사용자 리뷰를 관리하고, 리뷰의 감성을 분석해 평점을 산출합니다."
    )

    render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["영화 목록", "영화 추가", "리뷰 작성", "최근 리뷰"]
    )

    with tab1:
        render_movie_list_tab()

    with tab2:
        render_movie_add_tab()

    with tab3:
        render_review_write_tab()

    with tab4:
        render_recent_review_tab()


if __name__ == "__main__":
    main()