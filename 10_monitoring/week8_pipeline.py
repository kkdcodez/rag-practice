"""
Week 8 Pipeline Module
8주차 파이프라인 코드를 API에서 사용할 수 있도록 정리
"""

import os
import json
import pickle
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ============= 데이터 클래스 =============
@dataclass
class StepResult:
    """각 Step의 결과를 저장하는 클래스"""
    step: int
    step_name: str
    result: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class Checkpoint:
    """체크포인트 정보를 저장하는 클래스"""
    run_id: str
    completed_step: int
    user_goal: str
    intermediate_results: List[str]
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class Request:
    """사용자 요청을 저장하는 클래스"""
    id: str
    user_goal: str
    document: str
    status: str = "pending"
    
    def __post_init__(self):
        if self.id is None:
            self.id = f"req_{uuid.uuid4().hex[:8]}"

# ============= 파일 매니저 =============
class FileManager:
    """파일 저장 및 체크포인트 관리 클래스"""
    
    def __init__(self, base_dir: str = "runs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
    def save_step_result(self, run_id: str, step_result: StepResult):
        """Step 결과를 파일로 저장"""
        run_dir = self.base_dir / run_id
        run_dir.mkdir(exist_ok=True)
        
        filename = f"step_{step_result.step:02d}.json"
        filepath = run_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(step_result), f, ensure_ascii=False, indent=2)
        
        print(f"  💾 저장됨: {filepath}")
        return str(filename)
    
    def save_checkpoint(self, run_id: str, checkpoint: Checkpoint):
        """체크포인트 저장"""
        checkpoint_dir = self.base_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        
        filepath = checkpoint_dir / f"{run_id}_checkpoint.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(checkpoint), f, ensure_ascii=False, indent=2)
        
        print(f"  🔖 체크포인트 저장됨: {filepath}")
        return str(filepath)
    
    def load_checkpoint(self, run_id: str) -> Optional[Checkpoint]:
        """체크포인트 불러오기"""
        checkpoint_path = self.base_dir / "checkpoints" / f"{run_id}_checkpoint.json"
        
        if not checkpoint_path.exists():
            print(f"  ❌ 체크포인트를 찾을 수 없습니다: {run_id}")
            return None
        
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        checkpoint = Checkpoint(**data)
        print(f"  ✅ 체크포인트 로드됨: Step {checkpoint.completed_step}까지 완료")
        return checkpoint
    
    def load_step_result(self, run_id: str, step: int) -> Optional[StepResult]:
        """특정 Step 결과 불러오기"""
        filepath = self.base_dir / run_id / f"step_{step:02d}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return StepResult(**data)
    
    def save_final_result(self, run_id: str, result: dict):
        """최종 결과 저장 (JSON 형식)"""
        run_dir = self.base_dir / run_id
        filepath = run_dir / "final_output.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"  📄 최종 결과 저장됨: {filepath}")
        
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

# ============= 문서 파이프라인 =============
class DocumentPipeline:
    """문서 처리 파이프라인"""
    
    def __init__(self):
        # LLM 초기화 (API 키는 환경변수에서)
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7
        )
        self.stop_flag = False
        self.current_run_id = None
        self.checkpoint = None
        
    def step1_plan(self, user_goal: str, document: str) -> StepResult:
        """Step 1: 계획 세우기"""
        print("\n🔍 Step 1: 계획 세우기...")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 문서 분석 전문가입니다. 사용자의 요청을 분석하여 작업 계획을 세워주세요."),
            ("human", """
            사용자 요청: {user_goal}
            문서 길이: {doc_length}자
            
            이 작업을 수행하기 위한 간단한 계획을 3-4줄로 작성해주세요.
            """)
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                user_goal=user_goal,
                doc_length=len(document)
            )
        )
        
        return StepResult(
            step=1,
            step_name="계획 세우기",
            result=response.content
        )
    
    def step2_read(self, document: str, plan: str) -> StepResult:
        """Step 2: 입력 읽기"""
        print("\n📖 Step 2: 입력 읽기...")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "문서에서 핵심 정보를 추출하는 전문가입니다."),
            ("human", """
            계획: {plan}
            
            문서:
            {document}
            
            위 문서에서 핵심 포인트 5개를 추출해주세요.
            """)
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                plan=plan,
                document=document[:2000]  # 문서가 너무 길면 앞부분만
            )
        )
        
        return StepResult(
            step=2,
            step_name="입력 읽기",
            result=response.content
        )
    
    def step3_draft(self, key_points: str, user_goal: str) -> StepResult:
        """Step 3: 초안 만들기"""
        print("\n✍️ Step 3: 초안 만들기...")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "요약 초안을 작성하는 전문가입니다."),
            ("human", """
            사용자 요청: {user_goal}
            핵심 포인트:
            {key_points}
            
            위 정보를 바탕으로 200자 내외의 요약 초안을 작성해주세요.
            """)
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                user_goal=user_goal,
                key_points=key_points
            )
        )
        
        return StepResult(
            step=3,
            step_name="초안 만들기",
            result=response.content
        )
    
    def step4_finalize(self, draft: str, key_points: str) -> StepResult:
        """Step 4: 최종 정리"""
        print("\n🎯 Step 4: 최종 정리...")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "최종 결과를 정리하는 전문가입니다."),
            ("human", """
            초안: {draft}
            핵심 포인트: {key_points}
            
            최종 결과를 다음 형식으로 정리해주세요:
            
            [요약]
            (여기에 최종 요약)
            
            [핵심 포인트]
            • 포인트 1
            • 포인트 2
            • 포인트 3
            
            [액션 아이템]
            1. (담당자) - (할 일) - (기한)
            2. (담당자) - (할 일) - (기한)
            """)
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                draft=draft,
                key_points=key_points
            )
        )
        
        return StepResult(
            step=4,
            step_name="최종 정리",
            result=response.content
        )

# ============= 파이프라인 컨트롤러 =============
class PipelineController:
    """파이프라인을 제어하는 컨트롤러"""
    
    def __init__(self):
        self.pipeline = DocumentPipeline()
        self.file_manager = FileManager()
        self.stop_requested = False
        self.current_run_id = None
        
    def run(self, request: Request, status_callback=None) -> dict:
        """
        파이프라인 실행
        status_callback: 상태 업데이트 콜백 함수
        """
        self.current_run_id = request.id
        print(f"\n🚀 파이프라인 실행 시작: {self.current_run_id}")
        
        step_results = {}
        
        try:
            # Step 1: 계획 세우기
            if status_callback:
                status_callback(request.id, "running", 1)
            
            result1 = self.pipeline.step1_plan(request.user_goal, request.document)
            step_results[1] = result1
            self.file_manager.save_step_result(self.current_run_id, result1)
            
            # Step 2: 입력 읽기
            if status_callback:
                status_callback(request.id, "running", 2)
                
            plan = step_results[1].result
            result2 = self.pipeline.step2_read(request.document, plan)
            step_results[2] = result2
            self.file_manager.save_step_result(self.current_run_id, result2)
            
            # Step 3: 초안 만들기
            if status_callback:
                status_callback(request.id, "running", 3)
                
            key_points = step_results[2].result
            result3 = self.pipeline.step3_draft(key_points, request.user_goal)
            step_results[3] = result3
            self.file_manager.save_step_result(self.current_run_id, result3)
            
            # Step 4: 최종 정리
            if status_callback:
                status_callback(request.id, "running", 4)
                
            draft = step_results[3].result
            result4 = self.pipeline.step4_finalize(draft, key_points)
            step_results[4] = result4
            self.file_manager.save_step_result(self.current_run_id, result4)
            
            # 최종 결과 구조화
            final_result = self.parse_final_result(result4.result)
            self.file_manager.save_final_result(self.current_run_id, final_result)
            
            if status_callback:
                status_callback(request.id, "completed", 4, final_result)
            
            print("\n✅ 파이프라인 완료!")
            return final_result
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            if status_callback:
                status_callback(request.id, "failed", error=str(e))
            raise e
    
    def parse_final_result(self, text: str) -> dict:
        """최종 결과 텍스트를 구조화된 딕셔너리로 파싱"""
        # 간단한 파싱 (실제로는 더 정교하게)
        result = {
            "summary": "",
            "key_points": [],
            "action_items": []
        }
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if '[요약]' in line:
                current_section = 'summary'
            elif '[핵심 포인트]' in line:
                current_section = 'key_points'
            elif '[액션 아이템]' in line:
                current_section = 'action_items'
            elif line and current_section:
                if current_section == 'summary':
                    result['summary'] += line + ' '
                elif line.startswith('•') or line.startswith('-'):
                    result['key_points'].append(line[1:].strip())
                elif line[0].isdigit() and '.' in line:
                    result['action_items'].append(line)
        
        result['summary'] = result['summary'].strip()
        
        return result
