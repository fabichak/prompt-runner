"""
Configuration constants for Prompt Runner
"""
import os
from pathlib import Path

# Server Configuration
SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = None  # Will be set at runtime

# Workflow Files
JSON_WORKFLOW_FILE = "prompt.json"
COMBINE_WORKFLOW_FILE = "combine.json"

# Directory Configuration
INPUT_PROMPT_DIR = "prompt_files"

# Try /workspace first, fallback to local directory for testing
try:
    workspace = Path("/workspace")
    if workspace.exists() and workspace.is_dir():
        # Check if we can write to workspace
        test_file = workspace / "test_write"
        try:
            test_file.touch()
            test_file.unlink()
            BASE_OUTPUT_DIR = Path("/workspace/ComfyUI/output/prompt-runner")
        except (PermissionError, OSError):
            BASE_OUTPUT_DIR = Path("output/prompt-runner")
    else:
        BASE_OUTPUT_DIR = Path("output/prompt-runner")
except Exception:
    BASE_OUTPUT_DIR = Path("output/prompt-runner")

# GCS Configuration
GCS_BUCKET_PATH = "gs://aiof-saved-files/"

# VIDEO
FRAMES_TO_RENDER = 161  # Constant frames per chunk
STEPS = 8
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280

# Node IDs for workflow modification
NODE_WIDTH = "21"
NODE_HEIGHT = "20"
NODE_REF_IMAGES = "392"
NODE_SAMPLES_54 = "54"
NODE_FRAMES_VALUE = "19"
NODE_START_FRAME = "348"
NODE_VIDEO_COMBINE = "340"
NODE_PROMPT = "53"
NODE_LOAD_VIDEO_PATH = "389"

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# RunPod Configuration
DEFAULT_NO_SHUTDOWN = True  # Default is to NOT shutdown