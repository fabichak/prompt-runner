# job_planner.py
import logging
from pathlib import Path
from typing import List, Optional
import requests

from models.prompt_data import PromptData
from models.job import RenderJob
from config import FRAMES_TO_RENDER
from services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

def _is_url(s: Optional[str]) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))

class JobPlanner:
    """Plans and calculates job sequences for video generation"""

    def __init__(self, promptName, frames_per_chunk: int = FRAMES_TO_RENDER):
        self.frames_per_chunk = frames_per_chunk
        self.promptName = promptName
        self.storage = ServiceFactory.create_storage_manager()

    def _download_file(self, url: str, out_path: Path) -> str:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return str(out_path.resolve())

    def calculate_job_sequence(
        self,
        prompt_data: PromptData,
        reference_image_path: Optional[str] = None,
        reference_video_path: Optional[str] = None,
    ) -> List[RenderJob]:
        """Calculate the complete job sequence for a prompt"""

        render_jobs: List[RenderJob] = []
        job_number = 1

        # Ensure standard output dirs exist
        self.storage.ensure_directories(self.promptName)

        # Choose a stable inputs staging dir under your run output
        inputs_dir = Path("output") / "prompt-runner" / self.promptName / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        # Base name to infer defaults when args are missing
        base = Path(prompt_data.source_file) if prompt_data.source_file else Path(self.promptName)

        # Build specs: could be URL or local path, or None -> fallback to <base>.ext
        video_spec = reference_video_path or str(base.with_suffix(".mp4"))
        image_spec = reference_image_path or str(base.with_suffix(".png"))

        logger.info("Starting download of" + video_spec + " and " + image_spec)

        # Materialize video
        if _is_url(video_spec):
            video_local = self._download_file(video_spec, inputs_dir / "input.mp4")
        else:
            vp = Path(video_spec)
            if not vp.exists():
                raise FileNotFoundError(f"Video not found: {video_spec}")
            video_local = str(vp.resolve())

        # Materialize image
        if _is_url(image_spec):
            image_local = self._download_file(image_spec, inputs_dir / "input.png")
        else:
            ip = Path(image_spec)
            if not ip.exists():
                raise FileNotFoundError(f"Image not found: {image_spec}")
            image_local = str(ip.resolve())

        random_seed = 1013166398531279
        logger.info(
            "Creating job %s %d with frames %d",
            prompt_data.source_file, job_number, prompt_data.total_frames
        )

        render_job = RenderJob(
            prompt_name=self.promptName,
            job_number=job_number,
            seed=random_seed,
            start_frame=prompt_data.start_frame,
            frames_to_render=prompt_data.total_frames,
            video_input_path=video_local,
            reference_image_path=image_local,
            positive_prompt=prompt_data.positive_prompt,
            negative_prompt=prompt_data.negative_prompt,
            video_output_path=self.storage.get_video_path(self.promptName, job_number),
            video_output_full_path=self.storage.get_video_full_path(self.promptName, job_number),
        )

        render_jobs.append(render_job)
        return render_jobs
