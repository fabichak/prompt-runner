"""
Service factory for dependency injection
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating service instances"""
    
    @staticmethod
    def create_comfyui_client(server_address: str = None) -> Any:
        """Create ComfyUI client"""
        from services.comfyui_client import ComfyUIClient
        return ComfyUIClient(server_address)
    
    @staticmethod
    def create_storage_manager() -> Any:
        """Create storage manager"""
        from services.storage_utils import StorageManager
        return StorageManager()
    
    @staticmethod
    def create_runpod_manager() -> Any:
        """Create RunPod manager"""
        from services.runpod_utils import RunPodManager
        return RunPodManager()
    
    @staticmethod
    def create_workflow_manager(base_workflow_path, combine_workflow_path) -> Any:
        """Create workflow manager"""
        from services.workflow_manager import WorkflowManager
        return WorkflowManager(base_workflow_path, combine_workflow_path)