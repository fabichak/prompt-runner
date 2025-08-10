#!/usr/bin/env python3
"""
Comprehensive test suite for Prompt Runner v2
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Import modules to test
from models.prompt_data import PromptData
from models.job import RenderJob, CombineJob, JobType, JobStatus
from models.job_result import JobResult
from utils.file_parser import PromptFileParser
from utils.job_planner import JobPlanner
from services.workflow_manager import WorkflowManager
from services.storage_utils import StorageManager
from config import FRAMES_TO_RENDER


class TestPromptData(unittest.TestCase):
    """Test PromptData model"""
    
    def test_valid_prompt_data(self):
        """Test creating valid prompt data"""
        data = PromptData(
            video_name="test_video",
            total_frames=500,
            positive_prompt="A beautiful scene",
            negative_prompt="blurry, low quality"
        )
        self.assertTrue(data.validate())
        self.assertEqual(str(data), "PromptData(video=test_video, frames=500)")
    
    def test_invalid_prompt_data(self):
        """Test validation of invalid prompt data"""
        # Empty video name
        with self.assertRaises(ValueError):
            data = PromptData("", 500, "prompt", "")
            data.validate()
        
        # Invalid frame count
        with self.assertRaises(ValueError):
            data = PromptData("video", -1, "prompt", "")
            data.validate()


class TestFileParser(unittest.TestCase):
    """Test prompt file parsing"""
    
    def setUp(self):
        """Create temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.txt"
    
    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir)
    
    def test_parse_valid_file(self):
        """Test parsing a valid prompt file"""
        content = """test_video.mp4

500

A beautiful sunset over the ocean

blurry, low quality"""
        
        self.test_file.write_text(content)
        
        parser = PromptFileParser()
        data = parser.parse_prompt_file(self.test_file)
        
        self.assertIsNotNone(data)
        self.assertEqual(data.video_name, "test_video")
        self.assertEqual(data.total_frames, 500)
        self.assertEqual(data.positive_prompt, "A beautiful sunset over the ocean")
        self.assertEqual(data.negative_prompt, "blurry, low quality")
    
    def test_parse_invalid_file(self):
        """Test parsing invalid files"""
        # Missing parts
        content = """test_video

500"""
        self.test_file.write_text(content)
        
        parser = PromptFileParser()
        data = parser.parse_prompt_file(self.test_file)
        self.assertIsNone(data)
    
    def test_validate_directory(self):
        """Test validating prompt directory"""
        # Create valid and invalid files
        valid_file = Path(self.test_dir) / "valid.txt"
        valid_content = """video1

101

Prompt

Negative"""
        valid_file.write_text(valid_content)
        
        invalid_file = Path(self.test_dir) / "invalid.txt"
        invalid_file.write_text("invalid content")
        
        parser = PromptFileParser()
        files = parser.validate_prompt_directory(Path(self.test_dir))
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0][1].video_name, "video1")


class TestJobPlanner(unittest.TestCase):
    """Test job planning logic"""
    
    def test_calculate_job_sequence(self):
        """Test job sequence calculation"""
        prompt_data = PromptData(
            video_name="test",
            total_frames=303,  # Should create 3 job pairs (101, 101, 101)
            positive_prompt="positive",
            negative_prompt="negative"
        )
        
        planner = JobPlanner(frames_per_chunk=101)
        render_jobs, combine_jobs = planner.calculate_job_sequence(prompt_data)
        
        # Should have 6 render jobs (3 HIGH, 3 LOW)
        self.assertEqual(len(render_jobs), 6)
        
        # Should have 3 combine jobs (one for each LOW output)
        self.assertEqual(len(combine_jobs), 3)
        
        # Check job types alternate
        self.assertEqual(render_jobs[0].job_type, JobType.HIGH)
        self.assertEqual(render_jobs[1].job_type, JobType.LOW)
        self.assertEqual(render_jobs[2].job_type, JobType.HIGH)
        self.assertEqual(render_jobs[3].job_type, JobType.LOW)
        
        # Check frame counts
        self.assertEqual(render_jobs[0].frames_to_render, 101)
        self.assertEqual(render_jobs[2].frames_to_render, 101)
        self.assertEqual(render_jobs[4].frames_to_render, 101)
        
        # Check reference images (jobs 3+ should have them)
        self.assertIsNone(render_jobs[0].reference_image_path)  # Job 1
        self.assertIsNone(render_jobs[1].reference_image_path)  # Job 2
        self.assertIsNotNone(render_jobs[2].reference_image_path)  # Job 3
    
    def test_job_dependencies(self):
        """Test job dependency calculation"""
        planner = JobPlanner()
        
        # HIGH job 1 has no dependencies
        high_job_1 = RenderJob(job_type=JobType.HIGH, job_number=1)
        deps = planner.get_job_dependencies(high_job_1)
        self.assertEqual(deps, [])
        
        # LOW job 2 depends on HIGH job 1
        low_job_2 = RenderJob(job_type=JobType.LOW, job_number=2)
        deps = planner.get_job_dependencies(low_job_2)
        self.assertEqual(deps, [1])
        
        # HIGH job 3 depends on LOW job 2 (for reference)
        high_job_3 = RenderJob(job_type=JobType.HIGH, job_number=3)
        deps = planner.get_job_dependencies(high_job_3)
        self.assertEqual(deps, [1])  # Job 3 depends on job 1 (3-2=1)
    
    def test_validate_job_sequence(self):
        """Test job sequence validation"""
        planner = JobPlanner()
        
        # Valid sequence
        jobs = [
            RenderJob(job_type=JobType.HIGH, job_number=1, frames_to_render=101),
            RenderJob(job_type=JobType.LOW, job_number=2, frames_to_render=101),
        ]
        self.assertTrue(planner.validate_job_sequence(jobs, 101))
        
        # Invalid - frame mismatch
        jobs = [
            RenderJob(job_type=JobType.HIGH, job_number=1, frames_to_render=50),
            RenderJob(job_type=JobType.LOW, job_number=2, frames_to_render=50),
        ]
        self.assertFalse(planner.validate_job_sequence(jobs, 101))
    
    def test_reference_frame_calculation(self):
        """Test reference frame extraction logic"""
        planner = JobPlanner()
        
        # Normal case - should be frames - 10
        frame = planner.calculate_reference_frame(101)
        self.assertEqual(frame, 91)
        
        # Edge case - too few frames
        frame = planner.calculate_reference_frame(5)
        self.assertEqual(frame, 0)


class TestWorkflowManager(unittest.TestCase):
    """Test workflow modification"""
    
    def setUp(self):
        """Create test workflows"""
        self.base_workflow = {
            "309": {"inputs": {"lora_name": "default"}},
            "4": {"inputs": {"gguf_name": "default"}},
            "144": {"inputs": {"image": ""}},
            "54": {"inputs": {}},
            "365": {"inputs": {}},
            "341": {"inputs": {}},
            "19": {"inputs": {"value": 0}},
            "348": {"inputs": {"start_frame": 0}}
        }
        
        self.combine_workflow = {
            "25": {"inputs": {"videos": ""}},
            "30": {"inputs": {"image_2": ""}},
            "14": {"inputs": {"images": []}}
        }
        
        # Create temp files
        self.test_dir = tempfile.mkdtemp()
        self.base_path = Path(self.test_dir) / "prompt.json"
        self.combine_path = Path(self.test_dir) / "combine.json"
        
        with open(self.base_path, 'w') as f:
            json.dump(self.base_workflow, f)
        with open(self.combine_path, 'w') as f:
            json.dump(self.combine_workflow, f)
    
    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.test_dir)
    
    def test_modify_for_high_job(self):
        """Test workflow modification for HIGH job"""
        manager = WorkflowManager(self.base_path, self.combine_path)
        
        job = RenderJob(
            job_type=JobType.HIGH,
            job_number=1,
            frames_to_render=101,
            positive_prompt="test",
            negative_prompt="negative"
        )
        
        workflow = manager.modify_for_high_job(job)
        
        # Check LoRA is set to HIGH
        self.assertEqual(workflow["309"]["inputs"]["lora_name"], "wan2.2_high_t2v.safetensors")
        
        # Check model is set to HIGH
        self.assertEqual(workflow["4"]["inputs"]["gguf_name"], "Wan2.2_HIGH_Low_Noise_14B_VACE-Q8_0.gguf")
        
        # Check samples nodes are deleted
        self.assertNotIn("54", workflow)
        self.assertNotIn("341", workflow)
        
        # Check frames value is set
        self.assertEqual(workflow["19"]["inputs"]["value"], 101)
    
    def test_modify_for_low_job(self):
        """Test workflow modification for LOW job"""
        manager = WorkflowManager(self.base_path, self.combine_path)
        
        job = RenderJob(
            job_type=JobType.LOW,
            job_number=2,
            frames_to_render=101,
            latent_input_path="test_latent.safetensors"
        )
        
        workflow = manager.modify_for_low_job(job)
        
        # Check LoRA is set to LOW
        self.assertEqual(workflow["309"]["inputs"]["lora_name"], "wan2.2_low_t2v.safetensors")
        
        # Check model is set to LOW
        self.assertEqual(workflow["4"]["inputs"]["gguf_name"], "Wan2.2_T2V_Low_Noise_14B_VACE-Q8_0.gguf")
        
        # Check latent node is deleted
        self.assertNotIn("365", workflow)
    
    def test_create_combine_workflow(self):
        """Test combine workflow creation"""
        manager = WorkflowManager(self.base_path, self.combine_path)
        
        # First combine job
        job1 = CombineJob(
            combine_number=1,
            input_video_path="video1.mp4",
            output_path="combined1.mp4"
        )
        
        workflow1 = manager.create_combine_workflow(job1)
        
        # Check video input is set
        self.assertEqual(workflow1["25"]["inputs"]["videos"], "video1.mp4")
        
        # Check image_2 node is removed for first combine
        self.assertNotIn("30", workflow1)
        
        # Check images is set to [33, 0]
        self.assertEqual(workflow1["14"]["inputs"]["images"], [33, 0])
        
        # Subsequent combine job
        job2 = CombineJob(
            combine_number=2,
            input_video_path="video2.mp4",
            previous_combined_path="combined1.mp4",
            output_path="combined2.mp4"
        )
        
        workflow2 = manager.create_combine_workflow(job2)
        
        # Check previous combined is set
        self.assertEqual(workflow2["30"]["inputs"]["image_2"], "combined1.mp4")


class TestStorageManager(unittest.TestCase):
    """Test storage utilities"""
    
    def setUp(self):
        """Create test directory"""
        self.test_dir = tempfile.mkdtemp()
        # Temporarily override base directory
        import config
        self.original_base = config.BASE_OUTPUT_DIR
        config.BASE_OUTPUT_DIR = Path(self.test_dir)
        config.LATENTS_DIR = Path(self.test_dir) / "latents"
        config.VIDEOS_DIR = Path(self.test_dir) / "videos"
        config.REFERENCES_DIR = Path(self.test_dir) / "references"
        config.COMBINED_DIR = Path(self.test_dir) / "combined"
        config.FINAL_DIR = Path(self.test_dir) / "final"
        config.STATE_DIR = Path(self.test_dir) / "state"
    
    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.test_dir)
        # Restore original config
        import config
        config.BASE_OUTPUT_DIR = self.original_base
    
    def test_ensure_directories(self):
        """Test directory creation"""
        storage = StorageManager()
        
        # Check all directories exist
        self.assertTrue((Path(self.test_dir) / "latents").exists())
        self.assertTrue((Path(self.test_dir) / "videos").exists())
        self.assertTrue((Path(self.test_dir) / "references").exists())
        self.assertTrue((Path(self.test_dir) / "combined").exists())
        self.assertTrue((Path(self.test_dir) / "final").exists())
        self.assertTrue((Path(self.test_dir) / "state").exists())
    
    def test_path_generation(self):
        """Test path generation methods"""
        storage = StorageManager()
        
        # Test latent path
        path = storage.get_latent_path("test_video", 1)
        self.assertEqual(path.name, "job_001.latent")
        self.assertTrue("test_video" in str(path))
        
        # Test video path
        path = storage.get_video_path("test_video", 2)
        self.assertEqual(path.name, "job_002.mp4")
        
        # Test reference path
        path = storage.get_reference_path("test_video", 3)
        self.assertEqual(path.name, "job_003_ref.png")
        
        # Test combined path
        path = storage.get_combined_path("test_video", 1)
        self.assertEqual(path.name, "combined_001.mp4")
        
        # Test final path
        path = storage.get_final_path("test_video")
        self.assertEqual(path.name, "test_video_final.mp4")
    
    def test_state_management(self):
        """Test state save/load"""
        storage = StorageManager()
        
        # Save state
        state_data = {
            "video_name": "test",
            "completed_jobs": [1, 2, 3],
            "failed_jobs": []
        }
        storage.save_state("test_video", state_data)
        
        # Load state
        loaded = storage.load_state("test_video")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["video_name"], "test")
        self.assertEqual(loaded["completed_jobs"], [1, 2, 3])
        
        # Clear state
        storage.clear_state("test_video")
        loaded = storage.load_state("test_video")
        self.assertIsNone(loaded)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_full_job_planning(self):
        """Test complete job planning workflow"""
        # Create prompt data
        prompt_data = PromptData(
            video_name="integration_test",
            total_frames=202,  # 2 chunks of 101
            positive_prompt="A test prompt",
            negative_prompt="negative"
        )
        
        # Plan jobs
        planner = JobPlanner(frames_per_chunk=101)
        render_jobs, combine_jobs = planner.calculate_job_sequence(prompt_data)
        
        # Validate
        self.assertTrue(planner.validate_job_sequence(render_jobs, 202))
        
        # Check job count
        self.assertEqual(len(render_jobs), 4)  # 2 HIGH, 2 LOW
        self.assertEqual(len(combine_jobs), 2)  # 2 combines
        
        # Check dependencies
        self.assertTrue(planner.can_job_run(render_jobs[0], []))  # Job 1 can run
        self.assertFalse(planner.can_job_run(render_jobs[1], []))  # Job 2 needs job 1
        self.assertTrue(planner.can_job_run(render_jobs[1], [1]))  # Job 2 can run after 1
        
        # Check combine job setup
        self.assertEqual(combine_jobs[0].combine_number, 1)
        self.assertIsNone(combine_jobs[0].previous_combined_path)
        self.assertEqual(combine_jobs[1].combine_number, 2)
        self.assertIsNotNone(combine_jobs[1].previous_combined_path)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPromptData))
    suite.addTests(loader.loadTestsFromTestCase(TestFileParser))
    suite.addTests(loader.loadTestsFromTestCase(TestJobPlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkflowManager))
    suite.addTests(loader.loadTestsFromTestCase(TestStorageManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)