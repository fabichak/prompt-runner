# Comprehensive Dry-Run Mode for Prompt Runner

This document describes the comprehensive dry-run mode implementation that simulates all operations without making actual external connections.

## Overview

The dry-run mode provides complete simulation of the prompt-runner workflow, including:
- Job creation and planning
- Workflow generation with JSON file output
- ComfyUI WebSocket/HTTP communication simulation
- Google Cloud Storage upload simulation
- FFmpeg reference image extraction simulation
- RunPod instance management simulation

## Features

### ✅ Complete External Service Simulation
- **ComfyUI Client**: Mocks all WebSocket and HTTP communications
- **Storage Manager**: Simulates GCS uploads while maintaining local file structure
- **RunPod Manager**: Simulates instance information and health checks
- **FFmpeg Operations**: Simulates reference image extraction

### ✅ Comprehensive Workflow Generation
- Saves all generated workflows as JSON files in temporary folders
- Captures detailed job information and modifications
- Maintains complete audit trail of planned operations

### ✅ Intelligent Service Factory
- Dependency injection pattern for seamless real/mock service switching
- Environment variable support (`DRY_RUN=true`)
- Automatic fallback for workspace directory permissions

## Usage

### Basic Usage

```bash
# Enable dry-run mode with the existing --dry-run flag
python main.py --dry-run

# Process specific prompt file in dry-run mode
python main.py --dry-run --prompt-file prompt_files/example.txt

# Use environment variable
DRY_RUN=true python main.py --prompt-file prompt_files/example.txt
```

### Advanced Usage

```bash
# Dry-run with custom frames per chunk
python main.py --dry-run --frames-per-chunk 150 --prompt-file prompt_files/example.txt

# Dry-run with validation only
python main.py --dry-run --validate-only

# Dry-run with specific output directory (simulated)
python main.py --dry-run --output-dir /custom/output --prompt-file prompt_files/example.txt
```

## Output Structure

When dry-run mode is enabled, it creates a timestamped temporary directory:

```
temp_dry_run_YYYYMMDD_HHMMSS/
├── workflows/          # Generated workflow JSON files
│   ├── workflow_001_high_noise_render.json
│   ├── workflow_002_low_noise_render.json
│   └── workflow_003_combine.json
├── render_jobs/        # Render job plans
│   └── render_jobs_HHMMSS.json
├── combine_jobs/       # Combine job plans
│   └── combine_jobs_HHMMSS.json
└── state/             # State management files
    └── cleanup_video_name.json
```

### Workflow JSON Structure

Each workflow file contains:
```json
{
  "workflow_id": 1,
  "timestamp": "2025-08-10T18:23:50.123456",
  "job_info": {
    "type": "high_noise_render",
    "job_id": "uuid-here",
    "job_number": 1,
    "video_name": "example_video",
    "modifications": ["LoRA: wan2.2_high_t2v.safetensors", "Model: Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf"]
  },
  "workflow": {
    // Complete ComfyUI workflow JSON
  },
  "original_nodes_count": 42,
  "modifications_applied": ["..."]
}
```

### Job Plan Structure

Job plans contain complete execution details:
```json
{
  "job_type": "render",
  "timestamp": "2025-08-10T18:23:50.123456",
  "metadata": {
    "video_name": "example_video",
    "total_frames": 500,
    "frames_per_chunk": 101
  },
  "total_jobs": 10,
  "jobs": [
    {
      "job_id": "uuid-here",
      "job_number": 1,
      "job_type": "JobType.HIGH",
      "frames_to_render": 101,
      "start_frame": 0,
      "positive_prompt": "...",
      "negative_prompt": "...",
      "latent_input_path": null,
      "reference_image_path": null
    }
    // ... more jobs
  ]
}
```

## Architecture

### Service Factory Pattern

The implementation uses dependency injection through a service factory:

```python
from services.service_factory import ServiceFactory

# Automatically returns mock or real implementation based on dry-run mode
comfyui_client = ServiceFactory.create_comfyui_client()
storage_manager = ServiceFactory.create_storage_manager()
runpod_manager = ServiceFactory.create_runpod_manager()
```

### Mock Service Classes

#### MockComfyUIClient
- Simulates WebSocket connections and HTTP requests
- Generates realistic prompt IDs and execution times
- Saves workflow modifications to temp folder
- Provides comprehensive logging with emojis for clarity

#### MockStorageManager  
- Maintains same directory structure as real implementation
- Simulates GCS uploads with detailed metadata
- Creates demonstration files for inspection
- Tracks all simulated operations

#### MockRunPodManager
- Provides simulated instance information
- Simulates health checks with realistic metrics
- Handles shutdown simulations

### Dry-Run Manager

Central coordinator for dry-run operations:

```python
from services.dry_run_manager import enable_dry_run, is_dry_run, dry_run_manager

# Enable dry-run mode
enable_dry_run()

# Check if in dry-run mode
if is_dry_run():
    # Special dry-run logic
    pass

# Save workflows and job plans
dry_run_manager.save_workflow(workflow, job_info)
dry_run_manager.save_job_plan("render", jobs, metadata)
```

## Integration Points

### Main Application
- Enhanced `--dry-run` flag with comprehensive simulation
- Automatic mock service activation
- Detailed dry-run summary reporting

### Job Orchestrator
- FFmpeg simulation for reference image extraction
- State management with dry-run metadata
- Complete workflow execution simulation

### Workflow Manager
- Automatic workflow saving during dry-run
- Detailed modification tracking
- Comprehensive job metadata capture

## Testing

### Automated Tests

Run the included test suite:
```bash
python test_dry_run.py
```

### Manual Testing

1. **Basic Functionality Test**:
   ```bash
   python main.py --dry-run --prompt-file prompt_files/1.txt
   ```

2. **Check Generated Files**:
   ```bash
   ls -la temp_dry_run_*/
   cat temp_dry_run_*/render_jobs/render_jobs_*.json
   ```

3. **Verify No External Connections**:
   - Monitor network traffic during dry-run
   - Check logs for simulation messages (marked with 🎭, ☁️, etc.)

## Benefits

### 🚀 Development & Testing
- Test complete workflow logic without external dependencies  
- Validate job planning and workflow generation
- Debug issues without ComfyUI server running
- Develop and test on local machines

### 🔍 Workflow Analysis
- Inspect generated ComfyUI workflows before execution
- Analyze job sequences and dependencies
- Verify prompt and parameter handling
- Review resource requirements

### 📊 Planning & Estimation
- Estimate execution time and resource requirements
- Plan batch operations and resource allocation
- Validate prompt file formats and content
- Test different parameter configurations

### 🛡️ Risk Mitigation
- Validate workflows before expensive GPU execution
- Test error handling and edge cases
- Verify file paths and directory structures
- Debug complex multi-step operations

## Configuration

### Environment Variables
```bash
# Enable dry-run mode globally
export DRY_RUN=true

# Custom temp directory location (optional)
export DRY_RUN_TEMP_DIR="/custom/temp/path"
```

### Config File Support
The system automatically detects workspace permissions and falls back to local directories for testing:

```python
# In config.py - automatic fallback for testing
try:
    if workspace_available():
        BASE_OUTPUT_DIR = Path("/workspace/ComfyUI/output/prompt-runner")
    else:
        BASE_OUTPUT_DIR = Path("output/prompt-runner")  # Local fallback
except:
    BASE_OUTPUT_DIR = Path("output/prompt-runner")
```

## Best Practices

### 🎯 Use Cases
1. **Development**: Test workflow logic during development
2. **CI/CD**: Validate changes in continuous integration
3. **Debugging**: Analyze complex issues without external dependencies
4. **Education**: Learn workflow structure and job planning
5. **Resource Planning**: Estimate costs and requirements

### ⚠️ Limitations
- No actual video generation or processing
- Simulated timing may not reflect real execution time
- File sizes are placeholder values
- Network conditions not simulated

### 💡 Tips
- Review generated JSON files to understand workflow modifications
- Use dry-run for prompt file validation before expensive execution
- Combine with `--validate-only` for comprehensive pre-flight checks
- Preserve temp directories for later analysis

## Troubleshooting

### Common Issues

1. **Permission Errors**: 
   - System automatically falls back to local directories
   - Check that current directory is writable

2. **Import Errors**:
   - Ensure all required dependencies are installed
   - Check Python path configuration

3. **Missing Prompt Files**:
   - Verify prompt file paths and formats
   - Use `--validate-only` to check file structure

### Debug Mode

Enable verbose logging for detailed simulation information:
```bash
python main.py --dry-run --log-level DEBUG --prompt-file prompt_files/example.txt
```

## Implementation Files

### Core Files
- `services/dry_run_manager.py` - Central coordination
- `services/service_factory.py` - Dependency injection
- `services/mock_comfyui_client.py` - ComfyUI simulation
- `services/mock_storage_manager.py` - Storage simulation
- `services/mock_runpod_manager.py` - RunPod simulation

### Integration Files
- `main.py` - Enhanced dry-run flag integration
- `services/job_orchestrator.py` - FFmpeg simulation
- `services/workflow_manager.py` - Workflow saving
- `config.py` - Directory fallback logic

### Testing
- `test_dry_run.py` - Comprehensive test suite

This comprehensive dry-run mode enables safe testing, development, and analysis of the prompt-runner system without any external dependencies or costs.