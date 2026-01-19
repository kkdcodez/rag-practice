"""
Week 9: AI Pipeline API Service
8주차 파이프라인을 FastAPI로 감싸서 RESTful API로 제공
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import threading
import uuid
from datetime import datetime
from pathlib import Path
import json

# 8주차 파이프라인 임포트 (실제 경로에 맞게 수정 필요)
# from week8_pipeline import PipelineController, FileManager, Request

app = FastAPI(
    title="Document Pipeline API",
    version="1.0.0",
    description="8주차 문서 처리 파이프라인을 API로 제공합니다"
)

# ============= Pydantic Models =============
class PipelineRequest(BaseModel):
    """파이프라인 실행 요청"""
    document: str
    user_goal: str

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
# 실행 중인 파이프라인 상태를 추적
pipeline_status = {}

# ============= 8주차 코드 임시 구현 =============
# 실제 구현 시 8주차 코드를 import해서 사용
class MockPipelineController:
    """8주차 PipelineController 모의 구현"""
    def __init__(self):
        self.file_manager = MockFileManager()
    
    def run(self, request):
        """파이프라인 실행 (실제로는 8주차 코드 사용)"""
        import time
        run_id = request.id
        
        # 상태 업데이트
        pipeline_status[run_id] = {"status": "running", "current_step": 0}
        
        try:
            # 4단계 실행 시뮬레이션
            for step in range(1, 5):
                pipeline_status[run_id]["current_step"] = step
                
                # Step 실행 (실제로는 8주차 로직)
                result = {
                    "step": step,
                    "step_name": ["계획 세우기", "입력 읽기", "초안 만들기", "최종 정리"][step-1],
                    "result": f"Step {step} 결과",
                    "timestamp": datetime.now().isoformat()
                }
                
                # 파일로 저장
                self.file_manager.save_step_result(run_id, result, step)
                
                # 실행 시간 시뮬레이션
                time.sleep(2)
            
            # 최종 결과 저장
            final_result = {
                "summary": "문서 요약 결과",
                "key_points": ["포인트1", "포인트2", "포인트3"],
                "action_items": ["할일1", "할일2"]
            }
            self.file_manager.save_final_result(run_id, final_result)
            
            # 상태 완료로 업데이트
            pipeline_status[run_id] = {
                "status": "completed",
                "current_step": 4,
                "result": final_result
            }
            
        except Exception as e:
            # 에러 처리
            pipeline_status[run_id] = {
                "status": "failed",
                "error": str(e)
            }

class MockFileManager:
    """8주차 FileManager 모의 구현"""
    def __init__(self, base_dir="runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
    
    def save_step_result(self, run_id: str, result: dict, step: int):
        """Step 결과를 파일로 저장"""
        run_dir = self.base_dir / run_id
        run_dir.mkdir(exist_ok=True)
        
        filepath = run_dir / f"step_{step:02d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def save_final_result(self, run_id: str, result: dict):
        """최종 결과 저장"""
        run_dir = self.base_dir / run_id
        filepath = run_dir / "final_output.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def load_final_result(self, run_id: str) -> Optional[dict]:
        """최종 결과 불러오기"""
        filepath = self.base_dir / run_id / "final_output.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_completed_steps(self, run_id: str) -> int:
        """완료된 Step 수 확인"""
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return 0
        
        step_files = list(run_dir.glob("step_*.json"))
        return len(step_files)

class MockRequest:
    """8주차 Request 모의 구현"""
    def __init__(self, id: str, user_goal: str, document: str):
        self.id = id
        self.user_goal = user_goal
        self.document = document

# 파이프라인 컨트롤러 인스턴스
pipeline_controller = MockPipelineController()
file_manager = MockFileManager()

# ============= 백그라운드 실행 함수 =============
def run_pipeline_background(run_id: str, document: str, user_goal: str):
    """백그라운드에서 파이프라인 실행"""
    # 8주차 Request 객체 생성
    request = MockRequest(
        id=run_id,
        user_goal=user_goal,
        document=document
    )
    
    # 파이프라인 실행
    pipeline_controller.run(request)

# ============= API 엔드포인트 =============

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "service": "Document Pipeline API",
        "version": "1.0.0"
    }

@app.post("/api/v1/run", 
          response_model=PipelineResponse,
          summary="파이프라인 실행",
          description="문서 처리 파이프라인을 백그라운드에서 실행합니다")
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
        "current_step": 0
    }
    
    # 백그라운드 스레드에서 실행
    thread = threading.Thread(
        target=run_pipeline_background,
        args=(run_id, request.document, request.user_goal)
    )
    thread.daemon = True  # 메인 프로세스 종료 시 같이 종료
    thread.start()
    
    return PipelineResponse(
        run_id=run_id,
        status="pending",
        message=f"파이프라인 실행이 시작되었습니다. run_id: {run_id}"
    )

@app.get("/api/v1/status/{run_id}",
         response_model=StatusResponse,
         summary="실행 상태 조회",
         description="파이프라인 실행 상태를 조회합니다")
async def get_status(run_id: str):
    """
    파이프라인 실행 상태 조회
    - pending: 대기 중
    - running: 실행 중
    - completed: 완료
    - failed: 실패
    """
    # 메모리에서 상태 확인
    if run_id in pipeline_status:
        status_info = pipeline_status[run_id]
        return StatusResponse(
            run_id=run_id,
            status=status_info.get("status", "unknown"),
            current_step=status_info.get("current_step", 0),
            total_steps=4,
            message=f"Step {status_info.get('current_step', 0)}/4 진행 중"
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
            message=f"Step {completed_steps}/4 {'완료' if completed_steps == 4 else '진행 중'}"
        )
    
    # 찾을 수 없음
    raise HTTPException(status_code=404, detail=f"Run ID {run_id}를 찾을 수 없습니다")

@app.get("/api/v1/result/{run_id}",
         response_model=ResultResponse,
         summary="실행 결과 조회",
         description="완료된 파이프라인의 결과를 조회합니다")
async def get_result(run_id: str):
    """
    파이프라인 실행 결과 조회
    - 완료된 경우에만 결과 반환
    - 진행 중인 경우 현재 상태 반환
    """
    # 상태 확인
    if run_id in pipeline_status:
        status_info = pipeline_status[run_id]
        
        if status_info["status"] == "completed":
            # 파일에서 결과 읽기
            result = file_manager.load_final_result(run_id)
            return ResultResponse(
                run_id=run_id,
                status="completed",
                result=result or status_info.get("result")
            )
        elif status_info["status"] == "failed":
            return ResultResponse(
                run_id=run_id,
                status="failed",
                error=status_info.get("error", "Unknown error")
            )
        else:
            return ResultResponse(
                run_id=run_id,
                status=status_info["status"],
                result=None
            )
    
    # 파일 시스템에서 확인
    result = file_manager.load_final_result(run_id)
    if result:
        return ResultResponse(
            run_id=run_id,
            status="completed",
            result=result
        )
    
    # 찾을 수 없음
    raise HTTPException(status_code=404, detail=f"Run ID {run_id}의 결과를 찾을 수 없습니다")

# ============= Health Check =============
@app.get("/health",
         summary="헬스 체크",
         description="서비스 상태를 확인합니다")
async def health_check():
    """서비스 상태 확인"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_pipelines": len([s for s in pipeline_status.values() if s["status"] == "running"])
    }

if __name__ == "__main__":
    import uvicorn
    # 개발 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
