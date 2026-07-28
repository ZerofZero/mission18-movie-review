"""애플리케이션 설정 모듈.

.env 파일에 정의된 환경 변수를 읽어 애플리케이션 전역에서 사용할 수 있는
설정 객체로 제공합니다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend 디렉터리 경로입니다. 이 파일은 backend/app/config.py 에 위치합니다.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """환경 변수 기반 설정."""

    # protected_namespaces 를 비워 MODEL_ 로 시작하는 필드명을 허용합니다.
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # -----------------------------------------------------------------------
    # 애플리케이션
    # -----------------------------------------------------------------------
    APP_NAME: str = "Movie Review Sentiment API"
    APP_VERSION: str = "1.0.0"

    # -----------------------------------------------------------------------
    # 데이터베이스
    # -----------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./movie_review.db"
    SEED_ON_STARTUP: bool = True

    # -----------------------------------------------------------------------
    # TMDB API
    # -----------------------------------------------------------------------
    TMDB_ACCESS_TOKEN: str = ""
    TMDB_API_KEY: str = ""
    TMDB_LANGUAGE: str = "ko-KR"
    TMDB_IMAGE_BASE_URL: str = "https://image.tmdb.org/t/p/w500"
    TMDB_BASE_URL: str = "https://api.themoviedb.org/3"

    # -----------------------------------------------------------------------
    # 관리자 키
    # -----------------------------------------------------------------------
    ADMIN_KEY: str = ""

# -----------------------------------------------------------------------
    # 감성 분석 모델
    #
    # 경로와 파일명은 비밀 정보가 아니므로 기본값으로 둡니다.
    # 배포 환경에서 따로 주입할 필요가 없습니다.
    # -----------------------------------------------------------------------
    MODEL_DIR: str = "app/sentiment/model"
    MODEL_FILE: str = "mission_16_kr_electra_quantized.onnx"
    MODEL_MAX_LENGTH: int = 128

    # 긍정과 부정 구분을 담당하는 보조 모델입니다.
    # 비워 두면 3-class 모델만 사용합니다.
    BINARY_MODEL_DIR: str = "app/sentiment/model_binary"
    BINARY_MODEL_FILE: str = "nsmc_koelectra_small_quantized.onnx"
    BINARY_NEGATIVE_INDEX: int = 0

    KOREAN_RATIO_THRESHOLD: float = 0.3

    # -----------------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------------
    CORS_ORIGINS: str = "*"

    # -----------------------------------------------------------------------
    # 파생 값
    # -----------------------------------------------------------------------
    @property
    def model_dir_path(self) -> Path:
        """모델 디렉터리의 절대 경로."""
        return BASE_DIR / self.MODEL_DIR

    @property
    def model_file_path(self) -> Path:
        """ONNX 모델 파일의 절대 경로."""
        return self.model_dir_path / self.MODEL_FILE

    @property
    def binary_model_dir_path(self) -> Path | None:
        """보조 모델 디렉터리의 절대 경로."""
        if not self.BINARY_MODEL_DIR:
            return None
        return BASE_DIR / self.BINARY_MODEL_DIR

    @property
    def binary_model_file_path(self) -> Path | None:
        """보조 모델 파일의 절대 경로."""
        directory = self.binary_model_dir_path
        if directory is None or not self.BINARY_MODEL_FILE:
            return None
        return directory / self.BINARY_MODEL_FILE

    @property
    def cors_origin_list(self) -> list[str]:
        """쉼표로 구분된 CORS 출처를 목록으로 변환합니다."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def tmdb_headers(self) -> dict[str, str]:
        """TMDB 요청에 사용할 헤더.

        v4 Access Token 이 설정된 경우 Bearer 인증 헤더를 반환합니다.
        """
        if self.TMDB_ACCESS_TOKEN:
            return {"Authorization": f"Bearer {self.TMDB_ACCESS_TOKEN}"}
        return {}

    @property
    def tmdb_auth_params(self) -> dict[str, str]:
        """TMDB 요청에 사용할 쿼리 파라미터.

        v4 Access Token 이 없고 v3 API Key 만 있는 경우에 사용됩니다.
        """
        if not self.TMDB_ACCESS_TOKEN and self.TMDB_API_KEY:
            return {"api_key": self.TMDB_API_KEY}
        return {}

    @property
    def tmdb_configured(self) -> bool:
        """TMDB 인증 정보가 설정되어 있는지 여부."""
        return bool(self.TMDB_ACCESS_TOKEN or self.TMDB_API_KEY)


@lru_cache
def get_settings() -> Settings:
    """설정 객체를 반환합니다. 최초 호출 시 한 번만 생성됩니다."""
    return Settings()


settings = get_settings()