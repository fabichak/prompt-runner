# Task Completion Checklist

When completing a development task on this project, follow these steps:

## 1. Code Quality Checks
- [ ] Ensure code follows existing style conventions (4-space indentation, snake_case naming)
- [ ] Add docstrings to new functions
- [ ] Use descriptive variable names
- [ ] Handle errors appropriately with try-except blocks
- [ ] Add informative print statements with emoji indicators for status

## 2. Testing
- [ ] Test the script locally if possible:
  ```bash
  python main.py --start-at 1
  ```
- [ ] Verify WebSocket connection handling
- [ ] Test error conditions (missing files, connection failures)
- [ ] Ensure resume functionality works (`--start-at` parameter)

## 3. Manual Validation
- [ ] Check that prompt files are read correctly from `prompt_files/`
- [ ] Verify workflow JSON is valid JSON format
- [ ] Ensure output paths are correctly formatted
- [ ] Validate that all parameter iterations work as expected

## 4. Documentation
- [ ] Update inline comments if logic changed
- [ ] Document any new configuration parameters
- [ ] Update function docstrings if behavior changed
- [ ] Note any new dependencies or requirements

## 5. Version Control
```bash
# Check what changed
git status
git diff

# Stage changes
git add <modified files>

# Commit with descriptive message
git commit -m "feat/fix/refactor: Description of changes"

# Push to remote
git push origin main
```

## 6. Verification Steps
- [ ] Verify no syntax errors: `python -m py_compile main.py`
- [ ] Check imports work: `python -c "import websocket"`
- [ ] Ensure configuration constants are correct
- [ ] Validate file paths and directories exist

## 7. Integration Checks
- [ ] Verify ComfyUI server connectivity (port 8188)
- [ ] Check GCS bucket access if using cloud storage
- [ ] Ensure RunPod environment variables if using shutdown feature

## 8. Clean Up
- [ ] Remove any debug print statements
- [ ] Clean up any temporary files
- [ ] Ensure no sensitive information in code (API keys, passwords)

## Notes
- Since there's no formal testing framework or linter configured, manual verification is important
- The script interacts with external services (ComfyUI, GCS, RunPod), so integration testing is critical
- Always test with a small batch first before running full parameter combinations
- Keep the workflow JSON (`prompt.json`) backed up before modifications