"""Base job model providing common interface for all job types"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BaseJob(ABC):
    """Common interface for all job types"""
    job_id: str
    card_id: str  # Trello card ID for API tracking
    mode: str  # 'v2v', 'i2i', future: 't2i', 'a2v'
    status: JobStatus = field(default=JobStatus.PENDING, init=False)
    error_message: Optional[str] = field(default=None, init=False)

    @abstractmethod
    def to_workflow_params(self) -> Dict[str, Any]:
        """Get parameters for workflow modification"""
        pass

    @classmethod
    @abstractmethod
    def from_api_data(cls, api_data: Dict[str, Any]) -> 'BaseJob':
        """Create job from API response data"""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate job parameters"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'job_id': self.job_id,
            'card_id': self.card_id,
            'mode': self.mode,
            'status': self.status.value,
            'error_message': self.error_message
        }