# I2I (Image-to-Image) Workflow Documentation

## Overview
The i2i workflow processes images through ComfyUI with multiple CFG values and render iterations per image.

## Configuration

### Edit `config.py` to set up your i2i workflow:

```python
# REQUIRED: Fill in your desired CFG values
I2I_CFG_VALUES = [
    2.5,  # Low CFG
    3.0,
    3.5,
    4.0,
    4.5,  # High CFG
]

# Number of renders per CFG value (default: 4)
I2I_IMAGE_RENDER_AMOUNT = 4

# Poll interval for new images (seconds)
I2I_POLL_INTERVAL = 10
```

### File Structure
```
prompt-runner/
├── prompts/
│   └── i2i.json          # i2i workflow file
├── i2i-files/            # Input images directory
│   ├── image1.jpg
│   ├── subfolder/
│   │   └── image2.png
│   └── _old/             # Excluded folder (ignored)
│       └── archived.jpg
├── i2i_processed_images.txt  # Tracking file (auto-created)
└── i2i_failed_images.txt     # Failed images log (auto-created)
```

## Usage

### Basic Usage
```bash
# Process all images once
python main.py --mode i2i

# Continuously monitor for new images
python main.py --mode i2i --continuous
```

### Command Line Options
- `--mode i2i` - Enable i2i mode (required)
- `--continuous` - Keep monitoring for new images
- `--log-level DEBUG` - Show detailed logging
- `--no-shutdown` - Don't shutdown RunPod after completion

## How It Works

1. **Image Scanning**: Scans `i2i-files/` directory for images
   - Supports: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`
   - Excludes: `_old` folder and its subdirectories
   - Processes all subdirectories except excluded ones

2. **Processing**: For each image:
   - Renders with each CFG value in `I2I_CFG_VALUES`
   - Renders `I2I_IMAGE_RENDER_AMOUNT` times per CFG value
   - Total renders per image = len(CFG_VALUES) × IMAGE_RENDER_AMOUNT
   - Example: 5 CFG values × 4 renders = 20 outputs per image

3. **Output Naming**: 
   - Format: `{original_name}_cfg{value}_render{number}.png`
   - Example: `photo_cfg3.5_render2.png`

4. **Tracking**:
   - Processed images recorded in `i2i_processed_images.txt`
   - Failed images logged in `i2i_failed_images.txt` with timestamp
   - Images are never reprocessed unless tracking files are cleared

5. **Continuous Mode**:
   - Polls directory every `I2I_POLL_INTERVAL` seconds
   - Processes new images automatically
   - Skips already processed/failed images

## Workflow Modification Points

The i2i workflow modifies these nodes in `prompts/i2i.json`:
- **Node 365**: Input image path
- **Node 53**: Output filename prefix
- **Node 334**: CFG value and seed

## Example Scenarios

### Batch Processing
Place 10 images in `i2i-files/`, with CFG values [3.0, 4.0, 5.0] and 3 renders each:
- Total outputs: 10 images × 3 CFG × 3 renders = 90 images

### Continuous Processing
1. Start with `--continuous` flag
2. Drop new images into `i2i-files/` at any time
3. System automatically detects and processes them
4. Use Ctrl+C to stop

### Organizing Images
```
i2i-files/
├── portraits/
│   ├── person1.jpg
│   └── person2.jpg
├── landscapes/
│   ├── mountain.png
│   └── ocean.jpg
└── _old/           # These won't be processed
    └── test.jpg
```

## Troubleshooting

### Images Not Processing
- Check `i2i_processed_images.txt` - image might be already processed
- Check `i2i_failed_images.txt` - image might have failed
- Verify image format is supported
- Check image is not in `_old` folder

### Reset Processing
To reprocess all images:
```bash
rm i2i_processed_images.txt i2i_failed_images.txt
```

### View Logs
```bash
# View processed images
cat i2i_processed_images.txt

# View failed images with timestamps
cat i2i_failed_images.txt
```

## Important Notes

1. **Random Seeds**: Each render uses a random seed for variation
2. **File Paths**: System uses absolute paths for compatibility
3. **Memory Usage**: Large batches may require monitoring memory
4. **Network**: Ensure ComfyUI server is accessible
5. **Storage**: Each image generates multiple outputs - plan storage accordingly