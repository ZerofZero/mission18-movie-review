"""미션 18 보고서 생성 스크립트.

ReportLab 을 사용해 제출용 보고서를 PDF 로 만듭니다.
표 셀은 모두 Paragraph 로 감싸 긴 문장이 겹치지 않도록 처리했습니다.

사용법
    pip install reportlab
    python make_report.py
"""

from datetime import date
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"
IMAGE_DIR = BASE_DIR / "images"
OUTPUT_PATH = BASE_DIR / "mission18_report.pdf"

TITLE = "미션 18 영화 리뷰 감성 분석 서비스"
SUBTITLE = "Streamlit 과 FastAPI 를 이용한 웹 서비스 구현"
AUTHOR = "5팀 황지우"

FRONTEND_URL = "https://mission18-movie-review.streamlit.app"
BACKEND_URL = "https://movie-review-api-256118486084.asia-northeast3.run.app"
API_DOCS_URL = f"{BACKEND_URL}/docs"
SOURCE_REPOSITORY_URL = "https://github.com/ZerofZero/mission18-movie-review"
DOCKER_HUB_URL = "https://hub.docker.com/r/wldn2386/movie-review-api"
ARTIFACT_REGISTRY_IMAGE = (
    "asia-northeast3-docker.pkg.dev/mission18-movie-review/"
    "movie-review/movie-review-api:latest"
)

BLUE = colors.HexColor("#2E86AB")
ORANGE = colors.HexColor("#F4A261")
RED = colors.HexColor("#E05C4B")
GRAY = colors.HexColor("#6C757D")
LIGHT = colors.HexColor("#F2F4F6")
DARK = colors.HexColor("#2B2B2B")
LINE = colors.HexColor("#D9DEE3")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm
CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2


# ---------------------------------------------------------------------------
# 글꼴
# ---------------------------------------------------------------------------

def register_fonts() -> tuple[str, str]:
    """글꼴을 등록하고 본문과 굵은 글씨의 이름을 반환합니다."""
    candidates = [
        ("NanumGothic", "NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf"),
    ]

    for family, regular, bold in candidates:
        regular_path = FONT_DIR / regular
        bold_path = FONT_DIR / bold
        if regular_path.exists():
            pdfmetrics.registerFont(TTFont(family, str(regular_path)))
            bold_name = family
            if bold_path.exists():
                bold_name = f"{family}-Bold"
                pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
            return family, bold_name

    print("글꼴 파일을 찾을 수 없어 기본 글꼴을 사용합니다. 한글이 깨질 수 있습니다.")
    return "Helvetica", "Helvetica-Bold"


BODY_FONT, BOLD_FONT = register_fonts()


# ---------------------------------------------------------------------------
# 문단 양식
# ---------------------------------------------------------------------------

STYLES = {
    "title": ParagraphStyle(
        "title",
        fontName=BOLD_FONT,
        fontSize=22,
        leading=30,
        alignment=TA_CENTER,
        textColor=DARK,
        spaceAfter=6,
    ),
    "subtitle": ParagraphStyle(
        "subtitle",
        fontName=BODY_FONT,
        fontSize=12,
        leading=18,
        alignment=TA_CENTER,
        textColor=GRAY,
        spaceAfter=4,
    ),
    "cover_link": ParagraphStyle(
        "cover_link",
        fontName=BODY_FONT,
        fontSize=8.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=BLUE,
        spaceAfter=3,
        splitLongWords=True,
    ),
    "toc_title": ParagraphStyle(
        "toc_title",
        fontName=BOLD_FONT,
        fontSize=15,
        leading=22,
        textColor=BLUE,
        spaceBefore=14,
        spaceAfter=8,
    ),
    "h1": ParagraphStyle(
        "h1",
        fontName=BOLD_FONT,
        fontSize=15,
        leading=22,
        textColor=BLUE,
        spaceBefore=14,
        spaceAfter=8,
    ),
    "label": ParagraphStyle(
        "label",
        fontName=BOLD_FONT,
        fontSize=10.5,
        leading=16,
        textColor=DARK,
        spaceBefore=8,
        spaceAfter=4,
    ),
    "h2": ParagraphStyle(
        "h2",
        fontName=BOLD_FONT,
        fontSize=12,
        leading=18,
        textColor=DARK,
        spaceBefore=10,
        spaceAfter=5,
    ),
    "body": ParagraphStyle(
        "body",
        fontName=BODY_FONT,
        fontSize=9.5,
        leading=15.5,
        textColor=DARK,
        alignment=TA_LEFT,
        spaceAfter=5,
    ),
    "bullet": ParagraphStyle(
        "bullet",
        fontName=BODY_FONT,
        fontSize=9.5,
        leading=15.5,
        textColor=DARK,
        leftIndent=10,
        bulletIndent=2,
        spaceAfter=3,
    ),
    "caption": ParagraphStyle(
        "caption",
        fontName=BODY_FONT,
        fontSize=8.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=GRAY,
        spaceBefore=3,
        spaceAfter=10,
    ),
    "cell": ParagraphStyle(
        "cell",
        fontName=BODY_FONT,
        fontSize=8.5,
        leading=13,
        textColor=DARK,
    ),
    "cell_head": ParagraphStyle(
        "cell_head",
        fontName=BOLD_FONT,
        fontSize=8.5,
        leading=13,
        textColor=colors.white,
    ),
    "cell_center": ParagraphStyle(
        "cell_center",
        fontName=BODY_FONT,
        fontSize=8.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=DARK,
    ),
    "code": ParagraphStyle(
        "code",
        fontName=BODY_FONT,
        fontSize=8.5,
        leading=13,
        textColor=DARK,
        leftIndent=8,
        backColor=LIGHT,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    ),
}


# ---------------------------------------------------------------------------
# 구성 요소 도우미
# ---------------------------------------------------------------------------

def heading(text: str, level: int = 1):
    """제목 문단을 만듭니다."""
    return Paragraph(text, STYLES["h1" if level == 1 else "h2"])


def body(text: str):
    """본문 문단을 만듭니다."""
    return Paragraph(text, STYLES["body"])


def bullets(items: list[str]) -> list:
    """글머리 기호 목록을 만듭니다."""
    return [
        Paragraph(item, STYLES["bullet"], bulletText="\u00b7") for item in items
    ]


def code_block(text: str):
    """고정 폭처럼 보이는 인용 문단을 만듭니다."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(escaped.replace("\n", "<br/>"), STYLES["code"])


def make_table(
    header: list[str],
    rows: list[list[str]],
    widths: list[float] | None = None,
    align_center: list[int] | None = None,
    header_color=BLUE,
):
    """표를 만듭니다. 모든 칸은 Paragraph 로 감싸 줄바꿈이 되도록 합니다."""
    center = set(align_center or [])

    data = [[Paragraph(text, STYLES["cell_head"]) for text in header]]
    for row in rows:
        cells = []
        for index, text in enumerate(row):
            style = STYLES["cell_center"] if index in center else STYLES["cell"]
            cells.append(Paragraph(str(text), style))
        data.append(cells)

    if widths is None:
        widths = [CONTENT_WIDTH / len(header)] * len(header)
    else:
        total = sum(widths)
        widths = [w / total * CONTENT_WIDTH for w in widths]

    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ]
        )
    )
    return table


_figure_counter = {"value": 0}


def figure(name: str, caption: str, max_height: float = 150 * mm):
    """이미지와 설명을 배치합니다.

    그림 번호는 호출 순서에 따라 자동으로 매겨집니다.
    파일이 없으면 안내 문단을 대신 넣습니다.
    """
    _figure_counter["value"] += 1
    number = _figure_counter["value"]
    caption = f"그림 {number}. {caption}"

    path = IMAGE_DIR / name
    if not path.exists():
        print(f"  이미지 없음: {name}")
        return [
            Paragraph(
                f"[이미지를 찾을 수 없습니다: {name}]", STYLES["caption"]
            )
        ]

    reader = ImageReader(str(path))
    width, height = reader.getSize()
    ratio = height / width

    draw_width = CONTENT_WIDTH
    draw_height = draw_width * ratio

    if draw_height > max_height:
        draw_height = max_height
        draw_width = draw_height / ratio

    return [
        KeepTogether(
            [
                Image(str(path), width=draw_width, height=draw_height),
                Paragraph(caption, STYLES["caption"]),
            ]
        )
    ]


def spacer(height: float = 4 * mm):
    """여백을 만듭니다."""
    return Spacer(1, height)


def natural_sort_key(path: Path) -> list[object]:
    """파일명의 숫자를 실제 숫자 순서로 정렬하기 위한 키를 반환합니다.

    예: docs_2.png가 docs_10.png보다 먼저 오도록 합니다.
    """
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def append_figures_on_separate_pages(
    story: list,
    paths: list[Path],
    caption_prefix: str,
    max_height: float = 220 * mm,
) -> None:
    """여러 이미지를 한 쪽에 한 장씩 배치합니다.

    자동 생성 문서처럼 글자 판독성이 중요한 긴 화면은 여러 장을 같은 쪽에
    축소 배치하지 않고, 각 이미지를 가능한 크게 보여 줍니다.
    """
    for index, path in enumerate(paths, start=1):
        if index > 1:
            story.append(PageBreak())
        story.extend(
            figure(
                path.name,
                f"{caption_prefix} {index}",
                max_height=max_height,
            )
        )


def validate_assets() -> None:
    """보고서 생성 전에 제출 품질과 관련된 이미지 구성을 점검합니다."""
    docs_pages = sorted(IMAGE_DIR.glob("docs_[0-9]*.png"), key=natural_sort_key)
    if len(docs_pages) < 5:
        print(
            "주의: /docs 전체 캡쳐가 5장 미만입니다. "
            "설명 글자의 판독성을 위해 5~6장 분할 캡쳐를 권장합니다."
        )

    delete_capture = IMAGE_DIR / "docs_delete_204.png"
    if delete_capture.exists():
        print(
            "확인: docs_delete_204.png의 X-Admin-Key 값이 "
            "모자이크 처리되었는지 직접 확인하세요."
        )


# ---------------------------------------------------------------------------
# 쪽 장식
# ---------------------------------------------------------------------------

def draw_page(canvas, doc):
    """쪽 번호와 머리글을 그립니다."""
    canvas.saveState()

    canvas.setFont(BODY_FONT, 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(MARGIN, PAGE_HEIGHT - MARGIN + 6 * mm, TITLE)
    canvas.drawRightString(
        PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN + 6 * mm, AUTHOR
    )

    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(
        MARGIN,
        PAGE_HEIGHT - MARGIN + 4 * mm,
        PAGE_WIDTH - MARGIN,
        PAGE_HEIGHT - MARGIN + 4 * mm,
    )

    canvas.drawCentredString(
        PAGE_WIDTH / 2, MARGIN - 8 * mm, str(canvas.getPageNumber())
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# 목차
# ---------------------------------------------------------------------------

class ReportDocTemplate(SimpleDocTemplate):
    """제목을 목차 항목으로 등록하는 문서 틀."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return

        style = flowable.style.name
        if style == "h1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
        elif style == "h2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


def table_of_contents() -> list:
    """목차를 구성합니다."""
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "toc0",
            fontName=BOLD_FONT,
            fontSize=11,
            leading=20,
            textColor=DARK,
            spaceBefore=6,
        ),
        ParagraphStyle(
            "toc1",
            fontName=BODY_FONT,
            fontSize=9.5,
            leading=16,
            textColor=GRAY,
            leftIndent=12,
        ),
    ]

    return [
        Paragraph("목차", STYLES["toc_title"]),
        spacer(4 * mm),
        toc,
        PageBreak(),
    ]


# ---------------------------------------------------------------------------
# 1. 서비스 개요
# ---------------------------------------------------------------------------

def section_overview() -> list:
    story = [heading("1. 서비스 개요")]

    story.append(heading("1.1 목적과 범위", 2))
    story.append(
        body(
            "본 서비스는 영화 정보와 사용자 리뷰를 관리하고, 등록된 리뷰의 감성을 분석해 "
            "영화별 평점을 산출하는 웹 애플리케이션입니다. 사용자가 별점을 직접 매기는 대신 "
            "리뷰 문장의 감성을 모델이 판정하고, 그 결과를 수치로 환산해 평점으로 제공한다는 점이 "
            "일반적인 영화 평점 서비스와 다릅니다."
        )
    )
    story.append(
        body(
            "프론트엔드는 Streamlit, 백엔드는 FastAPI 로 구현했으며 모든 데이터는 백엔드에서 "
            "관리합니다. 프론트엔드는 별도의 저장 기능을 사용하지 않고 백엔드 API 만을 통해 "
            "자료를 주고받습니다."
        )
    )

    story.append(heading("1.2 기술 스택", 2))
    story.append(
        make_table(
            ["구분", "기술", "용도"],
            [
                ["프론트엔드", "Streamlit", "화면 구성과 사용자 입력 처리"],
                ["백엔드", "FastAPI", "REST API 제공과 자동 문서 생성"],
                ["데이터베이스", "SQLite, SQLAlchemy", "영화와 리뷰 저장, ORM 을 통한 추상화"],
                ["모델 서빙", "ONNX Runtime", "PyTorch 없이 감성 분석 모델 추론"],
                ["배포", "Docker", "백엔드 컨테이너화"],
                ["배포", "Google Cloud Run", "백엔드 호스팅"],
                ["배포", "Streamlit Community Cloud", "프론트엔드 호스팅"],
                ["토크나이저", "transformers", "한국어 문장 토큰화"],
                ["외부 API", "TMDB", "영화 정보와 포스터 이미지 조회"],
                ["보고서", "ReportLab", "PDF 문서 생성"],
                ["도식", "matplotlib, dbdiagram.io", "서비스 구조도와 데이터베이스 구조도 작성"],
            ],
            widths=[1.2, 2.0, 4.2],
        )
    )

    story.append(PageBreak())
    story.append(heading("1.3 요구사항 대응 현황", 2))
    story.append(
        make_table(
            ["구분", "요구사항", "구현 여부", "비고"],
            [
                ["프론트엔드", "영화 목록 표시", "완료", "제목, 포스터, 평균 평점 표시"],
                ["프론트엔드", "영화 추가", "완료", "TMDB 검색 연동 및 직접 입력 지원"],
                ["프론트엔드", "리뷰 등록", "완료", "심화 항목"],
                ["프론트엔드", "리뷰 감성 분석 결과 표시", "완료", "심화 항목, 등록 직후 자동 표시"],
                ["프론트엔드", "최근 10개 리뷰 표시", "완료", "심화 항목, 표시 개수 조정 가능"],
                [
                    "프론트엔드",
                    "Streamlit Cloud 배포",
                    "완료",
                    "GitHub 연동, Secrets 로 백엔드 주소 주입",
                ],
                ["백엔드", "영화 등록", "완료", "중복 등록 시 409 응답"],
                ["백엔드", "전체 및 특정 영화 조회", "완료", "검색, 장르 필터, 정렬, 분할 조회 지원"],
                ["백엔드", "특정 영화 삭제", "완료", "관리자 키 필요"],
                ["백엔드", "리뷰 관리", "완료", "심화 항목, 등록 조회 삭제"],
                ["백엔드", "평점 조회", "완료", "심화 항목, 감성 점수 평균"],
                ["백엔드", "리뷰 감성 분석", "완료", "심화 항목, 두 모델 결합"],
                ["백엔드", "모델 경량화", "완료", "심화 항목, ONNX 변환과 동적 양자화"],
                [
                    "백엔드",
                    "외부 접근 가능한 배포",
                    "완료",
                    "Google Cloud Run, 컨테이너 이미지 기반으로 자발적 수행",
                ],
            ],
            widths=[1.2, 2.6, 1.0, 2.8],
            align_center=[2],
        )
    )

    story.append(spacer(6 * mm))
    story.append(heading("1.4 데이터 구성", 2))
    story.append(
        body(
            "서비스 기동 시 데이터베이스가 비어 있으면 준비된 시드 자료를 삽입합니다. "
            "영화 300편은 TMDB 에서 수집했고, 리뷰 60건은 저작권 문제를 피하기 위해 직접 작성했습니다. "
            "리뷰 대상 영화 5편에는 각각 12건의 리뷰를 배정하되, 영화마다 감성 분포를 다르게 설계해 "
            "평점이 서로 구분되도록 했습니다."
        )
    )
    story.append(
        make_table(
            ["영화", "긍정", "중립", "부정", "설계 의도"],
            [
                ["기생충", "8", "3", "1", "호평이 압도적인 작품"],
                ["인터스텔라", "7", "3", "2", "호평 위주이나 길이와 난해함 지적"],
                ["라라랜드", "6", "3", "3", "결말에 대한 호불호"],
                ["부산행", "5", "4", "3", "재미는 있으나 개연성 아쉬움"],
                ["곡성", "4", "3", "5", "해석이 갈리는 작품"],
            ],
            widths=[1.4, 0.7, 0.7, 0.7, 3.5],
            align_center=[1, 2, 3],
        )
    )

    return story


# ---------------------------------------------------------------------------
# 2. 서비스 구조
# ---------------------------------------------------------------------------

def section_architecture() -> list:
    story = [heading("2. 서비스 구조")]

    story.append(heading("2.1 전체 구조도", 2))
    story.extend(figure("architecture.png", "서비스 전체 구조", 130 * mm))

    story.append(heading("2.2 프론트엔드", 2))
    story.append(
        body(
            "Streamlit 으로 구현했으며 하나의 화면에 네 개의 탭을 배치했습니다. "
            "여러 쪽으로 나누는 대신 탭 구조를 택한 이유는 상태 공유가 자연스럽고 "
            "화면 전환 없이 전체 기능을 확인할 수 있기 때문입니다."
        )
    )
    story.append(
        make_table(
            ["탭", "기능", "호출 API"],
            [
                [
                    "영화 목록",
                    "포스터 격자 표시, 제목 검색, 장르 필터, 정렬, 더 보기, 상세 조회",
                    "GET /movies, GET /movies/{id}, GET /movies/{id}/reviews, GET /movies/{id}/rating",
                ],
                [
                    "영화 추가",
                    "TMDB 검색으로 입력 자동 완성, 직접 입력, 등록",
                    "GET /tmdb/search, GET /tmdb/movie/{id}, POST /movies",
                ],
                [
                    "리뷰 작성",
                    "영화 선택, 닉네임과 내용 입력, 등록 직후 감성 분석 결과 표시",
                    "GET /movies, POST /reviews",
                ],
                [
                    "최근 리뷰",
                    "전체 리뷰를 최신순으로 표시, 표시 개수 조정",
                    "GET /reviews",
                ],
            ],
            widths=[1.0, 3.0, 3.6],
        )
    )

    story.append(spacer())
    story.append(
        body(
            "백엔드 주소는 Streamlit secrets, 환경 변수, 기본값 순으로 탐색합니다. "
            "배포 환경에서 코드 수정 없이 주소를 바꿀 수 있도록 하기 위한 구성입니다. "
            "조회 결과는 캐시에 보관하고 등록이나 삭제 후에는 캐시를 비워 목록을 갱신합니다."
        )
    )

    story.append(heading("2.3 백엔드", 2))
    story.append(
        body(
            "FastAPI 로 구현했으며 라우터, CRUD 계층, ORM 의 세 단계로 나누었습니다. "
            "라우터가 SQLAlchemy 를 직접 다루지 않도록 분리해 두어, 데이터베이스를 교체하더라도 "
            "CRUD 계층만 수정하면 됩니다."
        )
    )
    story.extend(
        bullets(
            [
                "라우터는 HTTP 요청을 받아 입력을 검증하고 응답 상태 코드를 결정합니다.",
                "CRUD 계층은 조회와 저장 로직을 담당하며 예외를 자체 정의해 전달합니다.",
                "ORM 계층은 SQLAlchemy 2.0 방식으로 테이블과 관계를 정의합니다.",
                "감성 분석과 TMDB 연동은 별도 모듈로 분리해 교체가 쉽도록 했습니다.",
            ]
        )
    )

    story.append(heading("2.4 모델 서빙", 2))
    story.append(
        body(
            "감성 분석 모델은 애플리케이션 기동 시 한 번만 적재하고 이후 재사용합니다. "
            "요청마다 모델을 불러오면 응답이 지연되기 때문입니다. "
            "두 모델 모두 ONNX Runtime 으로 추론하며 PyTorch 에 의존하지 않습니다. "
            "모델 적재에 실패하더라도 예외를 전파하지 않고 상태만 기록하므로, "
            "영화 관리 기능은 정상적으로 동작합니다."
        )
    )

    story.append(heading("2.5 데이터 흐름", 2))
    story.append(
        body("리뷰가 등록될 때의 처리 순서는 다음과 같습니다.")
    )
    story.append(
        code_block(
            "사용자 입력\n"
            "  → 프론트엔드가 POST /reviews 호출\n"
            "  → 한국어 여부 검증 (한글 비율 30퍼센트 미만이면 400)\n"
            "  → 모델 적재 여부 확인 (미적재 시 503)\n"
            "  → 주 모델과 보조 모델 추론 후 확률 결합\n"
            "  → 감성 판정과 점수를 리뷰와 함께 저장\n"
            "  → 201 응답으로 결과 반환\n"
            "  → 프론트엔드가 확률 분포와 점수를 화면에 표시"
        )
    )

    story.append(CondPageBreak(75 * mm))
    story.append(heading("2.6 배포 구성", 2))
    story.append(
        body(
            "프론트엔드와 백엔드를 서로 다른 환경에 배포했습니다. "
            "Streamlit Community Cloud 는 Streamlit 앱만 실행하므로 FastAPI 를 함께 올릴 수 없고, "
            "백엔드는 감성 분석 모델을 적재해야 하므로 컨테이너 환경이 필요했습니다. "
            "프론트엔드는 GitHub 저장소의 소스를 직접 실행하고, 백엔드는 컨테이너 이미지를 통해 "
            "Google Cloud Run 에 배포했습니다."
        )
    )

    story.append(Paragraph("서비스 주소", STYLES["label"]))
    story.append(
        make_table(
            ["구분", "주소"],
            [
                ["프론트엔드", FRONTEND_URL],
                ["백엔드 API", BACKEND_URL],
                ["API 문서", API_DOCS_URL],
                ["소스 저장소", SOURCE_REPOSITORY_URL],
                ["컨테이너 이미지", DOCKER_HUB_URL],
            ],
            widths=[1.5, 6.1],
        )
    )

    story.append(Paragraph("백엔드 배포 구성", STYLES["label"]))
    story.append(
        make_table(
            ["항목", "값"],
            [
                ["호스팅", "Google Cloud Run"],
                ["리전", "asia-northeast3, 서울"],
                ["서비스명", "movie-review-api"],
                ["자원", "메모리 2 GiB, CPU 1"],
                ["인스턴스", "최대 1개"],
                ["요청 제한 시간", "300초"],
                ["접근", "미인증 요청 허용"],
                ["컨테이너", "python:3.12-slim 기반, 압축 491 MB, 디스크 1.38 GB"],
            ],
            widths=[1.8, 5.8],
        )
    )
    story.append(
        body(
            "컨테이너 이미지는 Docker Hub 와 Artifact Registry 에 저장했습니다. "
            f"Cloud Run 배포에는 {ARTIFACT_REGISTRY_IMAGE} 이미지를 사용했습니다. "
            "외부 레지스트리 의존성을 줄이고 배포 가용성을 높이기 위한 선택입니다."
        )
    )

    story.append(
        KeepTogether(
            [
                Paragraph("프론트엔드 배포 구성", STYLES["label"]),
                make_table(
                    ["항목", "값"],
                    [
                        ["호스팅", "Streamlit Community Cloud"],
                        ["저장소", "ZerofZero/mission18-movie-review"],
                        ["브랜치", "main"],
                        ["진입점", "frontend/app.py"],
                        ["Python", "3.12"],
                        ["의존성", "frontend/requirements.txt"],
                    ],
                    widths=[1.8, 5.8],
                ),
            ]
        )
    )
    story.append(
        body(
            "백엔드 주소는 저장소에 기록하지 않고 Streamlit Secrets 의 BACKEND_URL 로 주입했습니다. "
            "컨테이너 이미지에도 비밀 정보를 포함하지 않았으며, .dockerignore 로 .env 를 제외한 뒤 "
            "Cloud Run 환경 변수에는 TMDB_API_KEY 와 ADMIN_KEY 만 등록했습니다. "
            "모델 경로와 파일명은 비밀 정보가 아니므로 config.py 의 기본값에 실제 값을 지정했습니다."
        )
    )

    story.append(Paragraph("운영상 특성", STYLES["label"]))
    story.extend(
        bullets(
            [
                "일정 시간 요청이 없으면 인스턴스가 종료됩니다. 다음 요청에서 컨테이너와 모델을 "
                "다시 적재하므로 첫 접속에 약 20초가 걸릴 수 있으며, 프론트엔드 요청 제한 시간을 "
                "30초로 설정했습니다.",
                "Cloud Run 의 로컬 파일 시스템은 영속적이지 않습니다. 인스턴스가 새로 시작될 때 "
                "영화 300편과 리뷰 60건을 다시 삽입하므로 기본 화면은 유지되지만, 사용자가 추가한 "
                "자료는 인스턴스 종료 후 사라질 수 있습니다.",
                "SQLite 파일이 인스턴스마다 분리되는 것을 방지하기 위해 최대 인스턴스를 1개로 "
                "제한했습니다.",
                "주 모델이 352 MB 로 GitHub 의 단일 파일 상한을 넘기므로 모델 가중치는 저장소에서 "
                "제외했습니다. 모델은 컨테이너 이미지에 포함하고 저장소 README 에 배치 방법을 "
                "안내했습니다.",
            ]
        )
    )

    story.append(
        body(
            "배포된 서비스의 화면입니다. 프론트엔드는 Streamlit Community Cloud 에서 실행되며, "
            "사이드바에 표시된 영화와 리뷰 개수는 Cloud Run 에 배포된 백엔드를 호출해 받아온 "
            "값입니다. 두 환경이 실제로 연동되어 동작하고 있음을 확인할 수 있습니다."
        )
    )
    story.extend(
        figure("deploy_frontend.png", "배포된 서비스의 영화 목록 화면", 120 * mm)
    )

    return story


# ---------------------------------------------------------------------------
# 3. 데이터베이스 설계
# ---------------------------------------------------------------------------

def section_database() -> list:
    story = [heading("3. 데이터베이스 설계")]

    story.append(heading("3.1 데이터베이스 구조도", 2))
    story.extend(figure("erd.png", "데이터베이스 구조도", 120 * mm))

    story.append(heading("3.2 테이블 명세", 2))

    story.append(Paragraph("movies", STYLES["label"]))
    story.append(
        make_table(
            ["컬럼", "자료형", "제약", "설명"],
            [
                ["id", "INTEGER", "PK", "영화 번호"],
                ["tmdb_id", "INTEGER", "UNIQUE", "TMDB 영화 번호, 직접 입력 시 비어 있음"],
                ["title", "VARCHAR(200)", "NOT NULL", "영화 제목"],
                ["release_date", "DATE", "", "개봉일"],
                ["director", "VARCHAR(100)", "", "감독"],
                ["genre", "VARCHAR(100)", "", "장르, 쉼표로 구분"],
                ["poster_url", "TEXT", "", "포스터 이미지 주소"],
                ["tmdb_vote_average", "FLOAT", "", "TMDB 평점, 10점 만점"],
                ["created_at", "DATETIME", "NOT NULL", "등록 시각"],
            ],
            widths=[1.7, 1.3, 1.0, 3.6],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "제목과 개봉일 조합에 UNIQUE 제약을 두어 같은 영화가 중복 등록되는 것을 방지합니다. "
            "제목이 같아도 개봉일이 다르면 리메이크로 간주해 허용합니다."
        )
    )

    story.append(Paragraph("reviews", STYLES["label"]))
    story.append(
        make_table(
            ["컬럼", "자료형", "제약", "설명"],
            [
                ["id", "INTEGER", "PK", "리뷰 번호"],
                ["movie_id", "INTEGER", "FK, NOT NULL", "대상 영화, 삭제 시 함께 삭제"],
                ["user_id", "INTEGER", "FK", "작성자 계정, 현재 미사용"],
                ["author_name", "VARCHAR(50)", "NOT NULL", "작성자 표시명"],
                ["content", "TEXT", "NOT NULL", "리뷰 내용"],
                ["sentiment_label", "VARCHAR(10)", "", "감성 판정, 부정 중립 긍정"],
                ["prob_negative", "FLOAT", "", "부정 확률"],
                ["prob_neutral", "FLOAT", "", "중립 확률"],
                ["prob_positive", "FLOAT", "", "긍정 확률"],
                ["sentiment_score", "FLOAT", "", "감성 점수, 1점에서 5점"],
                ["created_at", "DATETIME", "NOT NULL", "등록 시각"],
            ],
            widths=[1.7, 1.3, 1.2, 3.4],
        )
    )

    story.append(Paragraph("users", STYLES["label"]))
    story.append(
        make_table(
            ["컬럼", "자료형", "제약", "설명"],
            [
                ["id", "INTEGER", "PK", "사용자 번호"],
                ["username", "VARCHAR(50)", "UNIQUE, NOT NULL", "로그인 아이디"],
                ["hashed_password", "VARCHAR(255)", "NOT NULL", "해시된 비밀번호"],
                ["role", "VARCHAR(20)", "NOT NULL", "권한, user 또는 admin"],
                ["created_at", "DATETIME", "NOT NULL", "가입 시각"],
            ],
            widths=[1.7, 1.3, 1.4, 3.2],
        )
    )

    story.append(spacer())
    story.append(heading("3.3 설계 판단", 2))
    story.extend(
        bullets(
            [
                "감성 확률을 하나의 문자열로 묶지 않고 세 개의 컬럼으로 나누어 저장했습니다. "
                "SQL 로 직접 집계할 수 있고 구조도에서도 항목이 명확히 드러납니다.",
                "감성 점수를 저장 시점에 계산해 두었습니다. 평점 조회 시 확률에서 다시 계산하지 않고 "
                "평균 함수만 적용하면 되므로 조회가 단순해집니다.",
                "감성 관련 컬럼은 향후 미분석 리뷰를 저장할 수 있도록 NULL 을 허용했습니다. "
                "현재 구현에서는 감성 분석 모델이 적재되지 않거나 추론을 수행할 수 없으면 "
                "503 응답을 반환하며 리뷰를 저장하지 않습니다.",
                "작성자 표시명을 계정 번호와 별도로 저장했습니다. 사용자가 이름을 바꾸어도 "
                "과거 리뷰의 표기는 유지되며, 소유권 판정은 계정 번호로 수행할 수 있습니다.",
                "users 테이블은 로그인 기능 도입을 대비해 미리 정의했습니다. 현재는 사용하지 않지만 "
                "나중에 기능을 추가할 때 스키마 변경이 필요하지 않습니다.",
                "SQLite 는 외래 키 제약을 기본으로 강제하지 않으므로, 연결마다 관련 설정을 활성화해 "
                "영화 삭제 시 리뷰가 함께 삭제되도록 했습니다.",
            ]
        )
    )

    story.append(spacer())
    story.append(
        body(
            "시각은 한국 표준시 기준으로 저장합니다. SQLite 는 시간대 정보를 보존하지 않으므로 "
            "협정 세계시로 저장하면 화면에 아홉 시간 어긋난 값이 표시되고 조회할 때마다 변환이 "
            "필요합니다. 처음부터 한국 표준시로 저장해 이 문제를 피했습니다."
        )
    )

    return story


# ---------------------------------------------------------------------------
# 4. API 명세
# ---------------------------------------------------------------------------

def section_api() -> list:
    story = [heading("4. API 명세")]

    story.append(heading("4.1 엔드포인트 목록", 2))
    story.append(
        make_table(
            ["구분", "메서드", "경로", "기능"],
            [
                ["영화", "GET", "/movies", "목록 조회, 검색 필터 정렬 분할"],
                ["영화", "POST", "/movies", "등록, 중복 시 409"],
                ["영화", "GET", "/movies/genres", "장르 목록 조회"],
                ["영화", "GET", "/movies/{movie_id}", "상세 조회"],
                ["영화", "DELETE", "/movies/{movie_id}", "삭제, 관리자 키 필요"],
                ["영화", "GET", "/movies/{movie_id}/reviews", "해당 영화의 리뷰 조회"],
                ["영화", "GET", "/movies/{movie_id}/rating", "감성 분석 평점 조회"],
                ["리뷰", "GET", "/reviews", "전체 리뷰 최신순 조회"],
                ["리뷰", "POST", "/reviews", "등록, 감성 분석 동시 수행"],
                ["리뷰", "GET", "/reviews/{review_id}", "상세 조회"],
                ["리뷰", "DELETE", "/reviews/{review_id}", "삭제, 관리자 키 필요"],
                ["감성 분석", "POST", "/sentiment/analyze", "저장 없이 문장 분석"],
                ["TMDB 연동", "GET", "/tmdb/search", "제목으로 영화 검색"],
                ["TMDB 연동", "GET", "/tmdb/movie/{tmdb_id}", "상세 정보 조회"],
                ["기타", "GET", "/", "서비스 안내"],
                ["기타", "GET", "/health", "서버 및 모델 상태 확인"],
            ],
            widths=[1.1, 0.9, 2.6, 3.0],
            align_center=[1],
        )
    )

    story.append(spacer())
    status_table = make_table(
        ["코드", "상황"],
        [
            ["200", "조회 성공"],
            ["201", "등록 성공"],
            ["204", "삭제 성공"],
            ["400", "입력값 오류. 리뷰가 한국어로 작성되지 않은 경우"],
            ["403", "관리자 키가 올바르지 않음"],
            ["404", "대상을 찾을 수 없음"],
            ["409", "이미 등록된 영화"],
            ["422", "요청 형식 오류. FastAPI 가 자동으로 처리"],
            ["502", "TMDB 요청 실패"],
            ["503", "감성 분석 모델 미적재 또는 TMDB 인증 정보 미설정"],
            ["504", "TMDB 응답 지연"],
        ],
        widths=[0.8, 6.8],
        align_center=[0],
    )
    # 상태 코드 표의 마지막 몇 행만 다음 쪽으로 넘어가는 현상을 막습니다.
    story.append(KeepTogether([heading("4.2 응답 상태 코드", 2), status_table]))

    # 남은 공간이 너무 작으면 절 제목과 설명을 함께 다음 쪽에서 시작합니다.
    story.append(CondPageBreak(55 * mm))
    story.append(heading("4.3 자동 생성 문서", 2))

    docs_pages = sorted(
        IMAGE_DIR.glob("docs_[0-9]*.png"),
        key=natural_sort_key,
    )
    docs_count_text = f"아래 {len(docs_pages)}개 그림은" if docs_pages else "아래 그림은"
    story.append(
        body(
            "모든 엔드포인트에 요약, 상세 설명, 파라미터 설명, 응답 코드별 설명을 지정했습니다. "
            "요청 본문에는 예시값을 넣어 문서에서 바로 시험할 수 있도록 했습니다. "
            f"{docs_count_text} 문서 전체를 구간별로 나누어 담은 것이며, 개별 항목을 펼친 화면은 "
            "4.4절과 4.5절, 그리고 6.6절에서 확인할 수 있습니다."
        )
    )
    if not docs_pages:
        story.append(body("[문서 캡쳐 이미지를 찾을 수 없습니다.]"))
    else:
        append_figures_on_separate_pages(
            story,
            docs_pages,
            "자동 생성 문서 화면",
            max_height=220 * mm,
        )

    story.append(PageBreak())
    story.append(heading("4.4 인증 처리", 2))
    story.append(
        body(
            "영화와 리뷰 삭제는 되돌릴 수 없는 요청이므로 X-Admin-Key 헤더에 관리자 키를 "
            "포함하도록 했습니다. 관리자 키는 서버의 환경 변수로 관리하며 소스 코드에 포함하지 않습니다. "
            "문서에서는 삭제 엔드포인트에만 자물쇠 표시가 나타나고, 상단의 인증 버튼으로 키를 "
            "한 번 입력하면 이후 요청에 자동으로 포함됩니다."
        )
    )
    story.extend(
        figure("docs_auth_1.png", "관리자 키 입력 창", 105 * mm)
    )
    story.extend(
        figure("docs_auth_2.png", "인증이 완료된 상태", 105 * mm)
    )
    story.append(
        body(
            "인증 여부에 따라 삭제 요청의 결과가 달라집니다. 키 없이 요청하면 거부되고, "
            "인증을 마친 뒤에는 정상적으로 처리됩니다."
        )
    )
    story.extend(
        figure("docs_delete_403.png", "인증 없이 삭제를 시도한 경우 403 응답", 130 * mm)
    )
    story.extend(
        figure("docs_delete_204.png", "인증 후 삭제에 성공한 경우 204 응답", 130 * mm)
    )

    story.append(PageBreak())
    story.append(heading("4.5 오류 처리", 2))
    story.append(
        body(
            "예외 상황마다 상태 코드를 구분하고 사용자가 원인을 알 수 있는 메시지를 제공합니다. "
            "한국어 검증 실패의 경우 현재 한글 비율을 함께 알려주어 임계값 조정 여부를 판단할 수 "
            "있게 했습니다."
        )
    )
    story.extend(figure("docs_korean_400.png", "한국어로 작성되지 않은 리뷰 등록 시 400 응답", 120 * mm))
    story.extend(figure("docs_duplicate_409.png", "이미 등록된 영화를 다시 등록할 때 409 응답", 130 * mm))

    return story


# ---------------------------------------------------------------------------
# 5. 감성 분석 모델
# ---------------------------------------------------------------------------

def section_model() -> list:
    story = [heading("5. 감성 분석 모델")]

    story.append(heading("5.1 모델 선정 과정", 2))
    story.append(
        body(
            "미션 13에서 학습하고 미션 16에서 ONNX 로 변환한 KR-ELECTRA 기반 3-class 감성 분류 "
            "모델을 우선 후보로 두었습니다. 이미 확보한 자산을 재사용할 수 있고 부정, 중립, 긍정의 "
            "세 단계 판정이 평점 산출에 적합하기 때문입니다."
        )
    )
    story.append(
        body(
            "다만 이 모델의 학습 데이터는 쇼핑몰과 SNS 리뷰였고 영화 리뷰는 포함되지 않았습니다. "
            "학습 도메인과 사용 도메인이 다르면 성능이 떨어질 수 있으므로, 그대로 사용할 수 있는지 "
            "먼저 검증했습니다."
        )
    )

    story.append(heading("5.2 도메인 전이 성능 검증", 2))
    story.append(
        body(
            "직접 작성한 영화 리뷰 60건에 의도한 감성을 미리 지정하고, 모델 예측과 비교했습니다. "
            "검증 결과 60건 중 52건이 일치해 86.7퍼센트를 기록했습니다. "
            "미션 16의 자체 시험 자료에서 92.03퍼센트였던 것과 비교하면 약 5.3퍼센트포인트 하락한 "
            "수치입니다."
        )
    )
    story.append(
        make_table(
            ["의도한 감성", "부정으로 예측", "중립으로 예측", "긍정으로 예측", "합계", "일치율"],
            [
                ["부정", "13", "1", "0", "14", "92.9퍼센트"],
                ["중립", "2", "13", "1", "16", "81.2퍼센트"],
                ["긍정", "2", "2", "26", "30", "86.7퍼센트"],
            ],
            widths=[1.3, 1.3, 1.3, 1.3, 0.8, 1.2],
            align_center=[1, 2, 3, 4, 5],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "오분류 8건을 판정 방향에 따라 나누면 다음과 같습니다. "
            "부정적 어휘로 긍정을 표현한 반어 문장이 절반을 차지하며, "
            "이 가운데 둘은 부정으로, 나머지 둘은 중립으로 판정되었습니다."
        )
    )
    story.append(
        make_table(
            ["유형", "건수", "판정 방향", "예시"],
            [
                [
                    "부정 어휘로 긍정 표현",
                    "2",
                    "긍정을 부정으로",
                    "마지막 재회 장면에서는 눈물을 참기가 어려웠습니다.",
                ],
                [
                    "부정 어휘로 긍정 표현",
                    "2",
                    "긍정을 중립으로",
                    "불친절하지만 그만큼 곱씹을 거리가 많은 작품입니다.",
                ],
                [
                    "중립 경계",
                    "2",
                    "중립을 부정으로",
                    "러닝타임이 길어서 중간에 집중이 조금 흐트러졌습니다.",
                ],
                [
                    "중립 경계",
                    "1",
                    "중립을 긍정으로",
                    "무난하게 시간을 보내기에는 나쁘지 않은 선택입니다.",
                ],
                [
                    "명백한 오류",
                    "1",
                    "부정을 중립으로",
                    "기대하고 봤는데 지루하기만 하고 남는 것이 없었습니다.",
                ],
            ],
            widths=[1.1, 0.6, 1.5, 4.0],
            align_center=[1],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "네 건은 부정적 어휘로 긍정을 표현하는 구조에서 발생했습니다. "
            "눈물, 불안, 불친절 같은 단어는 상품 리뷰에서는 명백한 불만 신호이지만 "
            "영화 평론에서는 감동이나 연출력에 대한 찬사로 쓰입니다. "
            "중립 경계 3건은 사람이 보아도 판단이 갈릴 수 있는 문장이며, "
            "나머지 1건은 정답이 분명한데도 놓친 사례입니다."
        )
    )

    story.append(PageBreak())
    story.append(heading("5.3 모델 비교 실험", 2))
    story.append(
        body(
            "다른 공개 모델로 교체하면 개선될 수 있는지 확인하기 위해 동일한 60건으로 비교했습니다. "
            "공개 모델 중에는 출력 인덱스와 감성의 대응이 명시되지 않은 경우가 많아, 가능한 모든 "
            "대응을 시도하고 가장 높은 일치율을 채택했습니다. 비교 대상 모델에 유리한 조건입니다."
        )
    )
    story.append(
        make_table(
            ["모델", "학습 데이터", "분류", "일치율"],
            [
                ["미션 16 KR-ELECTRA", "쇼핑몰 및 SNS 리뷰", "3-class", "86.7퍼센트"],
                ["alsgyu KcBERT", "AI 허브 한국어 감정 데이터", "3-class", "83.3퍼센트"],
            ],
            widths=[2.4, 2.6, 1.0, 1.4],
            align_center=[2, 3],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "3-class 모델로는 개선되지 않았습니다. 이어서 영화 리뷰 도메인의 2-class 모델을 "
            "확인했습니다. 중립이 없는 모델이므로 중립 리뷰 16건을 제외한 44건으로 비교했고, "
            "앞서 오분류된 반어 문장 4건도 함께 시험했습니다. "
            "미션 16 모델은 이 4건을 모두 틀렸습니다."
        )
    )
    story.append(
        make_table(
            ["모델", "학습 데이터", "일치율", "반어 문장"],
            [
                ["daekeun-ml KoELECTRA-small", "NSMC", "100.0퍼센트", "4 / 4"],
                ["sangrimlee mBERT", "NSMC", "97.7퍼센트", "4 / 4"],
                ["matthewburke", "미공개", "97.7퍼센트", "4 / 4"],
                ["Copycats KoELECTRA", "일반화 감성 자료", "97.7퍼센트", "3 / 4"],
                ["monologg KoELECTRA", "NSMC", "97.7퍼센트", "3 / 4"],
                ["WhitePeak BERT", "미공개", "72.7퍼센트", "1 / 4"],
                ["미션 16 KR-ELECTRA", "쇼핑몰 및 SNS 리뷰", "88.6퍼센트", "0 / 4"],
            ],
            widths=[2.6, 2.2, 1.3, 1.3],
            align_center=[2, 3],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "NSMC 로 학습한 모델들이 반어적 표현을 정확히 판정했습니다. 실제 영화 리뷰에서 "
            "해당 표현이 긍정 평가로 쓰인다는 것을 학습했기 때문으로 보입니다. "
            "가장 작은 KoELECTRA-small 모델이 가장 높은 성능을 보인 점은, 이 문제에서 "
            "학습 도메인의 일치가 모델 크기보다 중요하다는 것을 시사합니다."
        )
    )

    story.append(heading("5.4 두 모델의 결합", 2))
    story.append(
        body(
            "3-class 모델만 중립을 판정할 수 있고, 2-class 모델은 긍정과 부정 구분이 정확합니다. "
            "각자의 역할을 나누는 결합을 설계했으며, 두 규칙을 세워 60건 전체로 검증했습니다."
        )
    )
    story.extend(
        bullets(
            [
                "규칙 A는 중립 확률을 유지한 채 나머지 확률을 2-class 모델의 비율로 다시 배분합니다.",
                "규칙 B는 3-class 모델이 중립으로 판정한 문장은 그대로 두고, 긍정이나 부정으로 "
                "판정한 문장에만 규칙 A를 적용합니다.",
            ]
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        make_table(
            ["보조 모델", "규칙 A", "규칙 B"],
            [
                ["daekeun-ml KoELECTRA-small", "90.0퍼센트", "90.0퍼센트"],
                ["sangrimlee mBERT", "90.0퍼센트", "90.0퍼센트"],
                ["matthewburke", "88.3퍼센트", "88.3퍼센트"],
            ],
            widths=[3.4, 1.6, 1.6],
            align_center=[1, 2],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "두 규칙의 결과가 같았으므로 개입 범위가 작고 설명이 명확한 규칙 B를 채택했습니다. "
            "보조 모델은 성능과 용량을 함께 고려해 KoELECTRA-small 을 선택했습니다."
        )
    )
    story.append(
        make_table(
            ["구분", "단독", "결합", "변화"],
            [
                ["전체 일치율", "86.7퍼센트", "90.0퍼센트", "3.3퍼센트포인트 상승"],
                ["부정", "92.9퍼센트", "92.9퍼센트", "변화 없음"],
                ["중립", "81.2퍼센트", "81.2퍼센트", "변화 없음"],
                ["긍정", "86.7퍼센트", "93.3퍼센트", "6.6퍼센트포인트 상승"],
            ],
            widths=[1.6, 1.4, 1.4, 3.2],
            align_center=[1, 2],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "설계 의도대로 부정과 중립 판정은 그대로 유지되고 긍정만 개선되었습니다. "
            "기존에 올바르게 판정하던 문장이 잘못되는 경우는 한 건도 발생하지 않았습니다. "
            "개선된 두 문장은 모두 반어적 표현 사례였습니다."
        )
    )
    story.append(
        make_table(
            ["리뷰", "단독", "결합"],
            [
                ["마지막 재회 장면에서는 눈물을 참기가 어려웠습니다.", "부정", "긍정 4.76"],
                ["음향과 촬영이 만들어내는 불안한 분위기가 대단했습니다.", "부정", "긍정 4.47"],
            ],
            widths=[4.8, 1.0, 1.4],
            align_center=[1, 2],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "보조 모델은 반어 문장 4건을 모두 정확히 판정했지만 개선은 2건에 그쳤습니다. "
            "규칙 B가 주 모델의 중립 판정을 건드리지 않기 때문입니다. "
            "주 모델이 중립으로 판정한 반어 문장 2건은 보조 모델의 판단이 적용되지 않고 "
            "그대로 남습니다. 이는 중립 판정을 보호하기 위해 감수한 제약이며, "
            "규칙 A를 적용해도 결과는 같았습니다."
        )
    )
    story.append(
        body(
            "이번 수치는 동일한 60건을 사용한 내부 비교 결과입니다. 리뷰 작성과 의도 라벨 부여를 "
            "한 사람이 수행했고, 같은 자료로 후보 모델과 결합 규칙을 비교했으므로 절대적인 "
            "일반화 성능보다는 모델과 규칙 사이의 상대적인 개선 정도로 해석해야 합니다."
        )
    )

    story.append(PageBreak())
    story.append(heading("5.5 평점 산출 방식", 2))
    story.append(
        body(
            "과제에서 평점은 리뷰 감성 분석 점수의 평균으로 정의되어 있으나 점수의 계산 방법은 "
            "명시되어 있지 않았습니다. 본 서비스에서는 확률 분포를 그대로 활용하는 가중 평균 방식을 "
            "택했습니다."
        )
    )
    story.append(
        code_block(
            "리뷰 점수 = 부정확률 × 1 + 중립확률 × 3 + 긍정확률 × 5\n"
            "영화 평점 = 해당 영화 리뷰들의 점수 평균"
        )
    )
    story.append(
        body(
            "확률의 합이 1이므로 결과는 항상 1점에서 5점 사이에 놓입니다. "
            "라벨만으로 1점, 3점, 5점을 부여하는 방식과 비교하면 확률 정보를 버리지 않으므로 "
            "같은 중립 판정 안에서도 긍정에 가까운 경우와 부정에 가까운 경우가 구분됩니다. "
            "실제로 중립으로 판정된 리뷰 중에는 3.08점인 것과 2.08점인 것이 함께 존재합니다."
        )
    )
    story.append(
        body(
            "비교 기준으로 TMDB 평점을 함께 표시합니다. 전 세계 사용자의 투표 결과이므로 "
            "감성 분석 평점의 타당성을 가늠하는 참고 자료가 됩니다."
        )
    )

    story.append(heading("5.6 모델 경량화", 2))
    story.append(
        body(
            "배포 환경에서 PyTorch 없이 동작하도록 두 모델 모두 ONNX 형식으로 변환하고 "
            "동적 양자화를 적용했습니다. 추론에는 ONNX Runtime 만 사용하므로 의존성이 크게 줄어듭니다."
        )
    )
    story.append(
        make_table(
            ["모델", "원본", "양자화 후", "절감률", "양자화 전후 검증"],
            [
                [
                    "KR-ELECTRA 3-class",
                    "420.85 MB",
                    "352.07 MB",
                    "16.3퍼센트",
                    "기존 검증 결과 유지",
                ],
                [
                    "KoELECTRA-small 2-class",
                    "54.12 MB",
                    "14.02 MB",
                    "74.1퍼센트",
                    "반어 문장 4 / 4 유지",
                ],
                ["합계", "474.97 MB", "366.09 MB", "22.9퍼센트", "-"],
            ],
            widths=[2.2, 1.2, 1.2, 1.1, 2.1],
            align_center=[1, 2, 3, 4],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "두 모델의 절감률 차이가 큽니다. 미션 16에서는 PyTorch 의 dynamo 기반 변환기를 "
            "사용했는데, 그 결과물은 일부 연산만 양자화 대상이 되어 절감 폭이 제한되었습니다. "
            "이번에 추가한 보조 모델은 기존 방식인 torch.onnx.export 를 사용했고 "
            "74.1퍼센트를 절감했습니다. 변환 방식의 선택이 양자화 효율에 직접 영향을 준다는 "
            "것을 확인했습니다."
        )
    )
    story.append(
        body(
            "보조 모델을 추가하면서 늘어난 용량은 14.02 MB 로 전체의 4퍼센트에 못 미칩니다. "
            "정확도 3.3퍼센트포인트 개선에 비하면 비용이 작다고 판단했습니다. "
            "위 표의 용량은 1 MB 를 2의 20제곱 바이트로 계산한 값입니다."
        )
    )
    story.append(
        body(
            "실제 배포에 사용한 컨테이너 이미지는 압축 상태로 491 MB 입니다. "
            "python:3.12-slim 기반 이미지와 서비스 의존성에 양자화 모델 366.09 MB 가 더해진 결과입니다. "
            "PyTorch 를 포함했다면 이미지가 두 배 이상 커졌을 가능성이 있으므로, ONNX Runtime 만으로 "
            "추론하도록 구성한 판단이 배포 단계에서도 유효했습니다."
        )
    )

    return story


# ---------------------------------------------------------------------------
# 6. 서비스 동작
# ---------------------------------------------------------------------------

def section_demo() -> list:
    story = [heading("6. 서비스 동작")]

    story.append(
        body(
            "시드 자료가 삽입된 상태에서 영화 등록과 리뷰 작성을 순서대로 수행한 화면입니다. "
            "등록 전에 해당 영화가 없다는 것을 먼저 확인하고, 등록 후 목록에 반영되는 것까지 "
            "이어서 담았습니다. 각 절의 화면은 절 아래에 순서대로 배치했으며, "
            "그림이 여러 쪽에 걸치는 경우 설명 문단 바로 다음 그림부터 순서대로 이어집니다."
        )
    )

    story.append(heading("6.1 영화 목록", 2))
    story.append(
        body(
            "포스터를 격자로 표시하고 제목 검색, 장르 필터, 정렬을 제공합니다. "
            "감성 평점순으로 정렬하면 리뷰가 등록된 영화가 위쪽에 배치됩니다. "
            "목록은 20편 단위로 나누어 불러오며 더 보기를 눌러 추가로 확인할 수 있습니다(그림 13)."
        )
    )
    story.extend(figure("screen_movies.png", "영화 목록 화면, 감성 평점순 정렬", 120 * mm))

    story.append(PageBreak())
    story.append(heading("6.2 영화 상세와 리뷰", 2))
    story.append(
        body(
            "포스터를 누르면 상세 정보와 해당 영화의 리뷰가 표시됩니다. "
            "TMDB 평점과 감성 분석 평점을 나란히 배치하고 감성별 리뷰 분포를 함께 제공합니다(그림 14)."
        )
    )
    story.extend(figure("screen_detail.png", "인터스텔라 상세 정보와 리뷰 목록", 150 * mm))

    story.append(PageBreak())
    story.append(heading("6.3 영화 등록", 2))
    story.append(
        body(
            "등록 기능은 대표로 한 편을 시연했습니다. 목록에 표시된 300편은 서비스 기동 시 "
            "동일한 저장 경로를 통해 삽입된 시드 자료입니다. "
            "등록에 앞서 대상 영화가 목록에 없다는 것을 먼저 확인했습니다(그림 15)."
        )
    )
    story.extend(figure("screen_search_empty.png", "등록 전 검색 결과가 없는 상태", 95 * mm))
    story.append(
        body(
            "TMDB 에서 제목으로 검색하고 결과를 선택하면 제목, 개봉일, 감독, 장르, 포스터 주소가 "
            "자동으로 채워집니다. 검색 없이 직접 입력할 수도 있습니다."
        )
    )
    story.extend(figure("screen_add_1.png", "영화 추가 화면", 105 * mm))
    story.extend(
        figure("screen_add_2.png", "TMDB 검색 결과", 140 * mm)
    )
    story.append(PageBreak())
    story.append(
        body(
            "검색 결과에서 선택하면 입력 항목이 자동으로 채워집니다. 필요하면 값을 수정한 뒤 "
            "등록합니다."
        )
    )
    story.extend(figure("screen_add_result.png", "영화 등록 성공", 130 * mm))
    story.extend(
        figure("screen_movies_after.png", "등록한 영화가 목록에 반영된 상태", 120 * mm)
    )

    story.append(PageBreak())
    story.append(heading("6.4 리뷰 작성과 감성 분석", 2))
    story.append(
        body(
            "영화를 선택하고 닉네임과 리뷰 내용을 입력합니다. 감성 분석 모델이 한국어 전용이므로 "
            "한국어로 작성된 리뷰만 등록할 수 있습니다(그림 20)."
        )
    )
    story.extend(figure("screen_review_form.png", "리뷰 작성 화면", 110 * mm))
    story.append(
        body(
            "등록과 동시에 감성 분석이 수행되어 판정, 확률 분포, 점수가 표시됩니다."
        )
    )
    story.extend(figure("screen_review_result.png", "리뷰 등록 후 감성 분석 결과", 130 * mm))
    story.extend(figure("screen_detail_new.png", "등록한 리뷰가 반영된 영화 상세 화면", 150 * mm))

    story.append(
        body(
            "등록 직후 화면은 등록 응답에 담긴 점수를 그대로 표시하고, 상세 화면과 목록은 "
            "평점 조회 결과를 사용합니다. 두 경로의 반올림 처리가 달라 소수 둘째 자리에서 "
            "값이 다르게 보일 수 있습니다."
        )
    )
    story.append(
        body(
            "등록과 리뷰 작성을 마친 뒤의 목록 화면입니다. 각 영화 카드에는 감성 분석 평점과 "
            "리뷰 개수가 함께 표시됩니다. 시드로 삽입한 다섯 편은 각각 12건의 리뷰를 보유하고 "
            "있으며, 화면에는 그중 일부가 나타나 있습니다. 방금 등록한 영화는 리뷰 1건으로 "
            "표시됩니다."
        )
    )
    story.extend(
        figure(
            "screen_movies_counts.png",
            "등록 후 목록에 표시된 영화별 평점과 리뷰 개수",
            135 * mm,
        )
    )

    story.append(PageBreak())
    story.append(heading("6.5 최근 리뷰", 2))
    story.append(
        body(
            "전체 리뷰를 최신순으로 표시합니다. 영화 번호, 영화 제목, 등록일, 리뷰 내용, "
            "감성 판정, 점수를 함께 제공합니다(그림 24)."
        )
    )
    story.extend(figure("screen_recent.png", "최근 리뷰 화면", 130 * mm))

    story.append(CondPageBreak(55 * mm))
    story.append(heading("6.6 문서를 통한 동작 확인", 2))
    story.append(
        body(
            "자동 생성 문서에서도 각 엔드포인트를 직접 실행할 수 있습니다. "
            "리뷰 등록 요청과 그 응답은 다음과 같습니다."
        )
    )
    story.extend(figure("docs_review_post.png", "리뷰 등록 요청", 105 * mm))
    story.extend(figure("docs_review_result.png", "리뷰 등록 응답", 130 * mm))
    story.append(
        body(
            "응답을 보면 긍정 확률 0.5316, 중립 확률 0.468 로 두 값이 근접해 있고 점수는 "
            "4.06 으로 산출되었습니다. 앞서 확인한 시드 리뷰들이 대부분 한쪽으로 확신에 찬 "
            "분포를 보인 것과 달리, 장단점을 함께 언급한 문장에서는 확률이 갈리며 점수도 "
            "중간값에 가깝게 나타납니다."
        )
    )
    story.extend(figure("docs_review_responses.png", "리뷰 등록 엔드포인트의 응답 코드 명세", 140 * mm))

    return story


# ---------------------------------------------------------------------------
# 7. 개발 과정의 문제와 해결
# ---------------------------------------------------------------------------

def section_troubleshooting() -> list:
    story = [heading("7. 개발 과정의 문제와 해결")]

    story.append(heading("7.1 리뷰 자료 확보", 2))
    story.append(
        body(
            "초기에는 TMDB 가 제공하는 리뷰를 활용할 계획이었습니다. 실제로 사용할 수 있는지 "
            "확인하기 위해 영화 10편의 리뷰를 조사했습니다."
        )
    )
    story.append(
        make_table(
            ["조사 항목", "결과"],
            [
                ["조사 편수", "10편"],
                ["리뷰 총합", "157건"],
                ["편당 평균", "15.7건"],
                ["한국어 리뷰", "157건 중 1건"],
                ["영화별 평균 리뷰 길이", "657~3,232자"],
                ["한국 영화 리뷰 수", "부산행 4건, 올드보이 4건, 곡성 5건"],
            ],
            widths=[2.0, 5.6],
        )
    )
    story.append(spacer(2 * mm))
    story.append(
        body(
            "수량은 충분했으나 대부분 영어 장문 평론이었습니다. 한국어 전용 모델에 입력할 수 없고, "
            "번역을 거치면 번역 품질이 감성 판정에 영향을 주어 모델 성능을 따로 평가할 수 없게 됩니다. "
            "또한 한국 영화일수록 리뷰가 적어 영화당 10건 이상이라는 요건을 채우려면 "
            "할리우드 대작 위주로 목록을 구성해야 했습니다."
        )
    )
    story.append(
        body(
            "네이버나 왓챠 등의 리뷰를 수집하는 방안은 저작권과 이용약관 문제가 있어 제외했습니다. "
            "결과적으로 리뷰 60건을 직접 작성했고, 각 리뷰에 의도한 감성을 함께 기록해 "
            "모델 검증 자료로도 활용했습니다."
        )
    )

    story.append(heading("7.2 양자화 과정의 경로 문제", 2))
    story.append(
        body(
            "보조 모델을 양자화하는 과정에서 형상 추론 단계의 결과 파일을 찾을 수 없다는 오류가 "
            "발생했습니다. 원인은 작업 경로에 포함된 대괄호와 한글이었습니다."
        )
    )
    story.append(
        body(
            "ONNX 변환 자체는 파이썬이 파일을 기록하므로 문제가 없었으나, 형상 추론은 C++ 로 "
            "구현되어 있어 해당 경로를 처리하지 못했습니다. 임시 폴더에서 양자화를 수행하고 "
            "결과 파일만 원래 위치로 옮기는 방식으로 해결했습니다."
        )
    )

    story.append(heading("7.3 응답 항목 이름 불일치", 2))
    story.append(
        body(
            "리뷰 등록 후 화면에 감성 판정이 미분석으로, 점수가 0점으로 표시되는 문제가 있었습니다. "
            "확률 막대는 정상이었습니다. 감성 분석 전용 응답은 label 과 score 를 사용하고 "
            "리뷰 등록 응답은 sentiment_label 과 sentiment_score 를 사용하는데, "
            "화면 코드가 전자만 참조하고 있었습니다. 확률 항목은 두 응답의 이름이 같아 "
            "문제가 드러나지 않았습니다. 두 이름을 모두 처리하도록 수정했습니다."
        )
    )

    story.append(heading("7.4 상세 정보의 배치", 2))
    story.append(
        body(
            "영화 목록에서 상세 보기를 눌러도 화면에 변화가 없어 보이는 문제가 있었습니다. "
            "상세 정보를 목록 아래에 배치했기 때문에, 영화가 많을 때는 한참 스크롤해야 "
            "확인할 수 있었습니다. 검색으로 목록을 줄이면 정상으로 보였던 것이 원인 파악을 "
            "늦추었습니다. 상세 정보를 목록 위로 옮겨 해결했습니다."
        )
    )

    story.append(heading("7.5 최근 리뷰의 편중", 2))
    story.append(
        body(
            "시드 리뷰 60건을 한 번에 삽입하면서 등록 시각이 모두 같아졌고, 그 결과 최근 리뷰 "
            "화면이 마지막에 삽입된 영화의 리뷰로만 채워졌습니다. 영화별로 번갈아 배치하고 "
            "12시간 간격으로 시각을 부여해 여러 영화가 고르게 나타나도록 했습니다."
        )
    )

    story.append(heading("7.6 영화 목록의 분할 조회", 2))
    story.append(
        body(
            "초기에는 영화 목록 전체를 한 번에 내려주었습니다. 영화 편수를 300편으로 늘리면서 "
            "응답 크기와 화면 렌더링 부담이 커졌고, 사용자가 원하는 만큼만 확인할 수 있도록 "
            "분할 조회를 도입했습니다. 응답에 전체 개수와 다음 자료의 존재 여부를 포함해 "
            "더 보기 버튼의 표시 여부를 판단합니다."
        )
    )

    story.append(heading("7.7 컨테이너에서 모델을 찾지 못한 문제", 2))
    story.append(
        body(
            "비밀 정보가 이미지에 포함되지 않도록 .dockerignore 로 .env 를 제외했는데, "
            "그 결과 모델 경로와 파일명도 전달되지 않아 설정 기본값이 적용되었습니다. "
            "기본값이 예시용 이름이어서 컨테이너가 실제 모델 파일을 찾지 못했고 감성 분석 기능이 "
            "동작하지 않았습니다."
        )
    )
    story.append(
        body(
            "비밀 정보와 일반 설정을 한 파일에 함께 둔 것이 원인이었습니다. 모델 경로와 파일명은 "
            "공개되어도 무방하므로 config.py 의 기본값을 실제 파일명으로 바꾸어 해결했습니다. "
            "배포 시 별도로 주입할 값은 TMDB_API_KEY 와 ADMIN_KEY 두 개로 줄어 관리도 단순해졌습니다."
        )
    )

    story.append(heading("7.8 새 프로젝트의 결제 계정 미연결", 2))
    story.append(
        body(
            "Google Cloud 에서 새 프로젝트를 만든 뒤 필요한 서비스를 활성화하려 했으나 결제 계정을 "
            "찾을 수 없다는 오류가 발생했습니다. 프로젝트 생성과 결제 계정 연결은 별도 절차이므로, "
            "콘솔에서 기존 결제 계정을 새 프로젝트에 연결한 뒤 정상적으로 진행했습니다."
        )
    )

    story.append(heading("7.9 컨테이너 포트 충돌", 2))
    story.append(
        body(
            "이미지를 다시 빌드해 로컬에서 실행할 때 포트가 이미 할당되어 있다는 오류가 발생했습니다. "
            "이전 컨테이너가 완전히 종료되지 않은 상태가 원인이었습니다. 실행 중인 컨테이너를 확인해 "
            "중지하고 제거한 뒤 새 컨테이너를 실행해 해결했습니다."
        )
    )

    return story


# ---------------------------------------------------------------------------
# 8. 향후 개선 방향
# ---------------------------------------------------------------------------

def section_future() -> list:
    story = [heading("8. 향후 개선 방향")]

    story.append(heading("8.1 중립 판정 개선", 2))
    story.append(
        body(
            "두 모델의 결합으로 긍정 판정은 개선되었으나 중립은 81.2퍼센트로 여전히 가장 낮습니다. "
            "남은 오분류 6건은 반어 문장 2건, 중립 경계 3건, 명백한 오류 1건으로 구성되며, "
            "여섯 건 모두 중립 판정이 개입된 사례입니다. "
            "중립 경계 3건은 사람이 보아도 판단이 갈릴 수 있어 정답 자체의 모호함이 일부 "
            "포함되어 있습니다. 반면 반어 문장 2건은 보조 모델이 올바르게 판정했음에도 "
            "결합 규칙상 반영되지 않은 사례이고, 나머지 1건은 정답이 분명한데도 놓친 오류입니다."
        )
    )
    story.append(
        body(
            "개선하려면 경계에 놓인 3-class 학습 자료가 필요합니다. 공개 자료로는 확보가 어려워 "
            "직접 구축해야 하며, 이 경우 라벨 기준을 사전에 정의하고 여러 사람이 교차 검토하는 "
            "절차가 필요합니다."
        )
    )

    story.append(heading("8.2 로그인 기능", 2))
    story.append(
        body(
            "현재는 리뷰 작성 시 닉네임을 입력받고 있으며 작성자 확인은 하지 않습니다. "
            "로그인을 도입하면 본인이 작성한 리뷰만 삭제할 수 있게 되고, 영화 등록 권한도 "
            "구분할 수 있습니다. 이를 대비해 users 테이블과 리뷰의 작성자 참조를 미리 정의해 "
            "두었으므로 스키마 변경 없이 기능을 추가할 수 있습니다."
        )
    )

    story.append(heading("8.3 데이터 영속성 확보", 2))
    story.append(
        body(
            "현재 구성에서는 Cloud Run 인스턴스가 종료되면 로컬 SQLite 자료가 사라집니다. "
            "기동 시 시드를 다시 삽입하도록 구성해 평가자가 항상 영화 300편과 리뷰 60건이 있는 "
            "동일한 화면을 확인할 수 있게 했지만, 사용자가 추가로 등록한 영화와 리뷰는 유지되지 않습니다."
        )
    )
    story.append(
        body(
            "SQLAlchemy 를 사용하고 있으므로 DATABASE_URL 연결 문자열과 데이터베이스별 설정을 바꾸면 "
            "외부 관리형 데이터베이스로 전환할 수 있습니다. 향후 PostgreSQL 등의 관리형 데이터베이스를 "
            "연결해 사용자 자료를 보존하는 것이 필요합니다. 또한 최소 인스턴스를 1개로 설정하면 약 20초의 "
            "콜드 스타트를 줄일 수 있으나 상시 과금이 발생하므로, 현재 평가용 서비스에서는 비용을 줄이는 "
            "대신 첫 접속 지연을 감수했습니다."
        )
    )

    story.append(heading("8.4 그 밖의 개선 사항", 2))
    story.extend(
        bullets(
            [
                "영화 상세 화면에 TMDB 의 줄거리와 출연진 정보를 추가로 조회해 표시할 수 있습니다.",
                "감성 점수를 구간으로 나누어 매우 긍정에서 매우 부정까지 다섯 단계로 표시하면 "
                "판정의 정도를 더 세밀하게 전달할 수 있습니다.",
                "감성 분석 평점과 TMDB 평점의 상관관계를 분석하면 모델 판정의 타당성을 "
                "정량적으로 평가할 수 있습니다.",
            ]
        )
    )

    return story


# ---------------------------------------------------------------------------
# 표지
# ---------------------------------------------------------------------------

def cover() -> list:
    return [
        Spacer(1, 52 * mm),
        Paragraph(TITLE, STYLES["title"]),
        Paragraph(SUBTITLE, STYLES["subtitle"]),
        Spacer(1, 22 * mm),
        Paragraph(AUTHOR, STYLES["subtitle"]),
        Paragraph(date.today().strftime("%Y년 %m월 %d일"), STYLES["subtitle"]),
        Spacer(1, 14 * mm),
        Paragraph(f"서비스 주소&nbsp;&nbsp;{FRONTEND_URL}", STYLES["cover_link"]),
        Paragraph(f"소스 저장소&nbsp;&nbsp;{SOURCE_REPOSITORY_URL}", STYLES["cover_link"]),
        PageBreak(),
    ]


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    _figure_counter["value"] = 0
    validate_assets()

    story: list = []
    story.extend(cover())
    story.extend(table_of_contents())
    story.extend(section_overview())
    story.append(PageBreak())
    story.extend(section_architecture())
    story.append(PageBreak())
    story.extend(section_database())
    story.append(PageBreak())
    story.extend(section_api())
    story.append(PageBreak())
    story.extend(section_model())
    story.append(PageBreak())
    story.extend(section_demo())
    story.append(PageBreak())
    story.extend(section_troubleshooting())
    story.append(PageBreak())
    story.extend(section_future())

    document = ReportDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=TITLE,
        author=AUTHOR,
    )
    document.multiBuild(story, onFirstPage=draw_page, onLaterPages=draw_page)

    size = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f"보고서를 생성했습니다: {OUTPUT_PATH}")
    print(f"용량 {size:.2f} MB")


if __name__ == "__main__":
    main()