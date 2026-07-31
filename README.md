# 영화 리뷰 감성 분석 서비스

영화 정보와 사용자 리뷰를 관리하고, 리뷰의 감성을 분석해 평점을 산출하는 웹 서비스입니다.
사용자가 별점을 직접 매기는 대신 리뷰 문장의 감성을 모델이 판정하고, 그 결과를 수치로 환산해 평점으로 제공합니다.

AI 부트캠프 스프린트 미션 18 과제로 제작했습니다.

## 배포 주소

| 구분 | 주소 |
|---|---|
| 프론트엔드 | https://mission18-movie-review.streamlit.app |
| 백엔드 API | https://movie-review-api-256118486084.asia-northeast3.run.app |
| API 문서 | https://movie-review-api-256118486084.asia-northeast3.run.app/docs |
| 컨테이너 이미지 | https://hub.docker.com/r/wldn2386/movie-review-api |

프론트엔드는 Streamlit Community Cloud, 백엔드는 Google Cloud Run 에 배포되어 있습니다.
백엔드는 일정 시간 요청이 없으면 대기 상태로 전환되므로, 첫 접속 시 컨테이너 기동과
모델 적재로 20초 내외가 소요될 수 있습니다.

## 기술 스택

| 구분 | 기술 |
|---|---|
| 프론트엔드 | Streamlit |
| 백엔드 | FastAPI |
| 데이터베이스 | SQLite, SQLAlchemy |
| 모델 서빙 | ONNX Runtime |
| 외부 API | TMDB |
| 배포 | Streamlit Community Cloud, Google Cloud Run |

## 주요 기능

- 영화 목록 조회. 제목 검색, 장르 필터, 정렬, 분할 조회
- 영화 등록. TMDB 검색으로 입력 항목 자동 완성
- 리뷰 등록. 한국어 리뷰만 허용하며 등록과 동시에 감성 분석 수행
- 영화별 평점 조회. 감성 점수의 평균
- 최근 리뷰 조회
- 관리자 키를 통한 영화 및 리뷰 삭제

## 감성 분석 모델

두 개의 모델을 결합해 판정합니다.

| 구분 | 모델 | 역할 |
|---|---|---|
| 주 모델 | KR-ELECTRA 기반 3-class 분류 | 중립 판정 |
| 보조 모델 | KoELECTRA-small 기반 2-class 분류 | 긍정과 부정 구분 |

주 모델이 중립으로 판정한 문장은 그대로 두고, 긍정이나 부정으로 판정한 문장만
중립 확률을 유지한 채 나머지 확률을 보조 모델 비율로 다시 배분합니다.

직접 작성한 영화 리뷰 60건으로 검증한 결과입니다.

| 구분 | 주 모델 단독 | 결합 |
|---|---|---|
| 전체 | 86.7퍼센트 | 90.0퍼센트 |
| 부정 | 92.9퍼센트 | 92.9퍼센트 |
| 중립 | 81.2퍼센트 | 81.2퍼센트 |
| 긍정 | 86.7퍼센트 | 93.3퍼센트 |

두 모델 모두 ONNX 형식으로 변환하고 동적 양자화를 적용해 PyTorch 없이 추론합니다.
합산 용량은 366MB 입니다.

### 평점 산출

각 리뷰의 감성 확률 분포에 가중치를 적용해 점수를 구한 뒤 영화별로 평균합니다.

```
리뷰 점수 = 부정확률 × 1 + 중립확률 × 3 + 긍정확률 × 5
영화 평점 = 해당 영화 리뷰들의 점수 평균
```

확률의 합이 1이므로 결과는 항상 1점에서 5점 사이입니다.

## 폴더 구조

```
.
├── backend/            FastAPI 백엔드
│   ├── app/
│   │   ├── routers/    엔드포인트 정의
│   │   └── sentiment/  감성 분석 모듈과 모델
│   ├── data/           시드 자료
│   └── Dockerfile
├── frontend/           Streamlit 프론트엔드
└── report/             보고서
```

## 모델 파일에 관하여

**감성 분석 모델은 이 저장소에 포함되어 있지 않습니다.**
주 모델이 352MB 로 GitHub 의 단일 파일 상한을 넘기 때문입니다.

모델은 컨테이너 이미지에 포함해 배포합니다. 이미지를 내려받으면 모델이 함께 딸려 옵니다.

```
docker pull wldn2386/movie-review-api:latest
```

소스에서 직접 빌드하려면 아래 경로에 모델 파일을 배치해야 합니다.

```
backend/app/sentiment/model/
    mission_16_kr_electra_quantized.onnx
    tokenizer.json
    tokenizer_config.json
    special_tokens_map.json
    vocab.txt

backend/app/sentiment/model_binary/
    nsmc_koelectra_small_quantized.onnx
    tokenizer.json
    tokenizer_config.json
    special_tokens_map.json
    vocab.txt
```

보조 모델은 `backend/export_binary_model.py` 를 실행해 직접 변환할 수 있습니다.

## 로컬 실행

### 준비

`backend/.env.example` 을 복사해 `backend/.env` 를 만들고 값을 채웁니다.

| 변수 | 설명 |
|---|---|
| `TMDB_ACCESS_TOKEN` 또는 `TMDB_API_KEY` | TMDB 인증 정보 |
| `ADMIN_KEY` | 삭제 요청에 필요한 관리자 키 |

### 실행

터미널 두 개가 필요합니다.

```
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

```
cd frontend
pip install -r requirements.txt
python -m streamlit run app.py
```

프론트엔드는 `http://localhost:8501`, API 문서는 `http://127.0.0.1:8000/docs` 입니다.

기동 시 데이터베이스가 비어 있으면 시드 자료를 자동으로 삽입합니다.
영화 300편과 리뷰 60건이 들어가며 리뷰는 삽입 시점에 감성 분석을 수행합니다.

### 데이터 초기화

```
cd backend
python -m app.seed
```

## 컨테이너 실행

```
cd backend
docker build -t movie-review-api .
docker run --rm -p 8080:8080 \
    -e TMDB_API_KEY=값 \
    -e ADMIN_KEY=값 \
    movie-review-api
```

환경 변수는 이미지에 포함하지 않고 실행 시 주입합니다.

## 배포

### 백엔드

Google Cloud Run 에 배포했습니다.

```
gcloud run deploy movie-review-api \
    --image asia-northeast3-docker.pkg.dev/PROJECT/movie-review/movie-review-api:latest \
    --region asia-northeast3 \
    --allow-unauthenticated \
    --memory 2Gi \
    --max-instances 1 \
    --timeout 300 \
    --set-env-vars "TMDB_API_KEY=값,ADMIN_KEY=값"
```

인스턴스를 하나로 고정한 이유는 SQLite 파일이 인스턴스마다 따로 만들어지기 때문입니다.
Cloud Run 의 파일 시스템은 유지되지 않으므로 컨테이너가 다시 시작되면 자료가 초기화되며,
이 경우 기동 시 시드가 다시 삽입됩니다.

### 프론트엔드

Streamlit Community Cloud 에 배포했습니다.

| 항목 | 값 |
|---|---|
| 저장소 | `ZerofZero/mission18-movie-review` |
| 브랜치 | `main` |
| 진입점 | `frontend/app.py` |
| Python | 3.12 |

의존성은 `frontend/requirements.txt` 가 사용됩니다.
Community Cloud 는 진입점 파일이 있는 디렉터리를 먼저 확인한 뒤 저장소 최상위를 확인하며,
진입점 디렉터리의 파일이 우선합니다.

백엔드 주소는 저장소에 두지 않고 Secrets 에 등록합니다.

```toml
BACKEND_URL = "https://movie-review-api-256118486084.asia-northeast3.run.app"
```

`frontend/config.py` 는 Streamlit secrets, 환경 변수, 기본값 순으로 주소를 찾으므로
배포 환경에서 코드를 수정할 필요가 없습니다.

## 데이터 출처

영화 정보와 포스터 이미지는 TMDB 에서 제공받았습니다.
리뷰는 저작권 문제를 피하기 위해 직접 작성했으며, 작성자는 별명으로 표시하고 개인정보를 수집하지 않습니다.

This product uses the TMDB API but is not endorsed or certified by TMDB.