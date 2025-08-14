#!/usr/bin/env python3
"""
Test script for dual ComfyUI instance system
Tests job queue management, instance coordination, and execution flow
"""
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from models.job import RenderJob, CombineJob, JobType, JobStatus
from models.dual_instance import ComfyUIInstanceConfig, InstanceStatus
from services.job_queue_manager import JobQueueManager
from services.multi_instance_client import MultiInstanceComfyUIClient
from services.dual_instance_orchestrator import DualInstanceOrchestrator
from config import COMFYUI_INSTANCES

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_jobs(prompt_name: str, job_count: int = 4) -> tuple:
    """Create test render and combine jobs"""
    render_jobs = []
    combine_jobs = []
    
    # Create alternating HIGH and LOW jobs
    for i in range(job_count):
        job_type = JobType.HIGH if i % 2 == 0 else JobType.LOW
        
        render_job = RenderJob(
            job_type=job_type,
            job_number=i + 1,
            start_frame=i * 100,
            frames_to_render=100,
            video_name=f"test_video_{i+1}",
            prompt_name=prompt_name,
            positive_prompt="test prompt",
            negative_prompt="test negative"
        )
        render_jobs.append(render_job)
    
    # Create a couple of combine jobs
    for i in range(2):
        combine_job = CombineJob(
            combine_number=i + 1,
            video_name=f"combined_{i+1}",
            prompt_name=prompt_name,
            input_video_path=f"/test/video_{i+1}.mp4",
            output_path=f"/test/combined_{i+1}.mp4"
        )
        combine_jobs.append(combine_job)
    
    return render_jobs, combine_jobs


def test_job_queue_manager():
    """Test the JobQueueManager functionality"""
    logger.info("Testing JobQueueManager...")
    
    # Create test instance configs
    configs = [
        ComfyUIInstanceConfig(
            instance_id="high_priority",
            host="127.0.0.1",
            port=8188,
            job_types=["HIGH"],
            enabled=True
        ),
        ComfyUIInstanceConfig(
            instance_id="low_priority", 
            host="127.0.0.1",
            port=8189,
            job_types=["LOW"],
            enabled=True
        )
    ]
    
    queue_manager = JobQueueManager(configs)
    
    # Create test jobs
    render_jobs, combine_jobs = create_test_jobs("test_prompt", 6)
    
    # Add jobs to queue
    queue_manager.add_jobs_for_prompt(render_jobs, combine_jobs, "test_prompt")
    
    # Check queue status
    status = queue_manager.get_queue_status()
    logger.info(f"Queue status: {status}")
    
    assert status["high_pending"] == 3, f"Expected 3 HIGH jobs, got {status['high_pending']}"
    assert status["low_pending"] == 3, f"Expected 3 LOW jobs, got {status['low_pending']}"
    assert status["combine_pending"] == 2, f"Expected 2 COMBINE jobs, got {status['combine_pending']}"
    
    # Test job retrieval
    high_job_data = queue_manager.get_next_job("high_priority")
    assert high_job_data is not None, "Should get a HIGH job"
    job, prompt_name = high_job_data
    assert job.job_type == JobType.HIGH, f"Expected HIGH job, got {job.job_type}"
    
    low_job_data = queue_manager.get_next_job("low_priority")
    assert low_job_data is not None, "Should get a LOW job"
    job, prompt_name = low_job_data
    assert job.job_type == JobType.LOW, f"Expected LOW job, got {job.job_type}"
    
    # Test that combine jobs are not ready yet
    combine_job_data = queue_manager.get_next_combine_job()
    assert combine_job_data is None, "COMBINE jobs should not be ready yet"
    
    logger.info("✅ JobQueueManager tests passed")


def test_multi_instance_client():
    """Test the MultiInstanceComfyUIClient functionality"""
    logger.info("Testing MultiInstanceComfyUIClient...")
    
    # Create test configs (won't actually connect to ComfyUI)
    configs = [ComfyUIInstanceConfig.from_dict(cfg) for cfg in COMFYUI_INSTANCES]
    
    multi_client = MultiInstanceComfyUIClient(configs)
    
    # Test configuration
    assert len(multi_client.configs) == len(configs), "Should have all configured instances"
    
    # Test instance lookup
    high_instances = multi_client.get_available_instances("HIGH")
    low_instances = multi_client.get_available_instances("LOW")
    
    logger.info(f"Instances that can handle HIGH jobs: {high_instances}")
    logger.info(f"Instances that can handle LOW jobs: {low_instances}")
    
    # Test status summary
    status = multi_client.get_status_summary()
    logger.info(f"Status summary: {status}")
    
    logger.info("✅ MultiInstanceComfyUIClient tests passed")


def test_dual_instance_orchestrator():
    """Test the DualInstanceOrchestrator functionality"""
    logger.info("Testing DualInstanceOrchestrator...")
    
    orchestrator = DualInstanceOrchestrator()
    
    # Check that orchestrator initialized correctly
    assert orchestrator.dual_mode in [True, False], "Dual mode should be set"
    assert len(orchestrator.instance_configs) > 0, "Should have at least one instance"
    
    # Test status retrieval
    status = orchestrator.get_execution_status()
    logger.info(f"Orchestrator status: {status}")
    
    logger.info("✅ DualInstanceOrchestrator tests passed")


def test_job_synchronization():
    """Test job synchronization logic"""
    logger.info("Testing job synchronization...")
    
    configs = [
        ComfyUIInstanceConfig(
            instance_id="high_priority",
            host="127.0.0.1", 
            port=8188,
            job_types=["HIGH"],
            enabled=True
        ),
        ComfyUIInstanceConfig(
            instance_id="low_priority",
            host="127.0.0.1",
            port=8189,
            job_types=["LOW"],
            enabled=True
        )
    ]
    
    queue_manager = JobQueueManager(configs)
    
    # Add jobs for multiple prompts
    for prompt_num in range(2):
        prompt_name = f"prompt_{prompt_num}"
        render_jobs, combine_jobs = create_test_jobs(prompt_name, 4)
        queue_manager.add_jobs_for_prompt(render_jobs, combine_jobs, prompt_name)
    
    # Simulate job completion
    total_high = queue_manager.state.high_jobs_pending
    total_low = queue_manager.state.low_jobs_pending
    
    logger.info(f"Total jobs: HIGH={total_high}, LOW={total_low}")
    
    # Complete all HIGH and LOW jobs
    for i in range(total_high):
        job_data = queue_manager.get_next_job("high_priority")
        if job_data:
            job, prompt_name = job_data
            queue_manager.mark_job_started(job.job_id)
            queue_manager.mark_job_completed(job.job_id, True, 5.0)
    
    for i in range(total_low):
        job_data = queue_manager.get_next_job("low_priority")
        if job_data:
            job, prompt_name = job_data
            queue_manager.mark_job_started(job.job_id)
            queue_manager.mark_job_completed(job.job_id, True, 5.0)
    
    # Now combine jobs should be ready
    status = queue_manager.get_queue_status()
    logger.info(f"Status after completing render jobs: {status}")
    
    # Test combine job retrieval
    combine_job_data = queue_manager.get_next_combine_job()
    assert combine_job_data is not None, "COMBINE jobs should be ready now"
    
    logger.info("✅ Job synchronization tests passed")


def main():
    """Run all tests"""
    logger.info("Starting dual instance system tests...")
    
    try:
        test_job_queue_manager()
        test_multi_instance_client()
        test_dual_instance_orchestrator()
        test_job_synchronization()
        
        logger.info("🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)