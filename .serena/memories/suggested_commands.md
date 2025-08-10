# Suggested Commands for Prompt Runner Development

## Running the Application
```bash
# Run the main script (default: start from job 1)
python main.py

# Resume from a specific job number
python main.py --start-at 100
```

## Git Commands
```bash
# Check status
git status

# Add changes
git add <file>
git add -A  # Add all changes

# Commit changes
git commit -m "Description of changes"

# Push to remote
git push origin main

# Pull latest changes
git pull origin main
```

## File System Navigation (Linux)
```bash
# List files
ls -la

# Change directory
cd <directory>

# Current directory
pwd

# Create directory
mkdir <directory>

# Remove file/directory
rm <file>
rm -rf <directory>

# Copy files
cp <source> <destination>

# Move/rename files
mv <source> <destination>
```

## Python Development
```bash
# Run Python script
python3 main.py

# Check Python version
python3 --version

# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Install specific package
pip install <package>
```

## Project-Specific Directories
```bash
# Navigate to prompt files
cd prompt_files/

# List prompt files
ls prompt_files/*.txt

# Edit prompt file
nano prompt_files/<filename>.txt
```

## Process Management
```bash
# Check if ComfyUI server is running
ps aux | grep comfy

# Check network connections
netstat -tuln | grep 8188

# Monitor WebSocket connections
ss -tan | grep 8188
```

## Google Cloud Storage (if configured)
```bash
# Upload file to GCS
gcloud storage cp <local-file> gs://aiof-saved-files/

# List GCS bucket contents
gcloud storage ls gs://aiof-saved-files/

# Download from GCS
gcloud storage cp gs://aiof-saved-files/<file> <local-destination>
```

## Debugging
```bash
# Run script with verbose output
python -v main.py

# Check Python imports
python -c "import websocket; print(websocket.__version__)"

# Test WebSocket connection
curl http://127.0.0.1:8188/prompt
```