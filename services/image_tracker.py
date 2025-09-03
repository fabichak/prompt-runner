"""Image tracking service for i2i workflow"""
import logging
from pathlib import Path
from typing import Set
from datetime import datetime

logger = logging.getLogger(__name__)


class ImageTracker:
    """Tracks processed and failed images for i2i workflow"""
    
    def __init__(self, processed_file: str, failed_file: str):
        self.processed_file = Path(processed_file)
        self.failed_file = Path(failed_file)
        self.processed_images = self._load_tracked_images(self.processed_file)
        self.failed_images = self._load_tracked_images(self.failed_file)
        
    def _load_tracked_images(self, file_path: Path) -> Set[str]:
        """Load tracked images from file"""
        tracked = set()
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            tracked.add(line)
                logger.info(f"Loaded {len(tracked)} images from {file_path}")
            except Exception as e:
                logger.error(f"Error loading tracked images from {file_path}: {e}")
        return tracked
    
    def is_processed(self, image_path: str) -> bool:
        """Check if image has been processed"""
        return str(image_path) in self.processed_images
    
    def is_failed(self, image_path: str) -> bool:
        """Check if image has failed before"""
        return str(image_path) in self.failed_images
    
    def should_process(self, image_path: str) -> bool:
        """Check if image should be processed"""
        return not (self.is_processed(image_path) or self.is_failed(image_path))
    
    def mark_processed(self, image_path: str):
        """Mark image as processed"""
        if str(image_path) not in self.processed_images:
            self.processed_images.add(str(image_path))
            self._append_to_file(self.processed_file, image_path)
            logger.info(f"Marked as processed: {image_path}")
    
    def mark_failed(self, image_path: str):
        """Mark image as failed"""
        if str(image_path) not in self.failed_images:
            self.failed_images.add(str(image_path))
            timestamp = datetime.now().isoformat()
            self._append_to_file(self.failed_file, f"{image_path} # Failed at {timestamp}")
            logger.warning(f"Marked as failed: {image_path}")
    
    def _append_to_file(self, file_path: Path, content: str):
        """Append content to tracking file"""
        try:
            with open(file_path, 'a') as f:
                f.write(f"{content}\n")
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
    
    def get_stats(self) -> dict:
        """Get tracking statistics"""
        return {
            "processed": len(self.processed_images),
            "failed": len(self.failed_images),
            "total": len(self.processed_images) + len(self.failed_images)
        }