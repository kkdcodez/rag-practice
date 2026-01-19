"""
Week 9: Production API Server
8주차 파이프라인과 FastAPI를 통합한 실제 실행 파일
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import threading
import uuid
from datetime import datetime
from pathlib import Path
import os
from dotenv import load_dotenv

# 상위 폴더의 .env 파일 로드 (week9_api 폴더 기준)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


# LangSmith 설정 (환경변수로 관리)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "10_monitoring"

# 8주차 파이프라인 임포트
from week8_pipeline import PipelineController, FileManager, Request

app = FastAPI(
    title="Document Pipeline API",
    version="1.0.0",
    description="8주차 문서 처리 파이프라인을 프로덕션 레벨 API로 제공합니다",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============= Pydantic Models =============
class PipelineRequest(BaseModel):
    """파이프라인 실행 요청"""

    document: str
    user_goal: str

    class Config:
        json_schema_extra = {
            "example": {
                "document": "인공지능 기술이 빠르게 발전하고 있습니다. 특히 대규모 언어모델의 등장으로...",
                "user_goal": "이 문서를 요약하고 주요 액션아이템을 추출해주세요",
            }
        }


class PipelineResponse(BaseModel):
    """파이프라인 실행 응답"""

    run_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    """상태 조회 응답"""

    run_id: str
    status: str  # pending, running, completed, failed
    current_step: Optional[int] = None
    total_steps: int = 4
    message: Optional[str] = None


class ResultResponse(BaseModel):
    """결과 조회 응답"""

    run_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============= 전역 상태 관리 =============
pipeline_status = {}
pipeline_controller = PipelineController()
file_manager = FileManager()


# ============= 상태 업데이트 콜백 =============
def update_status(
    run_id: str, status: str, step: int = None, result: dict = None, error: str = None
):
    """파이프라인 상태 업데이트 콜백"""
    pipeline_status[run_id] = {
        "status": status,
        "current_step": step,
        "timestamp": datetime.now().isoformat(),
    }

    if result:
        pipeline_status[run_id]["result"] = result
    if error:
        pipeline_status[run_id]["error"] = error


# ============= 백그라운드 실행 함수 =============
def run_pipeline_background(run_id: str, document: str, user_goal: str):
    """백그라운드에서 파이프라인 실행"""
    try:
        # Request 객체 생성
        request = Request(id=run_id, user_goal=user_goal, document=document)

        # 파이프라인 실행 (콜백과 함께)
        result = pipeline_controller.run(request, status_callback=update_status)

        # 완료 상태 업데이트
        update_status(run_id, "completed", 4, result)

    except Exception as e:
        # 실패 상태 업데이트
        update_status(run_id, "failed", error=str(e))
        print(f"Pipeline error for {run_id}: {e}")


# ============= API 엔드포인트 =============


@app.get("/", tags=["Health"])
async def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "service": "Document Pipeline API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.post(
    "/api/v1/run",
    response_model=PipelineResponse,
    summary="파이프라인 실행",
    description="문서 처리 파이프라인을 백그라운드에서 실행합니다",
    tags=["Pipeline"],
)
async def run_pipeline(request: PipelineRequest):
    """
    파이프라인 실행 요청

    - 즉시 run_id를 반환하고 백그라운드에서 처리
    - GET /api/v1/status/{run_id}로 상태 확인
    - GET /api/v1/result/{run_id}로 결과 조회
    """
    # Run ID 생성
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # 초기 상태 설정
    pipeline_status[run_id] = {
        "status": "pending",
        "current_step": 0,
        "timestamp": datetime.now().isoformat(),
    }

    # 백그라운드 스레드에서 실행
    thread = threading.Thread(
        target=run_pipeline_background,
        args=(run_id, request.document, request.user_goal),
    )
    thread.daemon = True
    thread.start()

    return PipelineResponse(
        run_id=run_id,
        status="pending",
        message=f"파이프라인 실행이 시작되었습니다. run_id: {run_id}",
    )


@app.get(
    "/api/v1/status/{run_id}",
    response_model=StatusResponse,
    summary="실행 상태 조회",
    description="파이프라인 실행 상태를 조회합니다",
    tags=["Pipeline"],
)
async def get_status(run_id: str):
    """
    파이프라인 실행 상태 조회

    상태값:
    - pending: 대기 중
    - running: 실행 중 (current_step 확인 가능)
    - completed: 완료
    - failed: 실패
    """
    # 메모리에서 상태 확인
    if run_id in pipeline_status:
        status_info = pipeline_status[run_id]

        message = None
        if status_info["status"] == "running":
            step = status_info.get("current_step", 0)
            step_names = ["계획 세우기", "입력 읽기", "초안 만들기", "최종 정리"]
            message = f"Step {step}/4: {step_names[step-1] if step > 0 and step <= 4 else '준비 중'}"
        elif status_info["status"] == "completed":
            message = "파이프라인 실행 완료"
        elif status_info["status"] == "failed":
            message = "파이프라인 실행 실패"

        return StatusResponse(
            run_id=run_id,
            status=status_info.get("status", "unknown"),
            current_step=status_info.get("current_step"),
            total_steps=4,
            message=message,
        )

    # 메모리에 없으면 파일 시스템 확인
    completed_steps = file_manager.get_completed_steps(run_id)
    if completed_steps > 0:
        status = "completed" if completed_steps == 4 else "running"
        return StatusResponse(
            run_id=run_id,
            status=status,
            current_step=completed_steps,
            total_steps=4,
            message=f"Step {completed_steps}/4 {'완료' if completed_steps == 4 else '진행 중'}",
        )

    # 찾을 수 없음
    raise HTTPException(status_code=404, detail=f"Run ID {run_id}를 찾을 수 없습니다")


@app.get(
    "/api/v1/result/{run_id}",
    response_model=ResultResponse,
    summary="실행 결과 조회",
    description="완료된 파이프라인의 결과를 조회합니다",
    tags=["Pipeline"],
)
async def get_result(run_id: str):
    """
    파이프라인 실행 결과 조회

    - 완료된 경우에만 결과 반환
    - 진행 중인 경우 현재 상태만 반환
    - 실패한 경우 에러 메시지 포함
    """
    # 상태 확인
    if run_id in pipeline_status:
        status_info = pipeline_status[run_id]

        if status_info["status"] == "completed":
            # 파일에서 결과 읽기 (백업)
            result = file_manager.load_final_result(run_id)
            if not result:
                result = status_info.get("result")

            return ResultResponse(run_id=run_id, status="completed", result=result)
        elif status_info["status"] == "failed":
            return ResultResponse(
                run_id=run_id,
                status="failed",
                error=status_info.get("error", "Unknown error occurred"),
            )
        else:
            return ResultResponse(
                run_id=run_id, status=status_info["status"], result=None
            )

    # 파일 시스템에서 확인
    result = file_manager.load_final_result(run_id)
    if result:
        return ResultResponse(run_id=run_id, status="completed", result=result)

    # 찾을 수 없음
    raise HTTPException(
        status_code=404, detail=f"Run ID {run_id}의 결과를 찾을 수 없습니다"
    )


@app.get(
    "/health",
    summary="헬스 체크",
    description="서비스 상태를 확인합니다",
    tags=["Health"],
)
async def health_check():
    """서비스 상태 확인"""
    active_count = len(
        [s for s in pipeline_status.values() if s["status"] == "running"]
    )
    total_count = len(pipeline_status)

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pipelines": {"active": active_count, "total": total_count},
        "langsmith": {
            "enabled": os.environ.get("LANGCHAIN_TRACING_V2") == "true",
            "project": os.environ.get("LANGCHAIN_PROJECT", "not set"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🚀 Document Pipeline API Server")
    print("=" * 60)
    print("📝 Swagger UI: http://localhost:8000/docs")
    print("📚 ReDoc: http://localhost:8000/redoc")
    print("🔍 LangSmith: Check your dashboard at smith.langchain.com")
    print("=" * 60)

    # 개발 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
