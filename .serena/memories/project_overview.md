# Prompt Runner Project Overview

## Purpose
This project is a batch image generation automation tool for ComfyUI workflows. It orchestrates and executes image generation jobs with various parameter combinations, handling:
- Multiple prompts from text files
- Parameter iteration (CFG scales, steps, samplers, schedulers, LoRA strengths)
- WebSocket communication with ComfyUI server
- Output management and cloud storage upload (Google Cloud Storage)
- RunPod instance management (shutdown capability)

## Tech Stack
- **Language**: Python 3.12.11
- **Core Dependencies**: 
  - websocket (WebSocket communication with ComfyUI)
  - Standard library: json, uuid, urllib, subprocess, shutil, argparse
- **External Services**:
  - ComfyUI server (127.0.0.1:8188)
  - Google Cloud Storage (via gcloud CLI)
  - RunPod (for instance management)
- **Workflow Format**: JSON-based ComfyUI workflow definitions

## Architecture
- Single main script (`main.py`) with modular helper functions
- WebSocket-based real-time communication for prompt execution
- Batch processing with resumability (--start-at parameter)
- Automated output archiving and cloud upload

## Key Components
1. **Prompt Management**: Reads prompts from `prompt_files/*.txt`
2. **Workflow Configuration**: Uses `prompt.json` as base workflow template
3. **Parameter Iteration**: Iterates through multiple parameter combinations
4. **Output Management**: Saves to `/workspace/ComfyUI/output/wan-image`
5. **Cloud Integration**: Uploads results to GCS bucket `gs://aiof-saved-files/`

## Repository
- Git repository: git@github.com:fabichak/prompt-runner.git
- Branch: main
- Version control active