"""리뷰 및 감성 분석 관련 API 라우터."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.dependencies import verify_admin_key
from app.sentiment.analyzer import analyzer, is_korean, korean_ratio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["리뷰"])
sentiment_router = APIRouter(prefix="/sentiment", tags=["감성 분석"])


# ---------------------------------------------------------------------------
# 내부 도우미
# ---------------------------------------------------------------------------

def _ensure_model_loaded() -> None:
    """감성 분석 모델이 준비되어 있는지 확인합니다."""
    if not analyzer.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="감성 분석 모델이 준비되지 않았습니다. 잠시 후 다시 시도해주세요.",
        )


def _ensure_korean(text: str) -> None:
    """입력이 한국어로 작성되었는지 확인합니다."""
    if not is_korean(text):
        ratio = round(korean_ratio(text) * 100, 1)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"리뷰는 한국어로 작성해주세요. 현재 한글 비율은 {ratio}퍼센트입니다."
            ),
        )


# ---------------------------------------------------------------------------
# 리뷰
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[schemas.ReviewRead],
    summary="전체 리뷰 조회",
    description=(
        "등록된 모든 리뷰를 최신순으로 조회합니다. "
        "기본값은 최근 10건이며 limit 으로 조정할 수 있습니다. "
        "각 리뷰에는 영화 번호와 제목, 감성 분석 결과가 함께 반환됩니다."
    ),
)
def read_reviews(
    limit: int = Query(
        default=10,
        ge=1,
        le=200,
        description="반환할 최대 리뷰 개수입니다.",
    ),
    db: Session = Depends(get_db),
):
    """최근 리뷰 목록을 반환합니다."""
    return crud.list_recent_reviews(db, limit=limit)


@router.get(
    "/{review_id}",
    response_model=schemas.ReviewRead,
    summary="리뷰 상세 조회",
    description="리뷰 번호로 한 건의 리뷰를 조회합니다.",
    responses={404: {"description": "해당 번호의 리뷰가 없습니다."}},
)
def read_review(review_id: int, db: Session = Depends(get_db)):
    """번호로 리뷰 한 건을 반환합니다."""
    review = crud.get_review(db, review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"리뷰를 찾을 수 없습니다: {review_id}",
        )
    return review


@router.post(
    "",
    response_model=schemas.ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="리뷰 등록",
    description=(
        "리뷰를 등록합니다. 등록과 동시에 감성 분석이 수행되어 결과가 함께 저장됩니다. "
        "감성 분석 모델이 한국어 전용이므로 한국어로 작성된 리뷰만 등록할 수 있습니다."
    ),
    responses={
        400: {"description": "리뷰가 한국어로 작성되지 않았습니다."},
        404: {"description": "대상 영화를 찾을 수 없습니다."},
        503: {"description": "감성 분석 모델이 준비되지 않았습니다."},
    },
)
def create_review(
    review_in: schemas.ReviewCreate,
    db: Session = Depends(get_db),
):
    """리뷰를 등록하고 감성 분석 결과와 함께 반환합니다."""
    _ensure_korean(review_in.content)
    _ensure_model_loaded()

    try:
        sentiment = analyzer.predict(review_in.content)
    except Exception:
        # 분석에 실패하더라도 리뷰 자체는 저장합니다.
        logger.exception("감성 분석에 실패했습니다. 리뷰는 분석 결과 없이 저장됩니다.")
        sentiment = None

    try:
        return crud.create_review(db, review_in, sentiment)
    except crud.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="리뷰 삭제",
    description=(
        "리뷰를 삭제합니다. "
        "요청 시 X-Admin-Key 헤더에 관리자 키를 포함해야 합니다."
    ),
    responses={
        204: {"description": "삭제되었습니다."},
        403: {"description": "관리자 키가 올바르지 않습니다."},
        404: {"description": "해당 번호의 리뷰가 없습니다."},
    },
    dependencies=[Depends(verify_admin_key)],
)
def delete_review(review_id: int, db: Session = Depends(get_db)):
    """리뷰를 삭제합니다."""
    if not crud.delete_review(db, review_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"리뷰를 찾을 수 없습니다: {review_id}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 감성 분석
# ---------------------------------------------------------------------------

@sentiment_router.post(
    "/analyze",
    response_model=schemas.SentimentAnalyzeResponse,
    summary="문장 감성 분석",
    description=(
        "문장 하나의 감성을 분석합니다. 결과는 저장되지 않습니다. "
        "미션 16에서 변환한 KR-ELECTRA 기반 3-class 분류 모델을 "
        "ONNX Runtime 으로 추론합니다. "
        "점수는 부정 1점, 중립 3점, 긍정 5점의 가중치를 확률로 가중 평균한 값입니다."
    ),
    responses={
        400: {"description": "입력이 한국어로 작성되지 않았습니다."},
        503: {"description": "감성 분석 모델이 준비되지 않았습니다."},
    },
)
def analyze_sentiment(payload: schemas.SentimentAnalyzeRequest):
    """입력 문장의 감성 분석 결과를 반환합니다."""
    _ensure_korean(payload.text)
    _ensure_model_loaded()

    result = analyzer.predict(payload.text)
    return schemas.SentimentAnalyzeResponse(text=payload.text, result=result)