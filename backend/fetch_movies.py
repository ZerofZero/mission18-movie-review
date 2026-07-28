"""시드용 영화 데이터 수집 스크립트.

TMDB 에서 영화 정보를 내려받아 data/seed_movies.json 으로 저장합니다.
개발 단계에서 한 번만 실행하며, 애플리케이션은 기동 시 이 파일만 읽습니다.
매 기동마다 TMDB 를 호출하지 않도록 하기 위한 구조입니다.

사용법
    python fetch_movies.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

# app 패키지의 설정을 재사용합니다.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "seed_movies.json"
REQUEST_TIMEOUT = 15.0
REQUEST_INTERVAL = 0.2

# 리뷰를 함께 등록할 영화입니다. 번호를 직접 지정해 검색 결과가 흔들리지 않게 합니다.
REVIEW_TARGET_IDS = [
    496243,  # 기생충
    157336,  # 인터스텔라
    313369,  # 라라랜드
    396535,  # 부산행
    293670,  # 곡성
]

# 추가로 수집할 목록과 편수입니다.
# 평점 상위 목록은 명작 위주이고, 인기 목록은 최근 화제작 위주입니다.
# 두 목록을 함께 사용해 목록의 성격이 한쪽으로 치우치지 않도록 합니다.
EXTRA_SOURCES = [
    {"path": "/movie/top_rated", "count": 100, "max_pages": 15},
    {"path": "/movie/popular", "count": 195, "max_pages": 20},
]


# ---------------------------------------------------------------------------
# TMDB 호출
# ---------------------------------------------------------------------------

def tmdb_get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    """TMDB API 를 호출하고 응답 본문을 반환합니다."""
    merged = {"language": settings.TMDB_LANGUAGE}
    merged.update(settings.tmdb_auth_params)
    if params:
        merged.update(params)

    response = client.get(
        f"{settings.TMDB_BASE_URL}{path}",
        params=merged,
        headers=settings.tmdb_headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# 변환
# ---------------------------------------------------------------------------

def extract_director(detail: dict) -> str | None:
    """제작진 정보에서 감독 이름을 추출합니다."""
    crew = (detail.get("credits") or {}).get("crew") or []
    names = [m["name"] for m in crew if m.get("job") == "Director" and m.get("name")]
    return ", ".join(names) if names else None


def extract_genre(detail: dict) -> str | None:
    """장르 목록을 쉼표로 이어 붙입니다."""
    names = [g["name"] for g in (detail.get("genres") or []) if g.get("name")]
    return ", ".join(names) if names else None


def to_seed_record(detail: dict) -> dict | None:
    """상세 정보를 시드 형식으로 변환합니다.

    포스터, 감독, 개봉일 중 하나라도 없으면 화면 구성이 어색해지므로 제외합니다.
    """
    poster_path = detail.get("poster_path")
    director = extract_director(detail)
    release_date = detail.get("release_date") or None

    if not poster_path or not director or not release_date:
        return None

    return {
        "tmdb_id": detail["id"],
        "title": detail.get("title") or detail.get("original_title"),
        "release_date": release_date,
        "director": director,
        "genre": extract_genre(detail),
        "poster_url": f"{settings.TMDB_IMAGE_BASE_URL}{poster_path}",
        "tmdb_vote_average": detail.get("vote_average"),
    }


def fetch_detail(client: httpx.Client, tmdb_id: int) -> dict | None:
    """영화 상세 정보를 조회해 시드 형식으로 변환합니다."""
    detail = tmdb_get(
        client, f"/movie/{tmdb_id}", {"append_to_response": "credits"}
    )
    return to_seed_record(detail)


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------

def collect_review_targets(client: httpx.Client) -> list[dict]:
    """리뷰 대상 영화를 수집합니다."""
    records = []
    for tmdb_id in REVIEW_TARGET_IDS:
        record = fetch_detail(client, tmdb_id)
        if record is None:
            print(f"  [제외] 번호 {tmdb_id}: 필수 정보 누락")
        else:
            records.append(record)
            print(f"  [수집] {record['title']} ({record['release_date']})")
        time.sleep(REQUEST_INTERVAL)
    return records


def collect_from_source(
    client: httpx.Client,
    path: str,
    count: int,
    max_pages: int,
    exclude_ids: set[int],
) -> list[dict]:
    """지정한 TMDB 목록에서 영화를 수집합니다."""
    records: list[dict] = []

    for page in range(1, max_pages + 1):
        if len(records) >= count:
            break

        data = tmdb_get(client, path, {"page": page})
        for item in data.get("results") or []:
            if len(records) >= count:
                break

            tmdb_id = item["id"]
            if tmdb_id in exclude_ids:
                continue

            record = fetch_detail(client, tmdb_id)
            time.sleep(REQUEST_INTERVAL)

            if record is None:
                continue

            records.append(record)
            exclude_ids.add(tmdb_id)
            print(f"  [수집] {record['title']} ({record['release_date']})")

    return records


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    if not settings.tmdb_configured:
        print("TMDB 인증 정보가 설정되어 있지 않습니다. .env 를 확인해주세요.")
        sys.exit(1)

    with httpx.Client() as client:
        print("리뷰 대상 영화를 수집합니다.")
        review_targets = collect_review_targets(client)

        exclude_ids = {record["tmdb_id"] for record in review_targets}
        source_results: list[tuple[str, list[dict]]] = []

        for source in EXTRA_SOURCES:
            print()
            print(f"{source['path']} 에서 최대 {source['count']}편을 수집합니다.")
            records = collect_from_source(
                client,
                path=source["path"],
                count=source["count"],
                max_pages=source["max_pages"],
                exclude_ids=exclude_ids,
            )
            source_results.append((source["path"], records))

    movies = review_targets + [r for _, records in source_results for r in records]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(movies, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"저장 위치      : {OUTPUT_PATH}")
    print(f"리뷰 대상 영화 : {len(review_targets)}편")
    for path, records in source_results:
        print(f"{path:20} : {len(records)}편")
    print(f"전체           : {len(movies)}편")


if __name__ == "__main__":
    main()