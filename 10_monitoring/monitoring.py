"""
Week 10: 모니터링 시스템 (Monitoring System)
Part 3.1 - 품질 메트릭 추적
Part 3.2 - 경고 규칙 설정
Part 3.3 - A/B 테스트 구현 (선택)
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict, field
from collections import deque
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# LangSmith 설정
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "week10-monitoring"


# ============= 데이터 클래스 =============

@dataclass
class MetricRecord:
    """메트릭 기록"""
    timestamp: str
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class AlertRecord:
    """경고 기록"""
    timestamp: str
    alert_type: str
    severity: str  # info, warning, critical
    message: str
    metric_value: float
    threshold: float
    acknowledged: bool = False
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# ============= Part 3.1: 품질 메트릭 추적 =============

class QualityMetricsTracker:
    """품질 메트릭 추적 시스템"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = {
            "latency": deque(maxlen=window_size),
            "success_rate": deque(maxlen=window_size),
            "completeness_score": deque(maxlen=window_size),
            "relevance_score": deque(maxlen=window_size),
            "hallucination_rate": deque(maxlen=window_size),
            "token_usage": deque(maxlen=window_size),
        }
        self.run_history: List[Dict] = []
        self._lock = threading.Lock()
    
    def record_run(self, run_data: Dict):
        """파이프라인 실행 결과 기록"""
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            # 레이턴시 기록
            if "latency_ms" in run_data:
                self.metrics["latency"].append(
                    MetricRecord(timestamp, "latency", run_data["latency_ms"])
                )
            
            # 성공률 기록
            success = 1.0 if run_data.get("status") == "completed" else 0.0
            self.metrics["success_rate"].append(
                MetricRecord(timestamp, "success_rate", success)
            )
            
            # 완성도 점수
            if "completeness_score" in run_data:
                self.metrics["completeness_score"].append(
                    MetricRecord(timestamp, "completeness_score", run_data["completeness_score"])
                )
            
            # 관련성 점수
            if "relevance_score" in run_data:
                self.metrics["relevance_score"].append(
                    MetricRecord(timestamp, "relevance_score", run_data["relevance_score"])
                )
            
            # 환각률
            if "has_hallucination" in run_data:
                hallucination = 1.0 if run_data["has_hallucination"] else 0.0
                self.metrics["hallucination_rate"].append(
                    MetricRecord(timestamp, "hallucination_rate", hallucination)
                )
            
            # 토큰 사용량
            if "token_usage" in run_data:
                self.metrics["token_usage"].append(
                    MetricRecord(timestamp, "token_usage", run_data["token_usage"])
                )
            
            # 실행 이력 저장
            self.run_history.append({
                "timestamp": timestamp,
                **run_data
            })
    
    def get_metric_stats(self, metric_name: str) -> Dict:
        """특정 메트릭의 통계 조회"""
        with self._lock:
            if metric_name not in self.metrics:
                return {"error": f"Unknown metric: {metric_name}"}
            
            records = list(self.metrics[metric_name])
            if not records:
                return {"count": 0, "avg": None, "min": None, "max": None}
            
            values = [r.value for r in records]
            return {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "latest": values[-1] if values else None
            }
    
    def get_all_stats(self) -> Dict:
        """모든 메트릭 통계 조회"""
        return {
            name: self.get_metric_stats(name)
            for name in self.metrics.keys()
        }
    
    def get_recent_runs(self, n: int = 10) -> List[Dict]:
        """최근 실행 이력 조회"""
        with self._lock:
            return self.run_history[-n:]
    
    def export_metrics(self, filepath: str):
        """메트릭을 파일로 내보내기"""
        with self._lock:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "stats": self.get_all_stats(),
                "recent_runs": self.run_history[-50:]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"메트릭 내보내기 완료: {filepath}")


# ============= Part 3.2: 경고 규칙 설정 =============

class AlertRule:
    """경고 규칙"""
    
    def __init__(
        self,
        name: str,
        metric_name: str,
        condition: str,  # "gt", "lt", "gte", "lte", "eq"
        threshold: float,
        severity: str = "warning",
        cooldown_seconds: int = 300  # 같은 경고 재발생 방지 시간
    ):
        self.name = name
        self.metric_name = metric_name
        self.condition = condition
        self.threshold = threshold
        self.severity = severity
        self.cooldown_seconds = cooldown_seconds
        self.last_triggered: Optional[datetime] = None
    
    def check(self, value: float) -> bool:
        """조건 확인"""
        if self.condition == "gt":
            return value > self.threshold
        elif self.condition == "lt":
            return value < self.threshold
        elif self.condition == "gte":
            return value >= self.threshold
        elif self.condition == "lte":
            return value <= self.threshold
        elif self.condition == "eq":
            return value == self.threshold
        return False
    
    def should_alert(self, value: float) -> bool:
        """경고 발생 여부 확인 (쿨다운 포함)"""
        if not self.check(value):
            return False
        
        now = datetime.now()
        if self.last_triggered:
            elapsed = (now - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        
        self.last_triggered = now
        return True


class AlertManager:
    """경고 관리자"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alerts: List[AlertRecord] = []
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        # 기본 규칙 설정
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """기본 경고 규칙 설정"""
        default_rules = [
            # 레이턴시 경고
            AlertRule(
                name="high_latency",
                metric_name="latency",
                condition="gt",
                threshold=30000,  # 30초
                severity="warning"
            ),
            AlertRule(
                name="critical_latency",
                metric_name="latency",
                condition="gt",
                threshold=60000,  # 60초
                severity="critical"
            ),
            
            # 성공률 경고
            AlertRule(
                name="low_success_rate",
                metric_name="success_rate",
                condition="lt",
                threshold=0.9,  # 90% 미만
                severity="warning"
            ),
            AlertRule(
                name="critical_success_rate",
                metric_name="success_rate",
                condition="lt",
                threshold=0.7,  # 70% 미만
                severity="critical"
            ),
            
            # 완성도 경고
            AlertRule(
                name="low_completeness",
                metric_name="completeness_score",
                condition="lt",
                threshold=0.6,
                severity="warning"
            ),
            
            # 환각률 경고
            AlertRule(
                name="high_hallucination",
                metric_name="hallucination_rate",
                condition="gt",
                threshold=0.3,  # 30% 초과
                severity="critical"
            ),
            
            # 토큰 사용량 경고
            AlertRule(
                name="high_token_usage",
                metric_name="token_usage",
                condition="gt",
                threshold=10000,  # 10K 토큰
                severity="info"
            ),
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: AlertRule):
        """규칙 추가"""
        with self._lock:
            self.rules.append(rule)
    
    def add_callback(self, callback: Callable):
        """경고 발생 시 콜백 추가"""
        self.callbacks.append(callback)
    
    def check_metrics(self, metrics_tracker: QualityMetricsTracker):
        """메트릭 확인 및 경고 발생"""
        with self._lock:
            stats = metrics_tracker.get_all_stats()
            
            for rule in self.rules:
                if rule.metric_name not in stats:
                    continue
                
                metric_stats = stats[rule.metric_name]
                if metric_stats["latest"] is None:
                    continue
                
                value = metric_stats["latest"]
                
                if rule.should_alert(value):
                    alert = AlertRecord(
                        timestamp=datetime.now().isoformat(),
                        alert_type=rule.name,
                        severity=rule.severity,
                        message=f"{rule.metric_name} {rule.condition} {rule.threshold}: 현재값 {value:.2f}",
                        metric_value=value,
                        threshold=rule.threshold
                    )
                    
                    self.alerts.append(alert)
                    self._notify(alert)
    
    def _notify(self, alert: AlertRecord):
        """경고 알림"""
        # 콘솔 출력
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }
        emoji = severity_emoji.get(alert.severity, "📢")
        
        print(f"\n{emoji} [{alert.severity.upper()}] {alert.alert_type}")
        print(f"   {alert.message}")
        print(f"   시간: {alert.timestamp}")
        
        # 콜백 실행
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"콜백 실행 오류: {e}")
    
    def get_alerts(self, severity: str = None, limit: int = 50) -> List[Dict]:
        """경고 조회"""
        with self._lock:
            alerts = self.alerts[-limit:]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            return [asdict(a) for a in alerts]
    
    def acknowledge_alert(self, index: int):
        """경고 확인 처리"""
        with self._lock:
            if 0 <= index < len(self.alerts):
                self.alerts[index].acknowledged = True
    
    def export_alerts(self, filepath: str):
        """경고 내보내기"""
        with self._lock:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "total_alerts": len(self.alerts),
                "alerts": [asdict(a) for a in self.alerts[-100:]]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"경고 내보내기 완료: {filepath}")


# ============= Part 3.3: A/B 테스트 (선택) =============

@dataclass
class ABTestVariant:
    """A/B 테스트 변형"""
    name: str
    config: Dict[str, Any]
    weight: float = 0.5  # 트래픽 비율


class ABTestManager:
    """A/B 테스트 관리자"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.variants: List[ABTestVariant] = []
        self.results: Dict[str, List[Dict]] = {}
        self._lock = threading.Lock()
    
    def add_variant(self, variant: ABTestVariant):
        """변형 추가"""
        with self._lock:
            self.variants.append(variant)
            self.results[variant.name] = []
    
    def select_variant(self) -> ABTestVariant:
        """변형 선택 (가중치 기반)"""
        import random
        
        with self._lock:
            if not self.variants:
                raise ValueError("No variants configured")
            
            # 가중치 기반 선택
            total_weight = sum(v.weight for v in self.variants)
            r = random.uniform(0, total_weight)
            
            cumulative = 0
            for variant in self.variants:
                cumulative += variant.weight
                if r <= cumulative:
                    return variant
            
            return self.variants[-1]
    
    def record_result(self, variant_name: str, result: Dict):
        """결과 기록"""
        with self._lock:
            if variant_name not in self.results:
                self.results[variant_name] = []
            
            self.results[variant_name].append({
                "timestamp": datetime.now().isoformat(),
                **result
            })
    
    def get_stats(self) -> Dict:
        """변형별 통계"""
        with self._lock:
            stats = {}
            
            for variant_name, results in self.results.items():
                if not results:
                    stats[variant_name] = {"count": 0}
                    continue
                
                # 성공률 계산
                success_count = sum(1 for r in results if r.get("success", False))
                success_rate = success_count / len(results) if results else 0
                
                # 평균 점수 계산
                scores = [r.get("score", 0) for r in results if "score" in r]
                avg_score = sum(scores) / len(scores) if scores else 0
                
                # 평균 레이턴시
                latencies = [r.get("latency_ms", 0) for r in results if "latency_ms" in r]
                avg_latency = sum(latencies) / len(latencies) if latencies else 0
                
                stats[variant_name] = {
                    "count": len(results),
                    "success_rate": success_rate,
                    "avg_score": avg_score,
                    "avg_latency_ms": avg_latency
                }
            
            return stats
    
    def get_winner(self) -> Optional[str]:
        """승자 결정 (통계적 유의성 확인은 간소화)"""
        stats = self.get_stats()
        
        if not stats:
            return None
        
        # 최소 샘플 수 확인
        min_samples = 30
        valid_variants = {
            name: s for name, s in stats.items()
            if s["count"] >= min_samples
        }
        
        if not valid_variants:
            return None
        
        # 성공률 기준 승자
        winner = max(valid_variants.items(), key=lambda x: x[1]["success_rate"])
        return winner[0]


# ============= 통합 모니터링 시스템 =============

class MonitoringSystem:
    """통합 모니터링 시스템"""
    
    def __init__(self, output_dir: str = "monitoring_output"):
        self.metrics_tracker = QualityMetricsTracker()
        self.alert_manager = AlertManager()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 주기적 체크 스레드
        self._check_interval = 60  # 초
        self._running = False
        self._check_thread = None
    
    def record_pipeline_run(
        self,
        run_id: str,
        status: str,
        latency_ms: float,
        evaluation_result: Dict = None
    ):
        """파이프라인 실행 기록"""
        run_data = {
            "run_id": run_id,
            "status": status,
            "latency_ms": latency_ms
        }
        
        if evaluation_result:
            run_data.update({
                "completeness_score": evaluation_result.get("evaluations", {}).get("completeness", {}).get("score", 0),
                "relevance_score": evaluation_result.get("evaluations", {}).get("relevance", {}).get("score", 0),
                "has_hallucination": evaluation_result.get("evaluations", {}).get("hallucination", {}).get("has_hallucination", False),
            })
        
        self.metrics_tracker.record_run(run_data)
        self.alert_manager.check_metrics(self.metrics_tracker)
    
    def start_monitoring(self):
        """모니터링 시작"""
        if self._running:
            return
        
        self._running = True
        self._check_thread = threading.Thread(target=self._periodic_check)
        self._check_thread.daemon = True
        self._check_thread.start()
        print("모니터링 시작됨")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
        print("모니터링 중지됨")
    
    def _periodic_check(self):
        """주기적 체크"""
        while self._running:
            self.alert_manager.check_metrics(self.metrics_tracker)
            time.sleep(self._check_interval)
    
    def get_dashboard_data(self) -> Dict:
        """대시보드 데이터"""
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics_tracker.get_all_stats(),
            "recent_runs": self.metrics_tracker.get_recent_runs(10),
            "recent_alerts": self.alert_manager.get_alerts(limit=10)
        }
    
    def export_all(self):
        """모든 데이터 내보내기"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 메트릭 내보내기
        metrics_file = self.output_dir / f"metrics_{timestamp}.json"
        self.metrics_tracker.export_metrics(str(metrics_file))
        
        # 경고 내보내기
        alerts_file = self.output_dir / f"alerts_{timestamp}.json"
        self.alert_manager.export_alerts(str(alerts_file))
        
        # 대시보드 데이터
        dashboard_file = self.output_dir / f"dashboard_{timestamp}.json"
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            json.dump(self.get_dashboard_data(), f, ensure_ascii=False, indent=2)
        
        print(f"\n모든 데이터 내보내기 완료: {self.output_dir}")


# ============= 메인 실행 =============

if __name__ == "__main__":
    print("=" * 60)
    print("Week 10: 모니터링 시스템 테스트")
    print("=" * 60)
    
    # 모니터링 시스템 초기화
    monitoring = MonitoringSystem()
    
    # 테스트 데이터 기록
    print("\n[1] 테스트 데이터 기록")
    
    test_runs = [
        {"run_id": "test_001", "status": "completed", "latency_ms": 5000},
        {"run_id": "test_002", "status": "completed", "latency_ms": 8000},
        {"run_id": "test_003", "status": "failed", "latency_ms": 35000},  # 경고 발생
        {"run_id": "test_004", "status": "completed", "latency_ms": 6000},
        {"run_id": "test_005", "status": "completed", "latency_ms": 7000},
    ]
    
    for run in test_runs:
        monitoring.record_pipeline_run(
            run_id=run["run_id"],
            status=run["status"],
            latency_ms=run["latency_ms"]
        )
        print(f"  기록됨: {run['run_id']}")
    
    # 통계 확인
    print("\n[2] 메트릭 통계")
    stats = monitoring.metrics_tracker.get_all_stats()
    for metric, stat in stats.items():
        if stat["count"] > 0:
            print(f"  {metric}: avg={stat['avg']:.2f}, count={stat['count']}")
    
    # 경고 확인
    print("\n[3] 발생한 경고")
    alerts = monitoring.alert_manager.get_alerts()
    if alerts:
        for alert in alerts:
            print(f"  [{alert['severity']}] {alert['alert_type']}: {alert['message']}")
    else:
        print("  발생한 경고 없음")
    
    # 데이터 내보내기
    print("\n[4] 데이터 내보내기")
    monitoring.export_all()
    
    print("\n모니터링 시스템 테스트 완료!")
