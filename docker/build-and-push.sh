#!/bin/bash
# Docker Build and Push Script
# Optimized for large images with CUDA support

# Configuration - CHANGE THESE VALUES
DOCKER_USERNAME="tlftlf"
IMAGE_NAME="comfyui-312-128-base"
TAG="latest"

# Full image name
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${TAG}"

echo "========================================="
echo "Docker Build and Push Script"
echo "Image: ${FULL_IMAGE_NAME}"
echo "========================================="

# Check Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker daemon is not running!"
    exit 1
fi

# Clean up Docker cache to prevent SIGBUS errors
echo "Cleaning Docker cache to prevent build issues..."
docker builder prune -f
docker system prune -f

# Check available disk space
AVAILABLE_SPACE=$(df -h . | awk 'NR==2 {print $4}')
echo "Available disk space: ${AVAILABLE_SPACE}"

# Build the image with optimizations for large builds
echo "----------------------------------------"
echo "Building image with optimizations..."
echo "This may take 10-20 minutes..."
echo "----------------------------------------"

# Try building with buildx first (faster, but may cause SIGBUS)
if docker buildx version > /dev/null 2>&1; then
    echo "Using Docker Buildx..."
    docker buildx build \
        --no-cache \
        --output type=docker \
        --progress=plain \
        -t ${FULL_IMAGE_NAME} .
    BUILD_RESULT=$?
else
    # Fallback to regular build
    echo "Using standard Docker build..."
    docker build \
        --no-cache \
        --progress=plain \
        -t ${FULL_IMAGE_NAME} .
    BUILD_RESULT=$?
fi

# If build failed with SIGBUS, try legacy builder
if [ $BUILD_RESULT -ne 0 ]; then
    echo "Build failed! Attempting with legacy builder..."
    DOCKER_BUILDKIT=0 docker build \
        --no-cache \
        -t ${FULL_IMAGE_NAME} .
    BUILD_RESULT=$?
fi

if [ $BUILD_RESULT -ne 0 ]; then
    echo "========================================="
    echo "Build failed!"
    echo "Troubleshooting tips:"
    echo "1. Increase Docker Desktop memory (Settings > Resources > Memory)"
    echo "2. Free up disk space (need at least 20GB)"
    echo "3. Try: docker system prune -a --volumes"
    echo "4. Restart Docker Desktop"
    echo "========================================="
    exit 1
fi

echo "========================================="
echo "Build successful!"
echo "========================================="

# Get image details
echo "Getting image information..."
IMAGE_SIZE=$(docker image inspect ${FULL_IMAGE_NAME} --format='{{.Size}}' 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "Unknown")
IMAGE_ID=$(docker image inspect ${FULL_IMAGE_NAME} --format='{{.Id}}' 2>/dev/null | cut -d: -f2 | cut -c1-12)
echo "Image ID: ${IMAGE_ID}"
echo "Image size: ${IMAGE_SIZE}"
echo ""

# Ask if user wants to push to Docker Hub
read -p "Do you want to push to Docker Hub? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Login to Docker Hub
    echo "----------------------------------------"
    echo "Logging in to Docker Hub..."
    echo "----------------------------------------"
    docker login -u ${DOCKER_USERNAME}
    
    if [ $? -ne 0 ]; then
        echo "Login failed!"
        exit 1
    fi
    
    # Push to Docker Hub with retry logic
    echo "----------------------------------------"
    echo "Pushing image to Docker Hub..."
    echo "This may take several minutes for large images..."
    echo "----------------------------------------"
    
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        docker push ${FULL_IMAGE_NAME}
        
        if [ $? -eq 0 ]; then
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Push failed. Retrying in 10 seconds... (Attempt $((RETRY_COUNT + 1)) of $MAX_RETRIES)"
            sleep 10
        else
            echo "Push failed after $MAX_RETRIES attempts!"
            echo "Try: docker push ${FULL_IMAGE_NAME} manually"
            exit 1
        fi
    done
else
    echo "Skipping Docker Hub push."
fi

echo "========================================="
echo "Process Complete!"
echo "========================================="
echo ""
echo "Image: ${FULL_IMAGE_NAME}"
echo "Size: ${IMAGE_SIZE}"
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Image available at: docker.io/${FULL_IMAGE_NAME}"
    echo ""
else
    echo "Image available locally as: ${FULL_IMAGE_NAME}"
    echo "To push later: docker push ${FULL_IMAGE_NAME}"
    echo ""
fi

echo "----------------------------------------"
echo "VastAI Usage Instructions:"
echo "----------------------------------------"
echo "1. Create new instance"
echo "2. Template/Image: ${FULL_IMAGE_NAME}"
echo "3. On-start script:"
echo "   cd /workspace && gdown YOUR_INIT_SCRIPT_ID -O runtime-init.sh && chmod +x runtime-init.sh && bash runtime-init.sh"
echo ""
echo "Or use this one-liner in on-start:"
echo "   cd /workspace && gdown 1fOqig7aJHJNdFt_4124x5ouxIgdCaT0I -O init.sh && dos2unix init.sh && bash init.sh"
echo ""
echo "----------------------------------------"
echo "Image Specifications:"
echo "----------------------------------------"
echo "- Base: vastai/pytorch:cuda-12.8.1-auto"
echo "- Python: 3.12"
echo "- PyTorch: 2.5.1 with CUDA 12.4 (compatible with CUDA 12.8)"
echo "- Includes: ML/AI packages, ComfyUI dependencies, Google Cloud SDK"
echo "========================================="