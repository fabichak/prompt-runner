"""
Service factory for dependency injection
"""
import logging
from typing import Any

from services.comfyui_client import ComfyUIClient
from services.storage_utils import StorageManager
from services.workflow_manager import WorkflowManager

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating service instances"""
    
    @staticmethod
    def create_comfyui_client(server_address: str = None) -> ComfyUIClient:
        """Create ComfyUI client"""
        return ComfyUIClient(server_address)
    
    @staticmethod
    def create_storage_manager() -> StorageManager:
        """Create storage manager"""
        return StorageManager()
    
    @staticmethod
    def create_workflow_manager(base_workflow_path, combine_workflow_path) -> WorkflowManager:
        """Create workflow manager"""
        return WorkflowManager(base_workflow_path, combine_workflow_path)