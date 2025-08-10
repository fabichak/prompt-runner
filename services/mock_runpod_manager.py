"""
Mock RunPod Manager for dry-run mode - simulates all RunPod operations
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class MockRunPodManager:
    """Mock RunPod manager that simulates all RunPod operations"""
    
    @staticmethod
    def get_pod_id() -> Optional[str]:
        """Simulate getting the current RunPod instance ID"""
        # Return a fake pod ID for simulation
        pod_id = "dry-run-pod-12345"
        logger.info(f"🎭 [DRY-RUN] Simulated RunPod ID: {pod_id}")
        return pod_id
    
    @staticmethod
    def shutdown_instance(force: bool = False) -> bool:
        """Simulate shutting down the RunPod instance"""
        try:
            pod_id = MockRunPodManager.get_pod_id()
            
            if not force:
                logger.info("🔌 [DRY-RUN] Shutdown requested but not forced, skipping...")
                return False
            
            logger.info(f"🔌 [DRY-RUN] Simulating shutdown of RunPod instance {pod_id}")
            logger.info("💤 [DRY-RUN] RunPod instance shutdown simulation completed")
            return True
                
        except Exception as e:
            logger.error(f"[DRY-RUN] Error simulating instance shutdown: {e}")
            return False
    
    @staticmethod
    def check_instance_health() -> bool:
        """Simulate checking if the RunPod instance is healthy"""
        try:
            # Simulate health metrics
            simulated_metrics = {
                "cpu_percent": 15.5,
                "memory_percent": 45.2,
                "disk_percent": 32.1,
                "status": "healthy"
            }
            
            logger.info(f"💓 [DRY-RUN] Simulated system health - "
                       f"CPU: {simulated_metrics['cpu_percent']}%, "
                       f"RAM: {simulated_metrics['memory_percent']}%, "
                       f"Disk: {simulated_metrics['disk_percent']}%")
            
            # Always return healthy in dry-run mode
            return True
            
        except Exception as e:
            logger.error(f"[DRY-RUN] Error simulating health check: {e}")
            return True
    
    @staticmethod
    def get_instance_info() -> dict:
        """Simulate getting information about the RunPod instance"""
        simulated_info = {
            'pod_id': 'dry-run-pod-12345',
            'pod_hostname': 'dry-run-host.runpod.io',
            'gpu_count': '1',
            'cpu_count': '8',
            'mem_gb': '32',
            'public_ip': '203.0.113.1',  # Example IP (TEST-NET-3)
            'api_key': 'SIMULATED'
        }
        
        logger.info(f"ℹ️ [DRY-RUN] Simulated RunPod instance info: {simulated_info}")
        return simulated_info