"""
Configuration constants for Prompt Runner
"""
import os
from pathlib import Path

# Server Configuration
SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = None  # Will be set at runtime

# Workflow Files
JSON_WORKFLOW_FILE = "prompts/v2v.json"
I2I_WORKFLOW_FILE = "prompts/i2i.json"
COMBINE_WORKFLOW_FILE = "combine.json"

# Directory Configuration
INPUT_PROMPT_DIR = "v2v-files"
I2I_INPUT_DIR = "i2i-files"

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
VIDEO_WIDTH = 352
VIDEO_HEIGHT = 624
CONTEXT_OPTIONS_FRAMES = 220
CONTEXT_OPTIONS_OVERLAP = 100


# Node IDs for workflow modification
NODE_WIDTH = "162"
NODE_HEIGHT = "163"
NODE_SELECT_EVERY = "163"
NODE_REF_IMAGES = "256"
NODE_SAMPLER = "130"
NODE_VIDEO_COMBINE = "184"
NODE_VIDEO_COMBINE_NOBG = "258"
NODE_PROMPT_POS = "132"
NODE_PROMPT_NEG = "132"
NODE_LOAD_VIDEO_PATH = "255"

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# RunPod Configuration
DEFAULT_NO_SHUTDOWN = True  # Default is to NOT shutdown

I2I_IMAGE_RENDER_AMOUNT = 1  # Number of renders per CFG value
I2I_SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
I2I_EXCLUDED_FOLDERS = {'_old'}  # Folders to exclude from scanning
I2I_PROCESSED_FILE = "i2i_processed_images.txt"  # File to track processed images
I2I_FAILED_FILE = "i2i_failed_images.txt"  # File to track failed images
I2I_POLL_INTERVAL = 30  # Seconds between folder scans for new images

I2I_NODE_IMAGE_PATH = "365"
I2I_NODE_OUTPUT = "53"
I2I_SAMPLER_NODE = "334" 

# External API Endpoints
TRELLO_API_BASE_URL = "https://xxtria-prompt-scheduler-76618010335.us-central1.run.app"