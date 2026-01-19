# Week 9: Document Pipeline API Service

8주차 문서 처리 파이프라인을 FastAPI로 제공하는 프로덕션 레벨 API 서비스입니다.

## 📋 기능

- **비동기 파이프라인 실행**: 백그라운드에서 4단계 문서 처리
- **실시간 상태 추적**: 각 단계별 진행 상황 확인
- **Swagger UI**: 자동 생성된 API 문서 및 테스트 인터페이스
- **LangSmith 모니터링**: 실행 추적, 비용 분석, 에러 로깅

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어서 API 키 입력
```

### 2. 서버 실행

```bash
# 개발 서버 실행
python app.py

# 또는 uvicorn 직접 실행
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 3. API 테스트

브라우저에서 접속:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📡 API 엔드포인트

### 파이프라인 실행
```bash
POST /api/v1/run
Content-Type: application/json

{
  "document": "문서 내용...",
  "user_goal": "이 문서를 요약해주세요"
}

Response:
{
  "run_id": "run_abc123",
  "status": "pending",
  "message": "파이프라인 실행이 시작되었습니다"
}
```

### 상태 확인
```bash
GET /api/v1/status/{run_id}

Response:
{
  "run_id": "run_abc123",
  "status": "running",
  "current_step": 2,
  "total_steps": 4,
  "message": "Step 2/4: 입력 읽기"
}
```

### 결과 조회
```bash
GET /api/v1/result/{run_id}

Response:
{
  "run_id": "run_abc123",
  "status": "completed",
  "result": {
    "summary": "요약 내용...",
    "key_points": ["포인트1", "포인트2"],
    "action_items": ["액션1", "액션2"]
  }
}
```

## 📊 LangSmith 모니터링

1. https://smith.langchain.com 접속
2. 프로젝트 "week9-deployment" 선택
3. 다음 항목 확인:
   - **Traces**: 각 실행의 상세 추적
   - **Costs**: 토큰 사용량 및 비용
   - **Errors**: 실패한 실행의 에러 로그

## 🚢 배포

### Railway 배포 (추천)

1. GitHub에 코드 푸시
2. railway.app 에서 새 프로젝트 생성
3. GitHub 저장소 연결
4. 환경변수 설정 (OPENAI_API_KEY 등)
5. 자동 배포 완료

### Render 배포

1. render.com 에서 Web Service 생성
2. GitHub 저장소 연결
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. 환경변수 설정

## 📁 프로젝트 구조

```
week9_api/
├── app.py              # 메인 FastAPI 애플리케이션
├── week8_pipeline.py   # 8주차 파이프라인 코드
├── requirements.txt    # 패키지 의존성
├── .env.example       # 환경변수 템플릿
├── runs/              # 파이프라인 실행 결과 저장
│   └── run_xxx/
│       ├── step_01.json
│       ├── step_02.json
│       ├── step_03.json
│       ├── step_04.json
│       └── final_output.json
└── README.md          # 이 파일

```

## 🔧 트러블슈팅

### OpenAI API 키 오류
- `.env` 파일에 올바른 API 키가 설정되어 있는지 확인
- 키의 앞뒤 공백 제거

### LangSmith 추적이 안 될 때
- LANGCHAIN_API_KEY가 올바른지 확인
- LANGCHAIN_TRACING_V2가 "true"로 설정되어 있는지 확인

### 파이프라인 실행이 오래 걸릴 때
- 문서 길이가 너무 긴 경우 첫 2000자만 처리하도록 제한됨
- GPT-3.5-turbo 대신 더 빠른 모델 사용 고려

## 📝 참고사항

- 이 코드는 8주차 파이프라인을 기반으로 합니다
- STOP/Resume 기능은 이번 과제에서 제외되었습니다
- 파일 시스템 기반 저장을 사용합니다 (프로덕션에서는 DB 권장)

## 🤝 기여

문제를 발견하거나 개선 사항이 있으면 Issue를 생성해주세요.

## 📄 라이선스

MIT License
