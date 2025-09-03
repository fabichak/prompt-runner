"""Image scanner service for i2i workflow"""
import logging
from pathlib import Path
from typing import List, Set
from config import I2I_SUPPORTED_IMAGE_FORMATS, I2I_EXCLUDED_FOLDERS

logger = logging.getLogger(__name__)


class ImageScanner:
    """Scans directories for image files"""
    
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created i2i input directory: {self.base_dir}")
    
    def scan_for_images(self) -> List[Path]:
        """Scan directory and subdirectories for image files"""
        images = []
        
        try:
            for path in self._recursive_scan(self.base_dir):
                if self._is_valid_image(path):
                    images.append(path)
            
            logger.info(f"Found {len(images)} image files in {self.base_dir}")
            return sorted(images)  # Return sorted for consistent ordering
            
        except Exception as e:
            logger.error(f"Error scanning for images: {e}")
            return []
    
    def _recursive_scan(self, directory: Path) -> List[Path]:
        """Recursively scan directory, excluding specified folders"""
        all_files = []
        
        try:
            for item in directory.iterdir():
                if item.is_dir():
                    # Skip excluded folders and their subdirectories
                    if item.name in I2I_EXCLUDED_FOLDERS:
                        logger.debug(f"Skipping excluded folder: {item}")
                        continue
                    # Recursively scan subdirectory
                    all_files.extend(self._recursive_scan(item))
                elif item.is_file():
                    all_files.append(item)
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {directory}: {e}")
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
        
        return all_files
    
    def _is_valid_image(self, path: Path) -> bool:
        """Check if file is a valid image based on extension"""
        return path.suffix.lower() in I2I_SUPPORTED_IMAGE_FORMATS
    
    def find_new_images(self, tracked_images: Set[str]) -> List[Path]:
        """Find images that haven't been tracked yet"""
        all_images = self.scan_for_images()
        new_images = [
            img for img in all_images 
            if str(img.absolute()) not in tracked_images
        ]
        
        if new_images:
            logger.info(f"Found {len(new_images)} new images to process")
            for img in new_images[:5]:  # Log first 5 for brevity
                logger.debug(f"  - {img.name}")
            if len(new_images) > 5:
                logger.debug(f"  ... and {len(new_images) - 5} more")
        
        return new_images