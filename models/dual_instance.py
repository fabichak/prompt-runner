"""
Data models for dual ComfyUI instance job scheduling system
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from models.job import JobType


class InstanceStatus(Enum):
    """Status of a ComfyUI instance"""
    IDLE = "idle"
    BUSY = "busy" 
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ComfyUIInstanceConfig:
    """Configuration for a single ComfyUI instance"""
    instance_id: str
    host: str
    port: int
    job_types: List[str]  # ["HIGH"], ["LOW"], or ["HIGH", "LOW"]
    max_concurrent: int = 1
    enabled: bool = True
    status: InstanceStatus = InstanceStatus.IDLE
    
    @property
    def address(self) -> str:
        """Get the full address string"""
        return f"{self.host}:{self.port}"
    
    def can_handle_job_type(self, job_type) -> bool:
        """Check if this instance can handle the given job type"""
        if hasattr(job_type, 'value'):
            # JobType enum
            return job_type.value in self.job_types
        else:
            # String
            return str(job_type) in self.job_types
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'instance_id': self.instance_id,
            'host': self.host,
            'port': self.port,
            'job_types': self.job_types,
            'max_concurrent': self.max_concurrent,
            'enabled': self.enabled,
            'status': self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComfyUIInstanceConfig':
        """Create from dictionary"""
        return cls(
            instance_id=data.get('instance_id', ''),
            host=data.get('host', '127.0.0.1'),
            port=data.get('port', 8188),
            job_types=data.get('job_types', ['HIGH', 'LOW']),
            max_concurrent=data.get('max_concurrent', 1),
            enabled=data.get('enabled', True),
            status=InstanceStatus(data.get('status', 'idle'))
        )


@dataclass
class JobAssignment:
    """Represents a job assigned to a specific instance"""
    job_id: str
    job_type: JobType
    instance_id: str
    prompt_name: str
    assigned_at: float  # timestamp
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def is_running(self) -> bool:
        """Check if the job is currently running"""
        return self.started_at is not None and self.completed_at is None
    
    @property
    def is_completed(self) -> bool:
        """Check if the job is completed"""
        return self.completed_at is not None


@dataclass 
class InstanceMetrics:
    """Performance metrics for a ComfyUI instance"""
    instance_id: str
    jobs_completed: int = 0
    jobs_failed: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    uptime_percentage: float = 100.0
    last_job_time: Optional[float] = None
    
    def update_job_completion(self, execution_time: float, success: bool):
        """Update metrics after job completion"""
        if success:
            self.jobs_completed += 1
            self.total_execution_time += execution_time
            self.avg_execution_time = self.total_execution_time / max(1, self.jobs_completed)
        else:
            self.jobs_failed += 1
        
        import time
        self.last_job_time = time.time()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        total_jobs = self.jobs_completed + self.jobs_failed
        if total_jobs == 0:
            return 100.0
        return (self.jobs_completed / total_jobs) * 100.0


@dataclass
class DualInstanceState:
    """Overall state of the dual instance system"""
    instances: Dict[str, ComfyUIInstanceConfig]
    assignments: Dict[str, JobAssignment]  # job_id -> assignment
    metrics: Dict[str, InstanceMetrics]    # instance_id -> metrics
    high_jobs_pending: int = 0
    low_jobs_pending: int = 0
    combine_jobs_pending: int = 0
    combine_jobs_ready: bool = False
    
    def get_available_instance(self, job_type: JobType) -> Optional[ComfyUIInstanceConfig]:
        """Get an available instance that can handle the given job type"""
        for instance in self.instances.values():
            if (instance.enabled and 
                instance.status == InstanceStatus.IDLE and
                instance.can_handle_job_type(job_type)):
                return instance
        return None
    
    def mark_instance_busy(self, instance_id: str):
        """Mark an instance as busy"""
        if instance_id in self.instances:
            self.instances[instance_id].status = InstanceStatus.BUSY
    
    def mark_instance_idle(self, instance_id: str):
        """Mark an instance as idle"""
        if instance_id in self.instances:
            self.instances[instance_id].status = InstanceStatus.IDLE
    
    def can_start_combine_jobs(self) -> bool:
        """Check if all HIGH and LOW jobs are complete and COMBINE jobs can start"""
        return self.high_jobs_pending == 0 and self.low_jobs_pending == 0