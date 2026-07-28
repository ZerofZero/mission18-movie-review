"""데이터베이스 연결 모듈.

SQLAlchemy 엔진과 세션을 구성하고, FastAPI 의존성으로 사용할 세션 생성 함수를
제공합니다.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# 엔진 생성
#
# SQLite 는 기본적으로 하나의 스레드에서만 연결을 사용하도록 제한합니다.
# FastAPI 는 여러 스레드에서 요청을 처리하므로 check_same_thread 를 해제합니다.
# ---------------------------------------------------------------------------
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


# ---------------------------------------------------------------------------
# 외래 키 제약 활성화
#
# SQLite 는 외래 키 제약을 기본적으로 강제하지 않습니다.
# ON DELETE CASCADE 가 동작하도록 연결마다 PRAGMA 를 설정합니다.
# ---------------------------------------------------------------------------
if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(Engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# 세션
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속하는 기본 클래스."""


def get_db() -> Generator[Session, None, None]:
    """요청 단위 데이터베이스 세션을 제공하는 FastAPI 의존성."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """정의된 모든 테이블을 생성합니다. 이미 존재하는 테이블은 건너뜁니다."""
    # 모델을 import 해야 Base 에 테이블 정보가 등록됩니다.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)