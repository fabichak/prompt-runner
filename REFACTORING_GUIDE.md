# Refactoring Guide - Unified Orchestrator Architecture

## Overview

This document describes the refactored architecture that simplifies job orchestration by implementing a strict 1:1:1 mapping (one input → one job → one output) and unifying all modes under a single orchestrator.

## Key Changes

### 1. **Unified Orchestrator** (`services/unified_orchestrator.py`)
- Single orchestrator handles all job types (v2v, i2i, future modes)
- API-driven processing through Trello
- No local state tracking (API handles state)
- Supports dry-run mode

### 2. **Mode Registry** (`services/mode_registry.py`)
- Central registration for job types and workflow managers
- Easy extensibility for new modes
- Runtime mode discovery

### 3. **Job Models** (`models/`)
- `base_job.py`: Common interface for all jobs
- `v2v_job.py`: Video-to-video specific implementation
- `i2i_job.py`: Image-to-image specific implementation
- Each job type implements `from_api_data()` for API integration

### 4. **Workflow Managers** (`services/workflows/`)
- `base_workflow.py`: Common interface
- `v2v_workflow.py`: V2V workflow modifications
- `i2i_workflow.py`: I2I workflow modifications
- Each manager handles mode-specific node modifications

## Removed Components

### Deleted Files:
- `utils/job_planner.py` - No longer needed (was only creating single jobs)
- `services/job_orchestrator.py` - Replaced by UnifiedOrchestrator
- `services/i2i_orchestrator.py` - Replaced by UnifiedOrchestrator
- `services/image_scanner.py` - API provides inputs now
- `services/image_tracker.py` - API tracks state
- `services/workflow_manager.py` - Replaced by mode-specific managers
- `services/i2i_workflow_manager.py` - Replaced by i2i_workflow.py

### Removed Features:
- File/directory scanning for inputs
- Local state tracking files
- Batch processing from directories
- Complex job planning logic

## Migration Steps

### 1. Run Migration Script
```bash
# Dry run to see what will happen
python migrate_to_unified.py --dry-run

# Backup and delete obsolete files
python migrate_to_unified.py --backup --delete
```

### 2. Update Configuration
Ensure your `config.py` has:
- `I2I_WORKFLOW_FILE = "prompts/i2i.json"`
- Trello API endpoint configured

### 3. Update Usage
```bash
# Old way (file-based)
python main.py prompt_files/my_prompt.txt

# New way (API-driven)
python main.py --trello
python main.py --trello --continuous
python main.py --trello --dry-run
```

## Adding New Modes

### Example: Text-to-Image Mode

1. **Create Job Model** (`models/t2i_job.py`):
```python
@dataclass
class T2IJob(BaseJob):
    prompt: str
    width: int
    height: int

    @classmethod
    def from_api_data(cls, api_data: Dict[str, Any]) -> 'T2IJob':
        return cls(
            job_id=api_data.get('cardId'),
            card_id=api_data.get('cardId'),
            mode='t2i',
            prompt=api_data.get('prompt'),
            width=api_data.get('width', 512),
            height=api_data.get('height', 512)
        )
```

2. **Create Workflow Manager** (`services/workflows/t2i_workflow.py`):
```python
class T2IWorkflowManager(BaseWorkflowManager):
    def get_workflow_file(self) -> str:
        return "prompts/t2i.json"

    def modify_workflow(self, job: BaseJob) -> Dict[str, Any]:
        # Modify workflow nodes for t2i
        pass
```

3. **Register Mode** (in `services/mode_registry.py`):
```python
ModeRegistry.register('t2i', T2IJob, T2IWorkflowManager)
```

That's it! The API can now send `mode: "t2i"` cards.

## API Contract

### Input (from Trello API)
```json
{
  "cardId": "unique-card-id",
  "mode": "v2v",  // or "i2i", "t2i", etc.
  "videoPath": "http://example.com/video.mp4",  // for v2v
  "imagePath": "http://example.com/image.png",  // for v2v/i2i
  "positivePrompt": "beautiful landscape",
  "negativePrompt": "blur, low quality",
  "cfg": 7.0,  // for i2i
  "totalFrames": 101,  // for v2v
  "seed": 12345  // optional, random if not provided
}
```

### Output (to Trello API)
```json
{
  "status": "completed",  // or "failed", "error"
  "job_id": "unique-job-id",
  "outputs": ["output1.png", "output2.mp4"],
  "error": "Error message if failed"
}
```

## Benefits

1. **Simplicity**: Single orchestrator, single flow
2. **Extensibility**: Add modes without touching core logic
3. **Maintainability**: Clear separation of concerns
4. **Stateless**: No complex state management
5. **API-First**: Clean integration with external systems
6. **Testability**: Easy to test individual components

## Testing

### Test API Connection:
```bash
python main.py --test-api
```

### List Available Modes:
```bash
python main.py --list-modes
```

### Dry Run:
```bash
python main.py --trello --dry-run
```

## Troubleshooting

### If imports fail:
- Ensure you've run the migration script
- Check that new files are in place
- Update any custom scripts to use new imports

### If modes aren't recognized:
- Check mode registration in `mode_registry.py`
- Ensure workflow JSON files exist
- Verify API is sending correct mode field

### For debugging:
```bash
python main.py --trello --log-level DEBUG
```