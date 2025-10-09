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
gdown 1_iqOdH0RN1RqWRUAK1WI2k7Rtbblko7F -O ./comfy.zip
echo "Extracting ComfyUI..."
unzip -q comfy.zip
rm comfy.zip
echo "ComfyUI extracted successfully"

# Step 5: Start model downloads in parallel in background
echo "----------------------------------------"
echo "Starting model downloads in background..."
echo "----------------------------------------"

# Create a directory for download logs
mkdir -p /workspace/download_logs

# Function to download and log
download_model() {
    local cmd="$1"
    local log_name="$2"
    local log_file="/workspace/download_logs/${log_name}.log"
    
    echo "Starting: $log_name" | tee "$log_file"
    if eval "$cmd" >> "$log_file" 2>&1; then
        echo "SUCCESS" >> "$log_file"
        echo "Completed: $log_name"
        return 0
    else
        echo "FAILED" >> "$log_file"
        echo "Failed: $log_name"
        return 1
    fi
}

# Start all downloads in background
download_model "hf download lym00/Wan2.2_T2V_A14B_VACE-test Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf --local-dir ComfyUI/models/unet" "unet" &
PID1=$!

download_model "hf download QuantStack/Wan2.2-T2V-A14B-GGUF VAE/Wan2.1_VAE.safetensors --local-dir ComfyUI/models/vae" "vae1" &
PID2=$!

download_model "hf download Kijai/WanVideo_comfy Wan2_1_VAE_fp32.safetensors --local-dir ComfyUI/models/vae" "vae2" &
PID3=$!

download_model "hf download Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors --local-dir ComfyUI/models/loras" "lora1" &
PID4=$!

download_model "hf download Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/text_encoders/umt5_xxl_fp16.safetensors --local-dir ComfyUI/models/text_encoders" "text_encoder" &
PID5=$!

download_model "hf download Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/clip_vision/clip_vision_h.safetensors --local-dir ComfyUI/models/clip_vision" "clip_vision" &
PID6=$!

download_model "gdown 1wJOPRcKWUO01vqIX9UEPuQ0rSAP5Kkzh -O ComfyUI/models/loras/xxta-maya-naked-000220-draft1.safetensors" "lora2" &
PID7=$!

download_model "gdown 1pNF4pHnUgbreGuvZz5GSpBxeFjE0IOcn -O ComfyUI/models/loras/xxta-maya-clothed-000132.safetensors" "lora3" &
PID8=$!

echo "Model downloads started in background. Continuing with setup..."

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

# Wait for all model downloads to complete
echo "----------------------------------------"
echo "Waiting for model downloads to complete..."
echo "----------------------------------------"

FAILED=0
wait $PID1 || FAILED=$((FAILED + 1))
wait $PID2 || FAILED=$((FAILED + 1))
wait $PID3 || FAILED=$((FAILED + 1))
wait $PID4 || FAILED=$((FAILED + 1))
wait $PID5 || FAILED=$((FAILED + 1))
wait $PID6 || FAILED=$((FAILED + 1))
wait $PID7 || FAILED=$((FAILED + 1))
wait $PID8 || FAILED=$((FAILED + 1))

echo "----------------------------------------"
echo "Download Summary:"
echo "----------------------------------------"
for log in /workspace/download_logs/*.log; do
    echo "=== $(basename $log .log) ==="
    tail -1 "$log"
done
echo "----------------------------------------"

if [ $FAILED -gt 0 ]; then
    echo "WARNING: $FAILED download(s) failed. Check logs in /workspace/download_logs/"
    echo "Continuing anyway..."
else
    echo "All model downloads completed successfully!"
fi

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