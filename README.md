# Prompt Runner v2

A sophisticated video generation system implementing complex HIGH/LOW noise model alternation with the Wan2.2 workflow for ComfyUI.

## Overview

Prompt Runner v2 transforms simple text prompts into high-quality videos using a 2-pass sampling system:
- **HIGH noise models** generate initial latent representations
- **LOW noise models** refine latents into video segments
- Progressive video combination creates seamless final outputs
- Reference image system maintains temporal consistency

## Key Features

- 🎬 **Multi-Stage Rendering**: Alternating HIGH/LOW model pipeline
- 🔄 **Reference Image System**: Temporal consistency across segments
- 📊 **State Persistence**: Resume failed jobs from saved checkpoints
- 🎯 **Job Orchestration**: Intelligent dependency management
- 💾 **Progressive Combination**: Efficient video merging
- ☁️ **GCS Integration**: Automatic cloud upload
- 🖥️ **RunPod Support**: Instance lifecycle management

## Architecture

```
prompt-runner/
├── main.py                    # Entry point and CLI
├── config.py                  # Configuration constants
├── models/                    # Data models
│   ├── prompt_data.py         # Prompt file representation
│   ├── job.py                 # RenderJob and CombineJob
│   └── job_result.py          # Execution results
├── services/                  # Core services
│   ├── comfyui_client.py      # WebSocket communication
│   ├── workflow_manager.py    # JSON workflow modifications
│   ├── job_orchestrator.py    # Job execution engine
│   ├── storage_utils.py       # File and GCS management
│   └── runpod_utils.py        # RunPod lifecycle
├── utils/                     # Utilities
│   ├── file_parser.py         # Prompt file parsing
│   └── job_planner.py         # Job sequence calculation
├── prompt_files/              # Input prompt files
├── prompt.json                # Base render workflow
└── combine.json               # Video combination workflow
```

## Installation

### Prerequisites

- Python 3.8+
- ComfyUI running on `127.0.0.1:8188`
- FFmpeg (for reference image extraction)
- gsutil (for GCS uploads)
- Required ComfyUI models:
  - `wan2.2_high_t2v.safetensors`
  - `wan2.2_low_t2v.safetensors`
  - `Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf`
  - `Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf`

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd prompt-runner

# Install dependencies (if using requirements.txt)
pip install websocket-client

# Ensure ComfyUI is running
# Check connection at http://127.0.0.1:8188
```

## Usage

### Basic Usage

```bash
# Process all prompt files in prompt_files directory
python main.py

# Process specific prompt file
python main.py --prompt-file my_prompt.txt

# Resume from saved state
python main.py --resume video_name

# Dry run to see job planning
python main.py --dry-run
```

### Command Line Options

```bash
# Input Options
--prompt-file FILE      Process specific prompt file
--prompt-dir DIR        Directory with prompt files (default: prompt_files)

# Execution Options
--resume VIDEO_NAME     Resume from saved state
--frames-per-chunk N    Frames per render chunk (default: 101)
--max-retries N         Max retries per job (default: 3)

# Output Options
--output-dir DIR        Custom output directory
--no-upload             Skip GCS upload
--keep-intermediate     Keep intermediate files

# RunPod Options
--no-shutdown           Keep instance running (default)
--force-shutdown        Force shutdown after completion

# Debug Options
--log-level LEVEL       Logging level (DEBUG/INFO/WARNING/ERROR)
--dry-run               Plan without executing
--validate-only         Validate files only
```

## Prompt File Format

Create `.txt` files in `prompt_files/` directory with this format:

```
video_name

total_frames

positive_prompt_text
can be multiple lines

negative_prompt_text
can be multiple lines
```

### Example:

```
sunset_beach

500

A beautiful sunset over the ocean with waves crashing on the shore, 
golden hour lighting, cinematic, 4k, highly detailed

blurry, low quality, distorted, watermark
```

## Workflow

### 1. Job Planning

For a 500-frame video with 101 frames per chunk:
- **5 HIGH jobs** (1, 3, 5, 7, 9): Generate latents
- **5 LOW jobs** (2, 4, 6, 8, 10): Create video segments
- **5 combine jobs**: Progressive video merging

### 2. Execution Flow

```
HIGH Job 1 → Latent 1
         ↓
LOW Job 2 → Video 1 → Reference Image 1
         ↓
HIGH Job 3 (uses Ref 1) → Latent 2
         ↓
LOW Job 4 → Video 2 → Reference Image 2
         ↓
... continues ...
```

### 3. Video Combination

```
Video 1 → Combined 1
Video 2 + Combined 1 → Combined 2
Video 3 + Combined 2 → Combined 3
... → Final Video
```

## Output Structure

```
/workspace/ComfyUI/output/prompt-runner/
├── latents/{video_name}/       # HIGH job outputs
│   ├── job_001.latent
│   └── job_003.latent
├── videos/{video_name}/        # LOW job outputs
│   ├── job_002.mp4
│   └── job_004.mp4
├── references/{video_name}/    # Reference images
│   ├── job_002_ref.png
│   └── job_004_ref.png
├── combined/{video_name}/      # Progressive combines
│   ├── combined_001.mp4
│   └── combined_002.mp4
├── final/{video_name}/          # Final outputs
│   └── {video_name}_final.mp4
└── state/                       # Recovery states
    └── {video_name}.json
```

## Node Modifications

### HIGH Jobs
- **LoRA (309)**: `wan2.2_high_t2v.safetensors`
- **Model (4)**: `Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf`
- **Reference (144)**: Deleted for jobs 1-2, set for 3+
- **Samples (54, 341)**: Deleted
- **Frames (19)**: Set to chunk size
- **Start Frame (348)**: Progressive increment

### LOW Jobs
- **LoRA (309)**: `wan2.2_low_t2v.safetensors`
- **Model (4)**: `Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf`
- **Latent (365)**: Deleted
- **Latent Input**: From previous HIGH job

## State Recovery

Failed jobs automatically save state for recovery:

```bash
# Resume from last checkpoint
python main.py --resume my_video_name

# State includes:
# - Completed job numbers
# - Failed job numbers
# - Timestamp
```

## Testing

Run the comprehensive test suite:

```bash
python test_runner.py
```

Tests cover:
- Prompt file parsing
- Job planning logic
- Workflow modifications
- Storage operations
- Integration scenarios

## Troubleshooting

### Common Issues

1. **ComfyUI Connection Failed**
   - Ensure ComfyUI is running on `127.0.0.1:8188`
   - Check firewall settings

2. **Missing Models**
   - Verify all required models are in ComfyUI model directory
   - Check model names match exactly

3. **FFmpeg Not Found**
   - Install FFmpeg: `apt-get install ffmpeg`
   - Ensure it's in PATH

4. **GCS Upload Failed**
   - Configure gsutil: `gsutil config`
   - Check bucket permissions

5. **Out of Memory**
   - Reduce frames per chunk
   - Monitor VRAM usage
   - Clear ComfyUI cache

### Logs

Logs are saved to timestamped files:
- `prompt_runner_YYYYMMDD_HHMMSS.log`

## Performance

- **Processing Time**: ~2-3 minutes per 101-frame chunk
- **Memory Usage**: 8-12GB VRAM typical
- **Disk Space**: ~5GB per 500-frame video
- **Network**: Minimal (WebSocket + GCS upload)

## Development

### Adding New Features

1. **New Job Types**: Extend `JobType` enum in `models/job.py`
2. **Workflow Modifications**: Add methods to `WorkflowManager`
3. **Storage Paths**: Update `StorageManager` path methods
4. **CLI Options**: Add arguments in `main.py`

### Code Style

- Type hints for all functions
- Docstrings for classes and methods
- Logging for important operations
- Error handling with recovery

## License

[Your License Here]

## Credits

Built for ComfyUI with the Wan2.2 workflow system.