"""보고서용 도식 생성 스크립트.

서비스 구조도와 데이터베이스 구조도를 이미지 파일로 만듭니다.
생성된 이미지는 images 폴더에 저장되며 보고서에 삽입됩니다.

사용법
    python make_diagrams.py
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUTPUT_DIR = Path(__file__).resolve().parent / "images"

BLUE = "#2E86AB"
ORANGE = "#F4A261"
RED = "#E05C4B"
GRAY = "#6C757D"
LIGHT = "#F2F4F6"
DARK = "#2B2B2B"


# ---------------------------------------------------------------------------
# 공통 설정
# ---------------------------------------------------------------------------

def setup_font() -> None:
    """한글 표시가 가능한 글꼴을 설정합니다."""
    candidates = ["Malgun Gothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans CJK JP", "AppleGothic"]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}

    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break

    plt.rcParams["axes.unicode_minus"] = False


def new_canvas(width: float, height: float):
    """테두리와 눈금이 없는 도화지를 만듭니다."""
    figure, axes = plt.subplots(figsize=(width, height))
    axes.set_xlim(0, 100)
    axes.set_ylim(0, 100)
    axes.axis("off")
    return figure, axes


def draw_box(
    axes,
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    facecolor: str = LIGHT,
    edgecolor: str = GRAY,
    textcolor: str = DARK,
    fontsize: int = 11,
    weight: str = "normal",
    radius: float = 1.2,
) -> None:
    """모서리가 둥근 상자와 가운데 정렬된 글자를 그립니다."""
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=1.4,
    )
    axes.add_patch(box)
    axes.text(
        x + width / 2,
        y + height / 2,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=textcolor,
        weight=weight,
        linespacing=1.5,
    )


def draw_arrow(
    axes,
    start: tuple[float, float],
    end: tuple[float, float],
    label: str = "",
    color: str = GRAY,
    style: str = "-|>",
    offset: float = 1.5,
) -> None:
    """상자 사이를 잇는 화살표를 그립니다."""
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=14,
        linewidth=1.4,
        color=color,
        shrinkA=0,
        shrinkB=0,
    )
    axes.add_patch(arrow)

    if label:
        midx = (start[0] + end[0]) / 2
        midy = (start[1] + end[1]) / 2
        axes.text(
            midx + offset,
            midy,
            label,
            fontsize=9,
            color=color,
            ha="left",
            va="center",
        )


# ---------------------------------------------------------------------------
# 서비스 구조도
# ---------------------------------------------------------------------------

def draw_architecture() -> Path:
    """서비스 구조도를 생성합니다."""
    figure, axes = new_canvas(12, 10)

    # 사용자
    draw_box(axes, 33, 90, 34, 7, "사용자 브라우저", facecolor="#FFFFFF", fontsize=12)

    # 프론트엔드 영역
    draw_box(
        axes, 8, 68, 84, 17, "", facecolor="#EAF3F8", edgecolor=BLUE, radius=1.5
    )
    axes.text(10, 82, "프론트엔드  Streamlit", fontsize=11, color=BLUE, weight="bold")

    tabs = ["영화 목록", "영화 추가", "리뷰 작성", "최근 리뷰"]
    for index, tab in enumerate(tabs):
        draw_box(
            axes,
            11 + index * 19.5,
            70.5,
            17,
            8,
            tab,
            facecolor="#FFFFFF",
            edgecolor=BLUE,
            fontsize=10,
        )

    # 백엔드 영역
    draw_box(
        axes, 8, 40, 84, 22, "", facecolor="#FDF3E7", edgecolor=ORANGE, radius=1.5
    )
    axes.text(10, 59, "백엔드  FastAPI", fontsize=11, color="#C77B2B", weight="bold")

    layers = [
        ("라우터\nmovies / reviews\ntmdb / sentiment", 11),
        ("CRUD 계층\ncrud.py", 39),
        ("ORM\nSQLAlchemy", 67),
    ]
    for label, x in layers:
        draw_box(
            axes,
            x,
            43,
            22,
            13,
            label,
            facecolor="#FFFFFF",
            edgecolor=ORANGE,
            fontsize=10,
        )

    draw_arrow(axes, (33, 49.5), (39, 49.5), color=ORANGE)
    draw_arrow(axes, (61, 49.5), (67, 49.5), color=ORANGE)

    # 하위 구성 요소
    draw_box(
        axes,
        6,
        16,
        26,
        16,
        "감성 분석 모듈\nONNX Runtime\n\nKR-ELECTRA 3-class\nKoELECTRA-small 2-class",
        facecolor="#FFFFFF",
        edgecolor=RED,
        fontsize=10,
    )
    draw_box(
        axes,
        37,
        16,
        26,
        16,
        "데이터베이스\nSQLite\n\nmovies / reviews\nusers",
        facecolor="#FFFFFF",
        edgecolor=BLUE,
        fontsize=10,
    )
    draw_box(
        axes,
        68,
        16,
        26,
        16,
        "외부 API\nTMDB\n\n영화 검색\n상세 정보 조회",
        facecolor="#FFFFFF",
        edgecolor=GRAY,
        fontsize=10,
    )

    # 연결선
    draw_arrow(axes, (50, 90), (50, 85), color=GRAY, style="<|-|>")
    draw_arrow(axes, (50, 68), (50, 62), label="  REST API", color=GRAY, style="<|-|>")
    draw_arrow(axes, (19, 40), (19, 32), color=RED, style="<|-|>")
    draw_arrow(axes, (50, 40), (50, 32), color=BLUE, style="<|-|>")
    draw_arrow(axes, (81, 40), (81, 32), color=GRAY, style="<|-|>")

    # 시드 안내
    axes.text(
        50,
        9,
        "기동 시 데이터가 없으면 seed_movies.json 과 seed_reviews.json 을 읽어 초기 자료를 삽입합니다.",
        fontsize=9,
        color=GRAY,
        ha="center",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "architecture.png"
    figure.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return path


# ---------------------------------------------------------------------------
# 데이터베이스 구조도
#
# 이 부분은 dbdiagram.io 로 대체되어 현재 사용하지 않습니다.
# 도구를 쓸 수 없는 환경에서 다시 필요할 경우를 대비해 남겨 두었습니다.
# ---------------------------------------------------------------------------

TABLES = {
    "movies": [
        ("PK", "id", "INTEGER"),
        ("", "tmdb_id", "INTEGER, UNIQUE"),
        ("", "title", "VARCHAR(200), NOT NULL"),
        ("", "release_date", "DATE"),
        ("", "director", "VARCHAR(100)"),
        ("", "genre", "VARCHAR(100)"),
        ("", "poster_url", "TEXT"),
        ("", "tmdb_vote_average", "FLOAT"),
        ("", "created_at", "DATETIME, NOT NULL"),
    ],
    "reviews": [
        ("PK", "id", "INTEGER"),
        ("FK", "movie_id", "INTEGER, NOT NULL"),
        ("FK", "user_id", "INTEGER"),
        ("", "author_name", "VARCHAR(50), NOT NULL"),
        ("", "content", "TEXT, NOT NULL"),
        ("", "sentiment_label", "VARCHAR(10)"),
        ("", "prob_negative", "FLOAT"),
        ("", "prob_neutral", "FLOAT"),
        ("", "prob_positive", "FLOAT"),
        ("", "sentiment_score", "FLOAT"),
        ("", "created_at", "DATETIME, NOT NULL"),
    ],
    "users": [
        ("PK", "id", "INTEGER"),
        ("", "username", "VARCHAR(50), UNIQUE"),
        ("", "hashed_password", "VARCHAR(255)"),
        ("", "role", "VARCHAR(20), NOT NULL"),
        ("", "created_at", "DATETIME, NOT NULL"),
    ],
}

TABLE_COLORS = {"movies": BLUE, "reviews": ORANGE, "users": GRAY}


def draw_table(axes, name: str, x: float, top: float, width: float) -> tuple:
    """테이블 하나를 그리고 좌우 중앙 좌표를 반환합니다."""
    rows = TABLES[name]
    header_height = 5.0
    row_height = 3.6
    height = header_height + row_height * len(rows)
    color = TABLE_COLORS[name]

    bottom = top - height

    box = FancyBboxPatch(
        (x, bottom),
        width,
        height,
        boxstyle="round,pad=0,rounding_size=0.8",
        facecolor="#FFFFFF",
        edgecolor=color,
        linewidth=1.6,
    )
    axes.add_patch(box)

    header = FancyBboxPatch(
        (x, top - header_height),
        width,
        header_height,
        boxstyle="round,pad=0,rounding_size=0.8",
        facecolor=color,
        edgecolor=color,
        linewidth=1.6,
    )
    axes.add_patch(header)

    axes.text(
        x + width / 2,
        top - header_height / 2,
        name,
        ha="center",
        va="center",
        fontsize=12,
        color="white",
        weight="bold",
    )

    for index, (key, column, spec) in enumerate(rows):
        y = top - header_height - row_height * (index + 0.5)
        axes.text(x + 1.5, y, key, fontsize=8, color=RED, va="center", weight="bold")
        axes.text(x + 6.5, y, column, fontsize=9, color=DARK, va="center")
        axes.text(x + width - 1.5, y, spec, fontsize=8, color=GRAY, va="center", ha="right")

        if index < len(rows) - 1:
            line_y = top - header_height - row_height * (index + 1)
            axes.plot(
                [x + 1, x + width - 1],
                [line_y, line_y],
                color="#E6E6E6",
                linewidth=0.7,
            )

    return x, bottom, x + width, top


def draw_erd() -> Path:
    """데이터베이스 구조도를 생성합니다."""
    figure, axes = new_canvas(13, 9)

    movies_box = draw_table(axes, "movies", 4, 92, 30)
    reviews_box = draw_table(axes, "reviews", 39, 92, 32)
    users_box = draw_table(axes, "users", 74, 60, 24)

    # movies 와 reviews 의 관계
    y = 74
    axes.plot([movies_box[2], reviews_box[0]], [y, y], color=BLUE, linewidth=1.6)
    axes.text(35.5, y + 2.2, "1", fontsize=11, color=BLUE, weight="bold")
    axes.text(37.0, y + 2.2, "N", fontsize=11, color=BLUE, weight="bold")
    axes.text(
        35.6,
        y - 3.5,
        "ON DELETE\nCASCADE",
        fontsize=8,
        color=BLUE,
        ha="center",
        va="top",
    )

    # users 와 reviews 의 관계
    y2 = 50
    axes.plot([reviews_box[2], users_box[0]], [y2, y2], color=GRAY, linewidth=1.6)
    axes.text(72.0, y2 + 2.2, "N", fontsize=11, color=GRAY, weight="bold")
    axes.text(73.4, y2 + 2.2, "1", fontsize=11, color=GRAY, weight="bold")
    axes.text(
        72.7,
        y2 - 3.5,
        "ON DELETE\nSET NULL",
        fontsize=8,
        color=GRAY,
        ha="center",
        va="top",
    )

    axes.text(
        4,
        6,
        "movies 는 title 과 release_date 조합에 UNIQUE 제약을 두어 중복 등록을 방지합니다.\n"
        "users 는 로그인 기능 도입을 위해 정의해 두었으며 현재 구현에서는 사용하지 않습니다.",
        fontsize=9,
        color=GRAY,
        va="bottom",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "erd_matplotlib.png"
    figure.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return path


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    """서비스 구조도를 생성합니다.

    데이터베이스 구조도는 dbdiagram.io 에서 작성해 images/erd.png 로 저장합니다.
    이 스크립트로 다시 만들 경우 해당 파일을 덮어쓰게 되므로 호출하지 않습니다.
    """
    setup_font()

    for path in (draw_architecture(),):
        size = path.stat().st_size / 1024
        print(f"{size:8.1f} KB  {path}")


if __name__ == "__main__":
    main()