# Dual ComfyUI Instance System

This document describes the new dual ComfyUI instance job scheduling system that enables parallel execution of HIGH and LOW priority jobs across two ComfyUI instances.

## Overview

The dual instance system maximizes ComfyUI utilization by running:
- **HIGH priority jobs** on ComfyUI instance 1 (default port 8188)
- **LOW priority jobs** on ComfyUI instance 2 (default port 8189)
- **COMBINE jobs** sequentially after all HIGH/LOW jobs complete

### Key Features

- ✅ **Parallel Execution**: HIGH and LOW jobs run simultaneously
- ✅ **Job Interleaving**: Jobs from different prompts interleave to keep both instances busy
- ✅ **Synchronization**: COMBINE jobs wait for all render jobs to complete
- ✅ **Error Recovery**: Robust error handling and automatic reconnection
- ✅ **Fallback Mode**: Graceful fallback to single instance if dual mode fails
- ✅ **Comprehensive Logging**: Detailed logging for monitoring and debugging

## Configuration

### Enable Dual Instance Mode

Edit `config.py` to enable dual instance mode:

```python
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
```

### Port Configuration

The default configuration assumes:
- **ComfyUI Instance 1**: `127.0.0.1:8188` (HIGH jobs)
- **ComfyUI Instance 2**: `127.0.0.1:8189` (LOW jobs)

To use different ports, update the `port` values in `COMFYUI_INSTANCES`.

## Usage

### Command Line Options

```bash
# Enable dual instance mode via command line
python main.py --dual-instance

# Force single instance mode (overrides config)
python main.py --single-instance

# Use default configuration setting
python main.py
```

### Running Multiple ComfyUI Instances

You need to start two ComfyUI instances on different ports:

```bash
# Terminal 1: Start ComfyUI instance 1 (HIGH jobs)
cd /path/to/ComfyUI
python main.py --port 8188

# Terminal 2: Start ComfyUI instance 2 (LOW jobs)  
cd /path/to/ComfyUI
python main.py --port 8189
```

### Example Execution

```bash
# Run with dual instance mode enabled
python main.py prompt_files/sample.txt --dual-instance

# Expected output:
# 🎯 Dual instance mode enabled via command line
# 🚀 Starting in DUAL INSTANCE mode
# ✅ Connected to instance high_priority at 127.0.0.1:8188
# ✅ Connected to instance low_priority at 127.0.0.1:8189
# ==========================================================
# STARTING PARALLEL RENDER JOBS
# ==========================================================
# 🔄 Executing HIGH job 1 on instance high_priority
# 🔄 Executing LOW job 2 on instance low_priority
# ...
```

## Job Execution Flow

### Phase 1: Render Jobs (Parallel)
1. **Job Distribution**: Jobs are distributed to appropriate queues (HIGH → Instance 1, LOW → Instance 2)
2. **Parallel Execution**: Both instances work simultaneously on their assigned job types
3. **Job Interleaving**: When Instance 1 finishes a HIGH job from prompt A, it immediately picks up the next HIGH job (possibly from prompt B)
4. **Progress Tracking**: System tracks completion across both instances

### Phase 2: Synchronization Point
1. **Wait for Completion**: System waits for ALL HIGH and LOW jobs to complete
2. **Ready Signal**: Once all render jobs are done, COMBINE jobs become available

### Phase 3: Combine Jobs (Sequential)
1. **Instance Selection**: COMBINE jobs execute on first available instance
2. **Sequential Processing**: COMBINE jobs run one at a time to avoid conflicts
3. **Final Output**: Create final video outputs

## Performance Benefits

### Expected Improvements
- **40-60% faster execution** for workloads with mixed HIGH/LOW jobs
- **80%+ instance utilization** when jobs are available
- **Reduced idle time** through intelligent job interleaving

### Benchmarking
To measure performance improvements:

```bash
# Run single instance benchmark
time python main.py prompt_files/test.txt --single-instance

# Run dual instance benchmark  
time python main.py prompt_files/test.txt --dual-instance
```

## Monitoring and Debugging

### Log Output
The system provides detailed logging:
- ✅ Connection status for each instance
- 🔄 Job assignments and execution progress  
- 📊 Queue status and synchronization points
- ⚠️ Error handling and recovery attempts

### Status Checking
Monitor system status during execution:
- Check log files for detailed execution traces
- Monitor ComfyUI web interfaces (ports 8188 and 8189)
- Review job completion metrics in logs

## Troubleshooting

### Common Issues

#### 1. "Failed to connect to any ComfyUI instances"
**Cause**: One or both ComfyUI instances are not running
**Solution**: 
```bash
# Start both instances
python /path/to/ComfyUI/main.py --port 8188
python /path/to/ComfyUI/main.py --port 8189
```

#### 2. "Instance X health check failed"
**Cause**: ComfyUI instance became unresponsive
**Solution**: System will attempt automatic reconnection, or restart the ComfyUI instance

#### 3. Jobs running slowly
**Cause**: Resource contention between instances
**Solution**: Monitor system resources (CPU, memory, GPU) and consider reducing concurrent jobs

#### 4. COMBINE jobs not starting
**Cause**: Some HIGH or LOW jobs may have failed
**Solution**: Check logs for failed jobs and resolve errors

### Fallback Behavior
If dual instance mode fails:
1. System automatically falls back to single instance mode
2. All jobs execute sequentially on the primary instance (port 8188)
3. Logs will indicate fallback activation

## Advanced Configuration

### Custom Instance Setup
For advanced setups, modify `COMFYUI_INSTANCES` in `config.py`:

```python
COMFYUI_INSTANCES = [
    {
        "instance_id": "gpu1_high",
        "host": "192.168.1.100",  # Remote host
        "port": 8188,
        "job_types": ["HIGH"],
        "max_concurrent": 2,      # Multiple concurrent jobs
        "enabled": True
    },
    {
        "instance_id": "gpu2_low", 
        "host": "192.168.1.101",  # Different remote host
        "port": 8188,
        "job_types": ["LOW"],
        "max_concurrent": 1,
        "enabled": True
    }
]
```

### Disabling Dual Instance Mode
To disable dual instance mode entirely:

```python
# In config.py
ENABLE_DUAL_INSTANCE = False
```

Or use the command line flag:
```bash
python main.py --single-instance
```

## Architecture Components

### Core Classes
- **`DualInstanceOrchestrator`**: Main coordinator for dual instance execution
- **`JobQueueManager`**: Manages HIGH, LOW, and COMBINE job queues with synchronization
- **`MultiInstanceComfyUIClient`**: Handles connections to multiple ComfyUI instances
- **`ComfyUIInstanceConfig`**: Configuration and status for individual instances

### Thread Safety
- All queue operations are thread-safe using Python threading primitives
- Job state synchronization prevents race conditions
- Error handling ensures graceful recovery from failures

## Testing

Run the test suite to verify dual instance functionality:

```bash
python test_dual_instance.py
```

This tests:
- Job queue management and synchronization
- Multi-instance client functionality  
- Orchestrator coordination
- Job completion synchronization logic

## Contributing

When modifying the dual instance system:
1. Run the test suite to ensure functionality
2. Test with both single and dual instance modes
3. Verify proper error handling and fallback behavior
4. Update documentation for any configuration changes

## Support

For issues with the dual instance system:
1. Check ComfyUI instance connectivity manually
2. Review log files for detailed error information  
3. Test with single instance mode to isolate issues
4. Verify system resources are sufficient for dual instances