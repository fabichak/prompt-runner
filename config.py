"""
Configuration constants for Prompt Runner v2
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
    _test_workspace = Path("/workspace")
    if _test_workspace.exists() and _test_workspace.is_dir():
        # Check if we can write to workspace
        _test_file = _test_workspace / "test_write"
        try:
            _test_file.touch()
            _test_file.unlink()
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

# Model Configuration
HIGH_LORA = "wan2.2_high_t2v.safetensors"
LOW_LORA = "wan2.2_low_t2v.safetensors"
HIGH_MODEL = "Wan2.2_T2V_High_Noise_14B_VACE-Q8_0.gguf"
LOW_MODEL = "Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf"

#VIDEO
START_FRAME_OFFSET = 10
REFERENCE_FRAME_OFFSET = 2*START_FRAME_OFFSET  # Hardcoded. the first 10 frames are always thrown away. then we need a refence of 10 before that, so 20
STEPS = 8
HIGH_STEPS = 4
FRAMES_TO_RENDER = 41  # Constant frames per chunk
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
NODE_REF_IMAGES = "358"
NODE_SAMPLES_54 = "54"
NODE_SAVE_LATENT = "366"
NODE_LOAD_LATENT = "367"
NODE_SAMPLES_341 = "341"
NODE_FRAMES_VALUE = "19"
NODE_START_FRAME = "348"
NODE_VIDEO_COMBINE = "340"
NODE_VIDEO_DECODE = "341"
NODE_PROMPT = "53"

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

# Dual ComfyUI Instance Configuration
ENABLE_DUAL_INSTANCE = True  # Enable dual instance mode
COMFYUI_INSTANCES = [
    {
        "instance_id": "high_priority",
        "host": "127.0.0.1", 
        "port": 8188,
        "job_types": ["HIGH"],
        "max_concurrent": 1,
        "enabled": True
    },
    {
        "instance_id": "low_priority",
        "host": "127.0.0.1",
        "port": 8189, 
        "job_types": ["LOW"],
        "max_concurrent": 1,
        "enabled": True
    }
]

# Fallback configuration for single instance mode
SINGLE_INSTANCE_CONFIG = {
    "instance_id": "main",
    "host": "127.0.0.1",
    "port": 8188,
    "job_types": ["HIGH", "LOW"],
    "max_concurrent": 1,
    "enabled": True
}

# RunPod Configuration
DEFAULT_NO_SHUTDOWN = True  # Default is to NOT shutdown