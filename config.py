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
LATENTS_DIR = BASE_OUTPUT_DIR / "latents"
VIDEOS_DIR = BASE_OUTPUT_DIR / "videos"
REFERENCES_DIR = BASE_OUTPUT_DIR / "references"
COMBINED_DIR = BASE_OUTPUT_DIR / "combined"
FINAL_DIR = BASE_OUTPUT_DIR / "final"
STATE_DIR = BASE_OUTPUT_DIR / "state"

# GCS Configuration
GCS_BUCKET_PATH = "gs://aiof-saved-files/"

# Job Configuration
FRAMES_TO_RENDER = 101  # Constant frames per chunk
DEFAULT_TOTAL_FRAMES = 500  # Default if not specified

# Model Configuration
HIGH_LORA = "wan2.2_high_t2v.safetensors"
LOW_LORA = "wan2.2_low_t2v.safetensors"
HIGH_MODEL = "Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf"
LOW_MODEL = "Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf"

# Node IDs for workflow modification
NODE_LORA = "309"  # Also has sub-node 298
NODE_MODEL = "4"
NODE_REF_IMAGES = "144"
NODE_SAMPLES_54 = "54"
NODE_LATENT_365 = "365"
NODE_SAMPLES_341 = "341"
NODE_FRAMES_VALUE = "19"
NODE_START_FRAME = "348"
NODE_VIDEO_OUTPUT = "344"

# Combine workflow node IDs
COMBINE_NODE_VIDEOS = "25"
COMBINE_NODE_IMAGE2 = "30"
COMBINE_NODE_IMAGES = "14"

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Reference Image Configuration
REFERENCE_FRAME_OFFSET = 10  # Extract frame at (frames_to_render - 10)

# RunPod Configuration
DEFAULT_NO_SHUTDOWN = True  # Default is to NOT shutdown