"""
Service factory for dependency injection - returns real or mock implementations based on dry-run mode
"""
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating service instances with dry-run support"""
    
    @staticmethod
    def is_dry_run_mode() -> bool:
        """Check if we're in dry-run mode via environment variable or import"""
        try:
            from services.dry_run_manager import is_dry_run
            return is_dry_run() or os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')
        except ImportError:
            return os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')
    
    @staticmethod
    def create_comfyui_client(server_address: str = None) -> Any:
        """Create ComfyUI client - real or mock based on dry-run mode"""
        if ServiceFactory.is_dry_run_mode():
            from services.mock_comfyui_client import MockComfyUIClient
            logger.info("🎭 Creating MockComfyUIClient for dry-run mode")
            return MockComfyUIClient(server_address or "127.0.0.1:8188")
        else:
            from services.comfyui_client import ComfyUIClient
            return ComfyUIClient(server_address)
    
    @staticmethod
    def create_storage_manager() -> Any:
        """Create storage manager - real or mock based on dry-run mode"""
        if ServiceFactory.is_dry_run_mode():
            from services.mock_storage_manager import MockStorageManager
            logger.info("🗄️ Creating MockStorageManager for dry-run mode")
            return MockStorageManager()
        else:
            from services.storage_utils import StorageManager
            return StorageManager()
    
    @staticmethod
    def create_runpod_manager() -> Any:
        """Create RunPod manager - real or mock based on dry-run mode"""
        if ServiceFactory.is_dry_run_mode():
            from services.mock_runpod_manager import MockRunPodManager
            logger.info("🎭 Creating MockRunPodManager for dry-run mode")
            return MockRunPodManager()
        else:
            from services.runpod_utils import RunPodManager
            return RunPodManager()
    
    @staticmethod
    def create_workflow_manager(base_workflow_path, combine_workflow_path) -> Any:
        """Create workflow manager - always real since it doesn't have external dependencies"""
        from services.workflow_manager import WorkflowManager
        return WorkflowManager(base_workflow_path, combine_workflow_path)