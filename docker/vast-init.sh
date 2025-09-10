#!/bin/bash

# Runtime Initialization Script for VastAI
# This downloads all dynamic content after container starts
# Everything else is pre-installed in the Docker image

set -e

echo "========================================="
echo "Starting Runtime Initialization"
echo "Time: $(date)"
echo "========================================="

cd /workspace

# Step 1: Download credentials and configuration from Google Drive
echo "----------------------------------------"
echo "Downloading configuration files..."
echo "----------------------------------------"

# Download service account key
echo "Downloading service account key..."
gdown 1Gc9418nIrQNRW5xj_BpbA_rlOxGlW2GT
gdown 1LyGmuc1qfFjPMCTTISFdKlNQhet_Oz4K -O .env 

# Step 2: Configure Google Cloud SDK
echo "----------------------------------------"
echo "Configuring Google Cloud SDK..."
echo "----------------------------------------"
gcloud auth activate-service-account --key-file=/workspace/wise-ally-466621-c6-264a23c5d604.json
gcloud config set project wise-ally-466621-c6 --quiet

# Step 3: Download ComfyUI
echo "----------------------------------------"
echo "Downloading ComfyUI..."
echo "----------------------------------------"
gsutil cp gs://aiof-saved-files/comfy.zip .
echo "Extracting ComfyUI..."
unzip -q comfy.zip
rm comfy.zip
echo "ComfyUI extracted successfully"

# Step 5: Start model download in background
echo "----------------------------------------"
echo "Starting model download in background..."
echo "----------------------------------------"
LOG_FILE="/workspace/model_download.log"
nohup gsutil -m cp -R gs://aiof-saved-files/models ComfyUI > $LOG_FILE 2>&1 &
MODEL_PID=$!
echo "Model download started with PID: $MODEL_PID"
echo "Monitor progress: tail -f $LOG_FILE"

# Step 4: Copy workflows
echo "----------------------------------------"
echo "Copying workflows..."
echo "----------------------------------------"
gsutil -m cp -R gs://aiof-saved-files/workflows ComfyUI/user/default || echo "Workflows copy completed"

echo "----------------------------------------"
echo "Setting up venv..."
echo "----------------------------------------"

source /venv/main/bin/activate

# Setup SageAttention
echo "----------------------------------------"
echo "Setting up SageAttention..."
echo "----------------------------------------"

git clone https://github.com/thu-ml/SageAttention.git
cd SageAttention
EXT_PARALLEL=4 NVCC_APPEND_FLAGS="--threads 8" MAX_JOBS=32 python setup.py install || pip install -e .
cd ..

# Step 6: Install ComfyUI-specific requirements
echo "----------------------------------------"
echo "Installing ComfyUI requirements..."
echo "----------------------------------------"

pip install -r ComfyUI/requirements.txt || echo "Some requirements already satisfied"
pip install -r ComfyUI/custom_nodes/comfyui-manager/requirements.txt || echo "Manager requirements already satisfied"

# Step 7: Fix ComfyUI custom nodes
echo "----------------------------------------"
echo "Fixing ComfyUI custom nodes..."
echo "----------------------------------------"
python ComfyUI/custom_nodes/comfyui-manager/cm-cli.py fix all || echo "Fix completed with warnings"

source .env 
git clone https://github.com/fabichak/prompt-runner.git

echo "Waiting for models to finish downloading..."
while ! grep -q "Operation completed" model_download.log 2>/dev/null; do
    echo "Still downloading models... $(date)"
    sleep 3
done
echo "Models download completed!"

echo "Starting ComfyUI!"
cd /workspace/ComfyUI
nohup python main.py --listen 0.0.0.0 --port 8188 > ../comfy.log 2>&1 &
cd ..

echo "Waiting for comfyui to start..."
while ! grep -q "To see the GUI go to: " comfy.log 2>/dev/null; do
    echo "Comfy still starting... $(date)"
    sleep 3
done
echo "Comfyui startup completed!"

#start prompt runner
entrypoint.sh

echo "----------------------------------------"
echo "Creating status files..."
echo "----------------------------------------"
cat > /workspace/status.txt << EOF
===========================================
VastAI ComfyUI Instance Status
===========================================
GPU Status:
$(nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv 2>/dev/null || echo "No GPU detected")
===========================================
EOF

cat /workspace/status.txt
