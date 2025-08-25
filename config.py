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

LATENTS_DIR = "latents"
VIDEOS_DIR = "videos"
REFERENCES_DIR = "references"
COMBINED_DIR = "combined"
STATE_DIR = "state"

# GCS Configuration
GCS_BUCKET_PATH = "gs://aiof-saved-files/"

# Model Configuration (using single model configuration)
LOW_LORA = "wan2.2_low_t2v.safetensors"
LOW_MODEL = "Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf"

# VIDEO
FRAMES_TO_RENDER = 161  # Constant frames per chunk
START_FRAME_OFFSET = 10
REFERENCE_FRAME_OFFSET = START_FRAME_OFFSET  # The first 10 frames are always thrown away
STEPS = 8
HIGH_STEPS = 4  # Keep for backward compatibility in case it's referenced elsewhere
DEFAULT_TOTAL_FRAMES = 500  # Default if not specified
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 1280
RESCALE_FACTOR = 1.5

# Node IDs for workflow modification
NODE_LORA = "309:298"  # Also has sub-node 298
NODE_MODEL = "4"
NODE_VACE = "144"
NODE_WIDTH = "21"
NODE_HEIGHT = "20"
NODE_REF_IMAGES = "392"
NODE_SAMPLES_54 = "54"
NODE_SAVE_LATENT = "366"
NODE_LOAD_LATENT = "367"
NODE_SAMPLES_341 = "341"
NODE_FRAMES_VALUE = "19"
NODE_START_FRAME = "348"
NODE_VIDEO_COMBINE = "340"
NODE_VIDEO_DECODE = "341"
NODE_PROMPT = "53"
NODE_IMAGE_BATCH_SKIP = "375"
NODE_LOAD_VIDEO_PATH = "389"
NODE_SAVE_VIDEO_PATH = "395"

# Combine workflow node IDs
COMBINE_NODE_VIDEOS = "25"
COMBINE_NODE_IMAGE_BATCH = "30"
COMBINE_NODE_LOAD_VIDEO_COMBINE = "40"
COMBINE_NODE_OUTPUT_COMBINE_N = "14"
COMBINE_NODE_OUTPUT_COMBINE_1 = "41"
COMBINE_NODE_RESCALE = "35"

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# RunPod Configuration
DEFAULT_NO_SHUTDOWN = True  # Default is to NOT shutdown