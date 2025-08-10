#!/bin/bash
# Quick start script for Prompt Runner v2

echo "==========================================="
echo "      PROMPT RUNNER V2 - Quick Start      "
echo "==========================================="

# Check if running on RunPod or local
if [ -d "/workspace/ComfyUI" ]; then
    echo "✓ Running on RunPod environment"
else
    echo "⚠ Not on RunPod - using local development mode"
    echo "  Output will be in ./output instead of /workspace/ComfyUI/output"
fi

# Check Python
if command -v python3 &> /dev/null; then
    echo "✓ Python3 found: $(python3 --version)"
else
    echo "✗ Python3 not found - please install Python 3.8+"
    exit 1
fi

# Check ComfyUI connection
if curl -s http://127.0.0.1:8188 > /dev/null; then
    echo "✓ ComfyUI server is running"
else
    echo "✗ ComfyUI not accessible at 127.0.0.1:8188"
    echo "  Please start ComfyUI first"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import websocket" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Create prompt_files directory if it doesn't exist
if [ ! -d "prompt_files" ]; then
    echo "Creating prompt_files directory..."
    mkdir prompt_files
    echo "⚠ No prompt files found - add .txt files to prompt_files/"
fi

# Check for prompt files
PROMPT_COUNT=$(ls -1 prompt_files/*.txt 2>/dev/null | wc -l)
if [ $PROMPT_COUNT -eq 0 ]; then
    echo "⚠ No prompt files found in prompt_files/"
    echo "  Creating sample prompt file..."
    cat > prompt_files/sample.txt << 'EOF'
sample_video

101

A beautiful sunset over the ocean with golden hour lighting, waves crashing on shore, 4k, cinematic

blurry, low quality, distorted
EOF
    echo "✓ Created prompt_files/sample.txt"
fi

echo ""
echo "Ready to run! Use one of these commands:"
echo ""
echo "  python main.py                  # Process all prompt files"
echo "  python main.py --dry-run        # Preview job planning"
echo "  python main.py --help           # Show all options"
echo ""
echo "==========================================="