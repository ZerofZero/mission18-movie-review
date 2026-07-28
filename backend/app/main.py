"""FastAPI 애플리케이션 진입점.

라우터를 등록하고, 기동 시 데이터베이스 준비와 감성 분석 모델 적재를 수행합니다.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import settings
from app.database import create_tables, get_db
from app.routers import movies, reviews, tmdb
from app.sentiment.analyzer import analyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 문서 구성
# ---------------------------------------------------------------------------

TAGS_METADATA = [
    {
        "name": "영화",
        "description": "영화 등록, 조회, 삭제와 영화별 리뷰 및 평점 조회를 제공합니다.",
    },
    {
        "name": "리뷰",
        "description": (
            "리뷰 등록, 조회, 삭제를 제공합니다. "
            "등록 시 감성 분석이 자동으로 수행되어 결과가 함께 저장됩니다."
        ),
    },
    {
        "name": "감성 분석",
        "description": (
            "저장 없이 문장의 감성만 분석합니다. "
            "KR-ELECTRA 기반 3-class 모델과 NSMC 로 학습한 2-class 모델을 결합해 판정합니다."
        ),
    },
    {
        "name": "TMDB 연동",
        "description": (
            "영화 등록 시 입력 항목을 자동으로 채우기 위해 TMDB 를 조회합니다. "
            "인증 정보는 서버에만 보관합니다."
        ),
    },
    {
        "name": "기타",
        "description": "서버 상태 확인 등 부가 기능을 제공합니다.",
    },
]

DESCRIPTION = """
영화 정보와 사용자 리뷰를 관리하고, 리뷰의 감성을 분석해 평점을 산출하는 API 입니다.

### 주요 기능

- 영화 등록, 조회, 삭제
- TMDB 연동을 통한 영화 정보 자동 입력
- 리뷰 등록, 조회, 삭제
- 리뷰 감성 분석 및 평점 산출

### 감성 분석 모델

두 개의 모델을 결합해 판정합니다.

주 모델은 미션 13에서 학습한 KR-ELECTRA 기반 3-class 분류 모델을
미션 16에서 ONNX 로 변환하고 동적 양자화를 적용한 것으로, 중립 판정에 강점이 있습니다.
보조 모델은 NSMC 로 학습한 KoELECTRA-small 기반 2-class 분류 모델로,
영화 리뷰의 반어적 표현에서 긍정과 부정을 구분하는 데 강점이 있습니다.

주 모델이 중립으로 판정한 문장은 그대로 두고, 긍정이나 부정으로 판정한 문장만
중립 확률을 유지한 채 나머지 확률을 보조 모델의 비율로 다시 배분합니다.
두 모델 모두 PyTorch 없이 ONNX Runtime 으로 추론하며 합산 용량은 366MB 입니다.

### 평점 산출 방식

각 리뷰의 감성 확률 분포에 부정 1점, 중립 3점, 긍정 5점의 가중치를 적용해
가중 평균을 구한 뒤, 영화별로 그 값을 평균합니다. 결과는 5점 만점입니다.

### 관리자 키

영화와 리뷰 삭제에는 X-Admin-Key 헤더가 필요합니다.
우측 상단의 Authorize 를 눌러 키를 입력한 뒤 사용합니다.
"""


# ---------------------------------------------------------------------------
# 생애 주기
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 기동과 종료 시 수행할 작업을 정의합니다."""
    logger.info("애플리케이션을 시작합니다.")

    # 1. 테이블 생성
    create_tables()
    logger.info("데이터베이스 테이블을 준비했습니다.")

    # 2. 감성 분석 모델 적재
    if analyzer.load():
        logger.info("감성 분석 모델을 적재했습니다.")
    else:
        logger.warning(
            "감성 분석 모델을 적재하지 못했습니다. 리뷰 관련 기능이 제한됩니다."
        )

    # 3. 시드 데이터 삽입
    if settings.SEED_ON_STARTUP:
        try:
            from app.seed import seed_database

            seed_database()
        except (ImportError, AttributeError):
            logger.info("시드 모듈이 아직 준비되지 않아 건너뜁니다.")
        except Exception:
            logger.exception("시드 데이터 삽입 중 오류가 발생했습니다.")

    yield

    logger.info("애플리케이션을 종료합니다.")


# ---------------------------------------------------------------------------
# 애플리케이션
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
    contact={"name": "5팀 황지우"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(movies.router)
app.include_router(reviews.router)
app.include_router(reviews.sentiment_router)
app.include_router(tmdb.router)


# ---------------------------------------------------------------------------
# 기타 엔드포인트
# ---------------------------------------------------------------------------

@app.get(
    "/",
    response_model=schemas.MessageResponse,
    tags=["기타"],
    summary="서비스 안내",
    description="서비스 이름과 문서 주소를 안내합니다.",
)
def read_root():
    """서비스 기본 정보를 반환합니다."""
    return schemas.MessageResponse(
        detail=f"{settings.APP_NAME} 가 실행 중입니다. 문서는 /docs 에서 확인할 수 있습니다."
    )


@app.get(
    "/health",
    response_model=schemas.HealthResponse,
    tags=["기타"],
    summary="서버 상태 확인",
    description=(
        "서버 상태와 함께 감성 분석 모델의 적재 여부, TMDB 설정 여부, "
        "등록된 영화와 리뷰 개수를 반환합니다."
    ),
)
def read_health(db: Session = Depends(get_db)):
    """서버 상태를 반환합니다."""
    return schemas.HealthResponse(
        status="ok",
        app_version=settings.APP_VERSION,
        model_loaded=analyzer.is_loaded,
        binary_model_loaded=analyzer.binary_loaded,
        tmdb_configured=settings.tmdb_configured,
        movie_count=crud.count_movies(db),
        review_count=crud.count_reviews(db),
    )