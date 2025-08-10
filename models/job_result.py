"""Job result tracking model"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class JobResult:
    """Tracks the result of a job execution"""
    job_id: str
    job_type: str  # "render" or "combine"
    success: bool = False
    
    # Output paths
    output_path: Optional[str] = None
    latent_path: Optional[str] = None
    reference_path: Optional[str] = None
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Error tracking
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool, error_message: Optional[str] = None):
        """Mark job as complete"""
        self.success = success
        self.end_time = datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        if error_message:
            self.error_message = error_message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'success': self.success,
            'output_path': self.output_path,
            'latent_path': self.latent_path,
            'reference_path': self.reference_path,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'error_details': self.error_details,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"JobResult({self.job_id}: {status}, {self.duration_seconds:.1f}s)"