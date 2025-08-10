#!/usr/bin/env python3
"""
Simple test script for dry-run mode functionality
"""
import sys
import os
import tempfile
from pathlib import Path

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_dry_run_imports():
    """Test that all dry-run imports work correctly"""
    print("🧪 Testing dry-run imports...")
    
    try:
        from services.dry_run_manager import DryRunManager, is_dry_run, enable_dry_run
        from services.mock_comfyui_client import MockComfyUIClient
        from services.mock_storage_manager import MockStorageManager
        from services.mock_runpod_manager import MockRunPodManager
        from services.service_factory import ServiceFactory
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_dry_run_manager():
    """Test dry-run manager functionality"""
    print("🧪 Testing DryRunManager...")
    
    try:
        from services.dry_run_manager import DryRunManager, enable_dry_run, dry_run_manager
        
        # Enable dry-run mode
        enable_dry_run()
        
        # Test workflow saving
        test_workflow = {
            "1": {"class_type": "TestNode", "inputs": {"value": 42}},
            "2": {"class_type": "OutputNode", "inputs": {"input": ["1", 0]}}
        }
        
        test_job_info = {
            "type": "test_render",
            "job_id": "test-123",
            "modifications": ["Test modification"]
        }
        
        filename = dry_run_manager.save_workflow(test_workflow, test_job_info)
        print(f"✅ Workflow saved: {filename}")
        
        # Test summary
        summary = dry_run_manager.get_summary()
        print(f"✅ Summary generated: {summary['workflows_generated']} workflows")
        
        return True
    except Exception as e:
        print(f"❌ DryRunManager error: {e}")
        return False

def test_mock_services():
    """Test mock service implementations"""
    print("🧪 Testing mock services...")
    
    try:
        from services.service_factory import ServiceFactory
        
        # Test mock ComfyUI client
        client = ServiceFactory.create_comfyui_client()
        if client.connect():
            print("✅ MockComfyUIClient connection test passed")
        
        # Test mock storage manager
        storage = ServiceFactory.create_storage_manager()
        storage.ensure_directories()
        print("✅ MockStorageManager directory test passed")
        
        # Test mock RunPod manager
        runpod = ServiceFactory.create_runpod_manager()
        info = runpod.get_instance_info()
        print(f"✅ MockRunPodManager info test passed: {info['pod_id']}")
        
        return True
    except Exception as e:
        print(f"❌ Mock services error: {e}")
        return False

def test_workflow_generation():
    """Test workflow generation with mock client"""
    print("🧪 Testing workflow generation...")
    
    try:
        from services.service_factory import ServiceFactory
        
        client = ServiceFactory.create_comfyui_client()
        
        # Test workflow execution
        test_workflow = {
            "nodes": {
                "1": {"class_type": "TestNode", "inputs": {"prompt": "test prompt"}},
                "2": {"class_type": "SaveVideo", "inputs": {"filename": "test.mp4"}}
            }
        }
        
        success, prompt_id, error = client.execute_with_retry(test_workflow)
        if success:
            print(f"✅ Workflow execution simulation passed: {prompt_id}")
        else:
            print(f"❌ Workflow execution failed: {error}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Workflow generation error: {e}")
        return False

def main():
    """Run all dry-run tests"""
    print("🎭 DRY-RUN MODE TESTING")
    print("=" * 50)
    
    tests = [
        test_dry_run_imports,
        test_dry_run_manager,
        test_mock_services,
        test_workflow_generation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All dry-run tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)