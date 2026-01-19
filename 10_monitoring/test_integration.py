"""
Week 10: 통합 테스트 (Integration Tests)
Part 1 - FastAPI 엔드포인트 통합 테스트
"""

import pytest
import time
import os
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient

# 테스트 대상 모듈 임포트
from app import app, pipeline_status


# ============= Fixtures =============

@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트"""
    # 테스트 전 상태 초기화
    pipeline_status.clear()
    return TestClient(app)


@pytest.fixture
def sample_request_data():
    """테스트용 요청 데이터"""
    return {
        "document": """
        인공지능(AI) 기술이 빠르게 발전하고 있습니다. 
        특히 대규모 언어모델(LLM)의 등장으로 자연어 처리 분야에서 
        혁신적인 변화가 일어나고 있습니다.
        """,
        "user_goal": "이 문서를 요약하고 핵심 포인트를 추출해주세요"
    }


# ============= 헬스체크 테스트 =============

class TestHealthEndpoints:
    """헬스체크 엔드포인트 테스트"""
    
    def test_root_endpoint(self, client):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["service"] == "Document Pipeline API"
        assert data["version"] == "1.0.0"
    
    def test_health_endpoint(self, client):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "pipelines" in data
        assert "langsmith" in data


# ============= 파이프라인 실행 테스트 =============

class TestPipelineRunEndpoint:
    """파이프라인 실행 엔드포인트 테스트"""
    
    def test_run_pipeline_success(self, client, sample_request_data):
        """파이프라인 실행 성공 테스트"""
        response = client.post("/api/v1/run", json=sample_request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "pending"
        assert data["run_id"].startswith("run_")
    
    def test_run_pipeline_missing_document(self, client):
        """필수 필드 누락 테스트 - document"""
        response = client.post("/api/v1/run", json={
            "user_goal": "요약해주세요"
        })
        
        assert response.status_code == 422  # Validation Error
    
    def test_run_pipeline_missing_user_goal(self, client):
        """필수 필드 누락 테스트 - user_goal"""
        response = client.post("/api/v1/run", json={
            "document": "테스트 문서"
        })
        
        assert response.status_code == 422  # Validation Error
    
    def test_run_pipeline_empty_body(self, client):
        """빈 요청 바디 테스트"""
        response = client.post("/api/v1/run", json={})
        
        assert response.status_code == 422
    
    def test_run_pipeline_creates_status_entry(self, client, sample_request_data):
        """파이프라인 실행 시 상태 엔트리 생성 확인"""
        response = client.post("/api/v1/run", json=sample_request_data)
        
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        
        # 상태가 생성되었는지 확인
        assert run_id in pipeline_status
        assert pipeline_status[run_id]["status"] in ["pending", "running"]


# ============= 상태 조회 테스트 =============

class TestStatusEndpoint:
    """상태 조회 엔드포인트 테스트"""
    
    def test_status_pending(self, client, sample_request_data):
        """대기 중 상태 조회 테스트"""
        # 파이프라인 실행
        run_response = client.post("/api/v1/run", json=sample_request_data)
        run_id = run_response.json()["run_id"]
        
        # 즉시 상태 조회 (아직 pending일 가능성 높음)
        status_response = client.get(f"/api/v1/status/{run_id}")
        
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["run_id"] == run_id
        assert data["status"] in ["pending", "running", "completed"]
        assert data["total_steps"] == 4
    
    def test_status_not_found(self, client):
        """존재하지 않는 run_id 상태 조회 테스트"""
        response = client.get("/api/v1/status/nonexistent_run_id")
        
        assert response.status_code == 404
        assert "찾을 수 없습니다" in response.json()["detail"]
    
    def test_status_shows_current_step(self, client):
        """현재 진행 중인 Step 표시 테스트"""
        # 수동으로 상태 설정
        test_run_id = "test_status_001"
        pipeline_status[test_run_id] = {
            "status": "running",
            "current_step": 2,
            "timestamp": "2024-01-01T00:00:00"
        }
        
        response = client.get(f"/api/v1/status/{test_run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["current_step"] == 2
        assert "Step 2/4" in data["message"]


# ============= 결과 조회 테스트 =============

class TestResultEndpoint:
    """결과 조회 엔드포인트 테스트"""
    
    def test_result_completed(self, client):
        """완료된 파이프라인 결과 조회 테스트"""
        # 완료 상태 수동 설정
        test_run_id = "test_result_001"
        pipeline_status[test_run_id] = {
            "status": "completed",
            "current_step": 4,
            "result": {
                "summary": "테스트 요약",
                "key_points": ["포인트1", "포인트2"],
                "action_items": ["액션1"]
            }
        }
        
        response = client.get(f"/api/v1/result/{test_run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] is not None
        assert data["result"]["summary"] == "테스트 요약"
    
    def test_result_not_completed(self, client):
        """진행 중인 파이프라인 결과 조회 테스트"""
        test_run_id = "test_result_002"
        pipeline_status[test_run_id] = {
            "status": "running",
            "current_step": 2
        }
        
        response = client.get(f"/api/v1/result/{test_run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["result"] is None
    
    def test_result_failed(self, client):
        """실패한 파이프라인 결과 조회 테스트"""
        test_run_id = "test_result_003"
        pipeline_status[test_run_id] = {
            "status": "failed",
            "error": "API 호출 실패"
        }
        
        response = client.get(f"/api/v1/result/{test_run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "API 호출 실패"
    
    def test_result_not_found(self, client):
        """존재하지 않는 run_id 결과 조회 테스트"""
        response = client.get("/api/v1/result/nonexistent_run_id")
        
        assert response.status_code == 404


# ============= 엣지 케이스 테스트 =============

class TestEdgeCases:
    """엣지 케이스 통합 테스트"""
    
    def test_empty_document(self, client):
        """빈 문서 처리 테스트"""
        response = client.post("/api/v1/run", json={
            "document": "",
            "user_goal": "요약해주세요"
        })
        
        # 빈 문서도 요청은 받아들여짐
        assert response.status_code == 200
    
    def test_very_long_document(self, client):
        """매우 긴 문서 처리 테스트"""
        long_document = "테스트 문장입니다. " * 1000  # ~15000자
        
        response = client.post("/api/v1/run", json={
            "document": long_document,
            "user_goal": "요약"
        })
        
        assert response.status_code == 200
    
    def test_special_characters_in_document(self, client):
        """특수문자 포함 문서 처리 테스트"""
        response = client.post("/api/v1/run", json={
            "document": "테스트 <script>alert('XSS')</script> & 'quotes' \"double\"",
            "user_goal": "분석"
        })
        
        assert response.status_code == 200
    
    def test_unicode_document(self, client):
        """유니코드 문서 처리 테스트"""
        response = client.post("/api/v1/run", json={
            "document": "日本語 中文 한국어 العربية",
            "user_goal": "번역"
        })
        
        assert response.status_code == 200
    
    def test_concurrent_requests(self, client, sample_request_data):
        """동시 요청 처리 테스트"""
        run_ids = []
        
        # 여러 요청 동시 전송
        for i in range(3):
            response = client.post("/api/v1/run", json=sample_request_data)
            assert response.status_code == 200
            run_ids.append(response.json()["run_id"])
        
        # 모든 run_id가 고유한지 확인
        assert len(run_ids) == len(set(run_ids))


# ============= Swagger 문서 테스트 =============

class TestSwaggerDocs:
    """Swagger 문서 테스트"""
    
    def test_swagger_ui_accessible(self, client):
        """Swagger UI 접근 테스트"""
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_openapi_json_accessible(self, client):
        """OpenAPI JSON 스키마 접근 테스트"""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "/api/v1/run" in data["paths"]
    
    def test_redoc_accessible(self, client):
        """ReDoc 접근 테스트"""
        response = client.get("/redoc")
        
        assert response.status_code == 200


# ============= 응답 형식 검증 테스트 =============

class TestResponseFormat:
    """응답 형식 검증 테스트"""
    
    def test_run_response_format(self, client, sample_request_data):
        """파이프라인 실행 응답 형식 테스트"""
        response = client.post("/api/v1/run", json=sample_request_data)
        
        data = response.json()
        
        # 필수 필드 확인
        assert "run_id" in data
        assert "status" in data
        assert "message" in data
        
        # 타입 확인
        assert isinstance(data["run_id"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
    
    def test_status_response_format(self, client):
        """상태 조회 응답 형식 테스트"""
        test_run_id = "test_format_001"
        pipeline_status[test_run_id] = {
            "status": "running",
            "current_step": 2,
            "timestamp": "2024-01-01T00:00:00"
        }
        
        response = client.get(f"/api/v1/status/{test_run_id}")
        data = response.json()
        
        # 필수 필드 확인
        assert "run_id" in data
        assert "status" in data
        assert "current_step" in data
        assert "total_steps" in data
    
    def test_result_response_format(self, client):
        """결과 조회 응답 형식 테스트"""
        test_run_id = "test_format_002"
        pipeline_status[test_run_id] = {
            "status": "completed",
            "current_step": 4,
            "result": {
                "summary": "요약",
                "key_points": [],
                "action_items": []
            }
        }
        
        response = client.get(f"/api/v1/result/{test_run_id}")
        data = response.json()
        
        # 필수 필드 확인
        assert "run_id" in data
        assert "status" in data
        assert "result" in data or "error" in data


# ============= 실제 파이프라인 통합 테스트 (선택적) =============

@pytest.mark.skipif(
    os.environ.get("OPENAI_API_KEY") is None,
    reason="OPENAI_API_KEY가 설정되지 않음"
)
class TestFullIntegration:
    """실제 파이프라인 통합 테스트 (API 키 필요)"""
    
    def test_full_pipeline_flow(self, client, sample_request_data):
        """전체 파이프라인 흐름 테스트"""
        # 1. 파이프라인 실행
        run_response = client.post("/api/v1/run", json=sample_request_data)
        assert run_response.status_code == 200
        run_id = run_response.json()["run_id"]
        
        # 2. 완료될 때까지 상태 확인 (최대 60초)
        max_wait = 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/api/v1/status/{run_id}")
            status = status_response.json()["status"]
            
            if status == "completed":
                break
            elif status == "failed":
                pytest.fail("파이프라인 실행 실패")
            
            time.sleep(2)
        
        # 3. 결과 확인
        result_response = client.get(f"/api/v1/result/{run_id}")
        assert result_response.status_code == 200
        
        result = result_response.json()
        assert result["status"] == "completed"
        assert result["result"] is not None
        assert "summary" in result["result"]


# ============= 실행 =============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
