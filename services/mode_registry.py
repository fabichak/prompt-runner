"""Mode registry for job types and workflow managers"""
from typing import Dict, Type, Tuple
import logging

from models.base_job import BaseJob
from models.v2v_job import V2VJob
from models.i2i_job import I2IJob
from services.workflows.base_workflow import BaseWorkflowManager
from services.workflows.v2v_workflow import V2VWorkflowManager
from services.workflows.i2i_workflow import I2IWorkflowManager

logger = logging.getLogger(__name__)


class ModeRegistry:
    """Registry for job modes and their components"""

    _modes: Dict[str, Tuple[Type[BaseJob], Type[BaseWorkflowManager]]] = {}

    @classmethod
    def register(cls, mode: str, job_class: Type[BaseJob],
                 workflow_manager: Type[BaseWorkflowManager]) -> None:
        """Register a new mode with its job class and workflow manager"""
        cls._modes[mode] = (job_class, workflow_manager)
        logger.info(f"Registered mode '{mode}' with {job_class.__name__} and {workflow_manager.__name__}")

    @classmethod
    def get_job_class(cls, mode: str) -> Type[BaseJob]:
        """Get job class for a specific mode"""
        if mode not in cls._modes:
            raise ValueError(f"Unknown mode: {mode}. Available modes: {list(cls._modes.keys())}")
        return cls._modes[mode][0]

    @classmethod
    def get_workflow_manager(cls, mode: str) -> BaseWorkflowManager:
        """Get workflow manager instance for a specific mode"""
        if mode not in cls._modes:
            raise ValueError(f"Unknown mode: {mode}. Available modes: {list(cls._modes.keys())}")
        workflow_manager_class = cls._modes[mode][1]
        return workflow_manager_class()

    @classmethod
    def get_available_modes(cls) -> list[str]:
        """Get list of all registered modes"""
        return list(cls._modes.keys())

    @classmethod
    def is_mode_registered(cls, mode: str) -> bool:
        """Check if a mode is registered"""
        return mode in cls._modes


# Register built-in modes
ModeRegistry.register('v2v', V2VJob, V2VWorkflowManager)
ModeRegistry.register('i2i', I2IJob, I2IWorkflowManager)

logger.info(f"Mode registry initialized with modes: {ModeRegistry.get_available_modes()}")