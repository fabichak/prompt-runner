# Code Style and Conventions

## Python Code Style
Based on analysis of main.py, the project follows these conventions:

### General Style
- **Python Version**: 3.12.11
- **Indentation**: 4 spaces (standard Python)
- **Line Length**: Approximately 100-120 characters
- **String Quotes**: Double quotes for most strings
- **F-strings**: Used for string formatting

### Naming Conventions
- **Variables**: snake_case (e.g., `prompt_files`, `start_time`, `current_job`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `SERVER_ADDRESS`, `CLIENT_ID`, `JSON_WORKFLOW_FILE`)
- **Functions**: snake_case with descriptive names (e.g., `queue_prompt`, `wait_for_prompt_completion`)
- **Configuration**: Grouped at top of file with clear section markers

### Code Organization
```python
# File structure pattern:
# 1. Imports (grouped: standard library, third-party, local)
# 2. Configuration constants (marked with --- Configuration ---)
# 3. Iteration parameters (marked with --- Iteration Parameters ---)
# 4. Helper functions (marked with --- Helper Functions ---)
# 5. Main logic (marked with --- Main Logic ---)
# 6. Entry point (if __name__ == "__main__")
```

### Documentation
- **Function Docstrings**: Triple quotes with brief description
  ```python
  def function_name(params):
      """Brief description of what the function does."""
  ```
- **Section Comments**: Using `# ---` separators for major sections
- **Inline Comments**: Used sparingly for complex logic
- **Print Statements**: Informative with emojis for status (✅, ❌, ⚠️, ⏩, ⏭️)

### Error Handling
- **Try-Except Blocks**: Used for external operations (file I/O, network, subprocess)
- **Specific Exceptions**: Caught when possible (e.g., `FileNotFoundError`, `subprocess.CalledProcessError`)
- **Error Messages**: Clear and actionable with emoji indicators
- **Return Values**: Functions return None on error, True/False for success/failure

### Logging/Output Style
```python
# Status indicators:
print("✅ Success message")
print("❌ Error: description")
print("⚠️  Warning: description")
print("⏩ Progress message")
print("\n" + "-"*50)  # Section separators
print("\n" + "="*50)  # Major section separators
```

### Type Hints
- Not currently used in the codebase
- Could be added for better code clarity

### Import Organization
```python
# Standard library
import websocket
import uuid
import json
# ... etc

# Third-party libraries
# (none currently)

# Local imports
# (none currently)
```

### Best Practices Observed
1. **Resource Management**: Using try-finally blocks for cleanup (WebSocket connections)
2. **Deep Copy**: Using `copy.deepcopy()` for workflow templates
3. **Path Handling**: Using `os.path.join()` for cross-platform compatibility
4. **Time Formatting**: Using `datetime.strftime()` for consistent time display
5. **Command-Line Arguments**: Using `argparse` for CLI interface

### Areas for Potential Improvement
- Add type hints for better code documentation
- Consider using logging module instead of print statements
- Add more comprehensive error recovery mechanisms
- Consider configuration file instead of hardcoded constants
- Add unit tests for helper functions