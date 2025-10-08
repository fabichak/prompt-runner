"""Base workflow manager providing common interface for all workflow types"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import json
import logging
from pathlib import Path

from models.base_job import BaseJob

logger = logging.getLogger(__name__)


class BaseWorkflowManager(ABC):
    """Base class for all workflow managers"""

    def __init__(self):
        """Initialize workflow manager"""
        self.base_workflow = None
        self._load_workflow()

    @abstractmethod
    def get_workflow_file(self) -> str:
        """Returns path to workflow JSON file"""
        pass

    @abstractmethod
    def modify_workflow(self, job: BaseJob) -> Dict[str, Any]:
        """Modifies workflow for specific job"""
        pass

    def _load_workflow(self) -> None:
        """Load the base workflow from file"""
        workflow_file = self.get_workflow_file()
        try:
            with open(workflow_file, 'r') as f:
                self.base_workflow = json.load(f)
            logger.info(f"Loaded workflow from {workflow_file}")
        except FileNotFoundError:
            logger.error(f"Workflow file not found: {workflow_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow file: {e}")
            raise

    def get_base_workflow(self) -> Dict[str, Any]:
        """Get the base workflow"""
        if self.base_workflow is None:
            self._load_workflow()
        return self.base_workflow