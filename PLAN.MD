# Prompt Runner v2 Implementation Plan

## Overview

This plan outlines the upgrade from Prompt Runner v1 (simple batch image generation) to v2 (complex video generation with Wan2.2 workflow support). The v2 system implements a sophisticated 2-pass sampling system with HIGH/LOW noise models, video segmentation, and progressive combination.

## Current State Analysis

**v1 System:**
- Single workflow execution with parameter variations
- Simple text prompt files
- Basic ComfyUI integration via websockets
- GCS upload and RunPod shutdown
- All code in single main.py file (~212 lines)

**v2 Requirements:**
- Complex multi-job render orchestration (HIGH/LOW model alternation)  
- New prompt file format (video name, frames, positive/negative prompts)
- Reference image system starting from job 3
- Video combination using combine.json
- Sophisticated file management (latents, videos, references)
- Code refactoring into modular structure

## Requirements Clarifications (RESOLVED)

All critical requirements have been clarified:

### Resolved Technical Details

1. **Frame Calculation Logic**
   - "LENGTH-10" means mathematical operation: `frames_to_render - 10`
   - This is the frame position to extract for reference images
   - For cases where `frames_to_render ≤ 10`, we'll use frame 0 as fallback

2. **Reference Image Extraction**
   - Extract frame at position `frames_to_render - 10` from node 344 output
   - Format: PNG for quality preservation
   - Saved in references directory with clear naming

3. **Video Combination Logic**
   - First COMBINE job uses output from RENDER job 2 (first LOW job)
   - Second COMBINE job uses output from RENDER job 4 AND previous COMBINE output
   - Progressive chaining: each combine includes previous combined video

4. **Job Calculation**
   - Total frames from line 2 of input file (e.g., 500 frames)
   - Frames divided into chunks (configurable, default 100)
   - Skip-n-frames increments by `frames_to_render` after job 3

### Combine.json Node Modifications

5. **Node Modifications for Combination**
   - Node 25 (`inputs.videos`): Set to current render job video filename
   - Node 30 (`image_2`): Removed for first combine, set to previous combined for subsequent
   - Node 14 (`inputs.images`): Set to [33, 0] for first combine only

6. **File Management Strategy**
   - Progressive cleanup after successful combination
   - Temporary files in organized directory structure
   - Clear naming conventions for all intermediate files

## Implementation Architecture

### Modular Structure

```
prompt-runner/
├── main.py                    # Entry point and orchestration
├── config.py                  # Configuration constants
├── models/
│   ├── __init__.py
│   ├── prompt_data.py         # PromptData dataclass
│   ├── job.py                 # RenderJob, CombineJob classes  
│   └── job_result.py          # JobResult for output tracking
├── services/
│   ├── __init__.py
│   ├── comfyui_client.py      # WebSocket communication
│   ├── workflow_manager.py    # JSON workflow modifications
│   ├── job_orchestrator.py    # Job execution engine
│   ├── storage_utils.py       # File operations, GCS
│   └── runpod_utils.py        # RunPod lifecycle
├── utils/
│   ├── __init__.py
│   ├── file_parser.py         # Parse new prompt format
│   └── job_planner.py         # Calculate job sequences
├── prompt.json                # Base render workflow
├── combine.json               # Base combine workflow  
└── prompt_files/              # Input directory
```

### Data Models

```python
@dataclass
class PromptData:
    video_name: str
    frames_to_render: int
    positive_prompt: str
    negative_prompt: str
    
@dataclass  
class RenderJob:
    job_id: str
    job_type: Literal["HIGH", "LOW"]
    job_number: int
    start_frame: int
    frames_to_render: int
    latent_input_path: Optional[str] = None
    reference_image_path: Optional[str] = None
    
@dataclass
class CombineJob:
    job_id: str
    input_video_path: str
    previous_combined_path: Optional[str] = None
    output_path: str
```

## Implementation Phases

### Phase 1: Infrastructure & Refactoring (Days 1-2)

**Objectives:**
- Modularize existing v1 code
- Set up new project structure  
- Create base data models and configuration

**Tasks:**
1. **Extract v1 utilities into modules:**
   - Move `queue_prompt`, `wait_for_prompt_completion` → `comfyui_client.py`
   - Move `zip_and_upload_output` → `storage_utils.py`  
   - Move `shutdown_runpod_instance` → `runpod_utils.py`
   - Create `config.py` with all constants

2. **Create new data structures:**
   - Implement `PromptData`, `RenderJob`, `CombineJob` dataclasses
   - Create `JobResult` for tracking outputs and file paths
   - Add validation methods for data integrity

3. **Set up file management system:**
   - Directory structure for latents, videos, references, final outputs
   - File naming conventions and path utilities
   - Cleanup and disk space management functions

**Deliverables:**
- Modular codebase with clear separation of concerns
- Data models with validation
- File management infrastructure
- Backward compatibility with v1 (for testing)

### Phase 2: Prompt Processing & Job Planning (Days 3-4)

**Objectives:**
- Parse new 4-line prompt file format. Variables are split with an empty line.
- Implement job sequence calculation
- Create render job planning logic

**Tasks:**
1. **Prompt file parser (`file_parser.py`):**
   ```python
   def parse_prompt_file(file_path: str) -> PromptData:
       # Parse: video_name, frames_to_render, positive_prompt, negative_prompt
   ```

2. **Job planning logic (`job_planner.py`):**
   ```python
   def calculate_job_sequence(prompt_data: PromptData, total_frames: int) -> List[RenderJob]:
       # Calculate: total job pairs needed, start frames, job types
   ```

3. **Job sequence validation:**
   - Verify job sequence covers all required frames
   - Handle edge cases (small frame counts, single job videos)
   - Generate job execution plan with dependencies

**Deliverables:**
- Robust prompt file parsing with validation
- Job planning algorithm with edge case handling  
- Unit tests for parsing and planning logic
- Sample job execution plans

### Phase 3: Workflow Management (Days 5-7)

**Objectives:**
- Implement JSON workflow modifications for HIGH/LOW jobs
- Handle node manipulation according to specifications
- Create workflow validation system

**Tasks:**
1. **Workflow modification engine (`workflow_manager.py`):**
   ```python
   class WorkflowManager:
       def modify_for_high_job(self, workflow: dict, job: RenderJob) -> dict
       def modify_for_low_job(self, workflow: dict, job: RenderJob) -> dict  
       def create_combine_workflow(self, combine_base: dict, video_paths: List[str]) -> dict
   ```

2. **Node modification implementation:**
   - **Node 309:298** (LoRA): HIGH → `wan2.2_high_t2v.safetensors`, LOW → `wan2.2_low_t2v.safetensors`
   - **Node 4** (model): HIGH → `Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf`, LOW → `Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf`
   - **Node 144** (ref_images): Delete for jobs 1-2, populate for jobs 3+
   - **Node 54** (samples): Delete for all HIGH jobs
   - **Node 365** (latent): Delete for all LOW jobs  
   - **Node 341** (samples): Delete for all HIGH jobs
   - **Node 19** (value): Set to `FRAMES-TO-RENDER`
   - **Node 348** (start_frame): Progressive calculation

3. **Workflow validation:**
   - Verify required nodes exist in base workflows
   - Validate node modifications don't break workflow structure
   - Test workflow generation with sample jobs

**Deliverables:**
- Complete workflow modification system
- Node manipulation functions with validation
- Workflow testing utilities

### Phase 4: Job Execution Engine (Days 8-10)

**Objectives:**  
- Implement render job execution with ComfyUI integration
- Handle latent file passing between HIGH/LOW jobs
- Add reference image extraction and usage

**Tasks:**
1. **Job orchestrator (`job_orchestrator.py`):**
   ```python
   class JobOrchestrator:
       def execute_render_jobs(self, prompt_data: PromptData, jobs: List[RenderJob]) -> List[JobResult]
       def execute_combine_jobs(self, video_paths: List[str]) -> JobResult
       def extract_reference_image(self, video_path: str) -> str
   ```

2. **Render job execution:**
   - Queue HIGH jobs and save latent outputs
   - Queue LOW jobs with latent inputs, save video outputs
   - Handle job dependencies and sequencing
   - Progress tracking and error handling

3. **Reference image system:**
   - Extract reference images from LOW job videos
   - Store in organized directory structure  
   - Pass reference paths to subsequent HIGH jobs
   - Handle missing or corrupted reference files

**Deliverables:**
- Complete job execution engine
- Reference image extraction system
- Progress tracking and logging
- Error handling

### Phase 5: Video Combination (Days 11-12)

**Objectives:**
- Implement progressive video combination using combine.json
- Handle video format compatibility and merging
- Create final output management

**Tasks:**
1. **Combination workflow:**
   - Generate combine jobs for each video segment
   - Progressive merging: video1 → combined1, video2 + combined1 → combined2, etc.
   - Handle video format standardization

2. **File management:**
   - Organize intermediate videos for combination
   - Track combination progress and outputs
   - Clean up intermediate files after successful combination

3. **Output finalization:**
   - Generate final combined video for each prompt file
   - Apply naming conventions and metadata
   - Prepare for GCS upload

**Deliverables:**
- Video combination system using combine.json
- Progressive merging logic
- Final output management and cleanup
- Integration with existing upload system

### Phase 6: Integration & Testing (Days 13-15)

**Objectives:**
- Integrate all components into unified system
- Comprehensive testing with various scenarios
- Performance optimization and error handling

**Tasks:**
1. **System integration:**
   - Connect all phases into main execution pipeline
   - Implement comprehensive error handling
   - Add progress tracking across entire pipeline

2. **Testing strategy:**
   ```
   Unit Tests:
   - Prompt file parsing
   - Job planning calculations  
   - Workflow modifications
   - Individual service functions
   
   Integration Tests:
   - End-to-end job execution
   - File management operations
   - ComfyUI communication
   ```

3. **Edge case handling:**
   - Small frame count videos (≤ 10 frames)
   - Single job pair videos
   - Failed job recovery

**Deliverables:**
- Fully integrated v2 system
- Comprehensive test suite
- Error handling documentation

## File Organization Strategy

### Directory Structure
```
/workspace/ComfyUI/output/
├── prompt-runner/
│   ├── latents/
│   │   ├── {video_name}/
│   │   │   ├── job_001.latent
│   │   │   ├── job_003.latent  
│   │   │   └── ...
│   ├── videos/
│   │   ├── {video_name}/
│   │   │   ├── job_002.mp4
│   │   │   ├── job_004.mp4
│   │   │   └── ...
│   ├── references/
│   │   ├── {video_name}/
│   │   │   ├── job_002_ref.png
│   │   │   ├── job_004_ref.png  
│   │   │   └── ...
│   ├── combined/
│   │   ├── {video_name}_temp_1.mp4
│   │   ├── {video_name}_temp_2.mp4
│   │   └── ...
│   └── final/
│       ├── {video_name}_final.mp4
│       └── ...
```

### Naming Conventions
- **Latent files**: `{video_name}_job_{job_num:03d}.latent`
- **Video segments**: `{video_name}_job_{job_num:03d}.mp4`  
- **Reference images**: `{video_name}_job_{job_num:03d}_ref.png`
- **Combined temp**: `{video_name}_combined_{stage:03d}.mp4`
- **Final output**: `{video_name}_final.mp4`

## Risk Assessment & Mitigation

### High Risk Items

1. **Complex Job Dependencies**
   - **Risk**: HIGH jobs depend on previous LOW job outputs
   - **Mitigation**: Robust job state tracking and validation

2. **Memory Management**  
   - **Risk**: ComfyUI VRAM exhaustion with complex workflows
   - **Mitigation**: Job queuing and memory monitoring

3. **File System Management**
   - **Risk**: Disk space exhaustion with large videos
   - **Mitigation**: Progressive cleanup and space monitoring

### Medium Risk Items

4. **Workflow Node Compatibility**
   - **Risk**: Node IDs might change in ComfyUI updates
   - **Mitigation**: Workflow validation and node existence checking

5. **Video Format Compatibility**
   - **Risk**: Combination failures due to format mismatches
   - **Mitigation**: Format standardization and validation

## Success Metrics

### Functional Requirements
- ✅ Parse new 4-line prompt file format
- ✅ Execute HIGH/LOW job sequences correctly  
- ✅ Handle reference image passing between jobs
- ✅ Combine video segments into final output
- ✅ Upload results to GCS and cleanup files

### Performance Requirements  
- **Processing Time**: ≤ 2x slower than v1 per equivalent output
- **Memory Usage**: Stable memory profile without leaks
- **Disk Usage**: Efficient cleanup with minimal temporary storage
- **Reliability**: ≥ 95% successful completion rate

### Code Quality Requirements
- **Modularity**: Clear separation of concerns across modules
- **Testability**: ≥ 80% unit test coverage for core logic
- **Maintainability**: Self-documenting code with clear interfaces  
- **Extensibility**: Easy to add new job types or workflow modifications

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| 1. Infrastructure | 2 days | Modular architecture, data models |
| 2. Prompt Processing | 2 days | Parser, job planner |  
| 3. Workflow Management | 3 days | HIGH/LOW workflow modifications |
| 4. Job Execution | 3 days | Render orchestration, reference system |
| 5. Video Combination | 2 days | Progressive merging system |
| 6. Integration & Testing | 3 days | Full system integration |

**Total Estimated Duration: 15 days**

## Next Steps

1. **Clarify ambiguous requirements** (listed above)
2. **Set up development environment** with v2 branch
3. **Begin Phase 1 implementation** starting with code refactoring
4. **Create sample prompt files** for testing each phase
5. **Establish testing infrastructure** for continuous validation

This plan provides a comprehensive roadmap for upgrading Prompt Runner to v2 while maintaining code quality and system reliability.