"""FastAPI 공통 의존성.

여러 라우터에서 함께 사용하는 의존성을 정의합니다.
"""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

# 자동 생성 문서에서 자물쇠 아이콘과 인증 입력란을 표시하기 위한 정의입니다.
admin_key_header = APIKeyHeader(
    name="X-Admin-Key",
    scheme_name="AdminKey",
    description="삭제 요청에 필요한 관리자 키입니다.",
    auto_error=False,
)


def verify_admin_key(api_key: str | None = Security(admin_key_header)) -> str:
    """관리자 키를 검증합니다.

    영화와 리뷰 삭제처럼 되돌릴 수 없는 요청에만 적용합니다.
    """
    if not settings.ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="관리자 키가 서버에 설정되어 있지 않습니다.",
        )

    if api_key != settings.ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 키가 올바르지 않습니다.",
        )

    return api_key