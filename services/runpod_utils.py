"""RunPod instance management utilities"""
import os
import subprocess
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _is_dry_run() -> bool:
    """Check if we're in dry-run mode"""
    try:
        from services.dry_run_manager import is_dry_run
        return is_dry_run()
    except ImportError:
        return os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')


class RunPodManager:
    """Handles RunPod instance lifecycle"""
    
    @staticmethod
    def get_pod_id() -> Optional[str]:
        """Get the current RunPod instance ID"""
        # In dry-run mode, return mock ID for any machine
        if _is_dry_run():
            logger.info("🎭 [DRY-RUN] Using mock RunPod ID for non-RunPod environment")
            return "dry-run-mock-pod-id"
            
        try:
            pod_id = os.environ.get('RUNPOD_POD_ID')
            if pod_id:
                logger.info(f"RunPod ID: {pod_id}")
                return pod_id
            else:
                logger.warning("RUNPOD_POD_ID environment variable not found")
                return None
        except Exception as e:
            logger.error(f"Error getting pod ID: {e}")
            return None
    
    @staticmethod
    def shutdown_instance(force: bool = False) -> bool:
        """Shutdown the RunPod instance"""
        # In dry-run mode, simulate shutdown
        if _is_dry_run():
            logger.info("🎭 [DRY-RUN] Simulating RunPod instance shutdown")
            if force:
                logger.info("🔌 [DRY-RUN] Force shutdown simulated successfully")
                return True
            else:
                logger.info("⏭️ [DRY-RUN] Shutdown requested but not forced, simulating skip")
                return False
        
        try:
            pod_id = RunPodManager.get_pod_id()
            if not pod_id:
                logger.warning("Cannot shutdown - no pod ID found")
                return False
            
            if not force:
                logger.info("Shutdown requested but not forced, skipping...")
                return False
            
            logger.info(f"Shutting down RunPod instance {pod_id}")
            
            # Use runpodctl to stop the pod
            cmd = ["runpodctl", "stop", "pod", pod_id]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("RunPod instance shutdown initiated")
                return True
            else:
                logger.error(f"Failed to shutdown: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error shutting down instance: {e}")
            return False
    
    @staticmethod
    def check_instance_health() -> bool:
        """Check if the RunPod instance is healthy"""
        # In dry-run mode, always return healthy
        if _is_dry_run():
            logger.info("🎭 [DRY-RUN] System health check bypassed - simulating healthy system")
            return True
        
        try:
            # Check if we're running on RunPod
            if not os.environ.get('RUNPOD_POD_ID'):
                logger.info("Not running on RunPod")
                return True  # Consider healthy if not on RunPod (local dev)
            
            # Check basic system resources
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            logger.info(f"System health - CPU: {cpu_percent}%, RAM: {memory.percent}%, Disk: {disk.percent}%")
            
            # Check if any critical thresholds are exceeded
            if cpu_percent > 95:
                logger.warning(f"High CPU usage: {cpu_percent}%")
                return False
            if memory.percent > 95:
                logger.warning(f"High memory usage: {memory.percent}%")
                return False
            if disk.percent > 95:
                logger.warning(f"High disk usage: {disk.percent}%")
                return False
            
            return True
            
        except ImportError:
            logger.warning("psutil not available for health check")
            return True
        except Exception as e:
            logger.error(f"Error checking instance health: {e}")
            return True
    
    @staticmethod
    def get_instance_info() -> Dict[str, Any]:
        """Get information about the RunPod instance"""
        # In dry-run mode, return mock data that works on any machine
        if _is_dry_run():
            import platform
            import socket
            
            mock_info = {
                'pod_id': 'dry-run-mock-pod-id',
                'pod_hostname': f'dry-run-{socket.gethostname()}',
                'gpu_count': 'DRY-RUN-MOCK',
                'cpu_count': str(os.cpu_count() or 'UNKNOWN'),
                'mem_gb': 'DRY-RUN-MOCK',
                'public_ip': '127.0.0.1',
                'api_key': 'DRY-RUN-MODE',
                'system_info': {
                    'platform': platform.system(),
                    'architecture': platform.machine(),
                    'python_version': platform.python_version(),
                    'hostname': socket.gethostname()
                },
                'dry_run_mode': True
            }
            
            logger.info(f"🎭 [DRY-RUN] Mock RunPod instance info: {mock_info}")
            return mock_info
        
        # Normal RunPod environment
        info = {
            'pod_id': os.environ.get('RUNPOD_POD_ID', 'N/A'),
            'pod_hostname': os.environ.get('RUNPOD_POD_HOSTNAME', 'N/A'),
            'gpu_count': os.environ.get('RUNPOD_GPU_COUNT', 'N/A'),
            'cpu_count': os.environ.get('RUNPOD_CPU_COUNT', 'N/A'),
            'mem_gb': os.environ.get('RUNPOD_MEM_GB', 'N/A'),
            'public_ip': os.environ.get('RUNPOD_PUBLIC_IP', 'N/A'),
            'api_key': 'SET' if os.environ.get('RUNPOD_API_KEY') else 'NOT SET',
            'dry_run_mode': False
        }
        
        logger.info(f"RunPod instance info: {info}")
        return info