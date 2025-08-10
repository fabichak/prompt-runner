import websocket
import uuid
import json
import urllib.request
import urllib.parse
import os
import random
import subprocess
import time
import copy
import argparse
import shutil
from datetime import datetime

# --- Configuration ---
SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())
JSON_WORKFLOW_FILE = "prompt.json"
INPUT_PROMPT_DIR = "prompt_files" # Directory for your prompt .txt files
GCS_BUCKET_PATH = "gs://aiof-saved-files/"
IMAGE_OUTPUT_DIR = "/workspace/ComfyUI/output/wan-image"

# --- Iteration Parameters ---
OFA1M1_STRENGTHS = [1.0]
STEPS = [8, 10, 12]
CFG_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
# New list of specific (sampler, scheduler) pairs to test
SAMPLER_PAIRS = [("ddim", "simple")]


# --- Helper Functions (no changes) ---
def queue_prompt(prompt, prompt_id):
    """Queues a prompt for execution."""
    try:
        p = {"prompt": prompt, "client_id": CLIENT_ID, "prompt_id": prompt_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
        urllib.request.urlopen(req)
        return prompt_id
    except urllib.error.URLError as e:
        print(f"Error queuing prompt: {e}")
        return None

def wait_for_prompt_completion(ws, prompt_id):
    """Waits for a specific prompt to finish execution."""
    print(f"Waiting for prompt {prompt_id} to complete...")
    while True:
        try:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message.get('type') == 'execution_success' and message['data'].get('prompt_id') == prompt_id:
                    print(f"Prompt {prompt_id} completed successfully.")
                    return True
                elif message.get('type') == 'execution_error' and message['data'].get('prompt_id') == prompt_id:
                    print(f"!!! Execution error for prompt {prompt_id}: {message['data']}")
                    return False
        except websocket.WebSocketConnectionClosedException:
            print("Websocket connection closed unexpectedly.")
            return False
        except Exception as e:
            print(f"An error occurred while waiting for prompt: {e}")
            return False

def zip_and_upload_output(directory_to_zip, gcs_path):
    """Zips the output directory and uploads it to GCS."""
    if not os.path.isdir(directory_to_zip):
        print(f"❌ Error: Output directory '{directory_to_zip}' not found. Nothing to zip.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name_base = f"image_generation_output_{timestamp}"
    archive_path = f"{archive_name_base}.zip"
    
    print(f"\nZipping output directory '{directory_to_zip}' to '{archive_path}'...")
    try:
        shutil.make_archive(archive_name_base, 'zip', directory_to_zip)
        print(f"✅ Zipping complete.")
    except Exception as e:
        print(f"❌ Error during zipping: {e}")
        return

    print(f"Uploading '{archive_path}' to '{gcs_path}'...")
    command = ["gcloud", "storage", "cp", archive_path, gcs_path]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ Upload successful.")
    except FileNotFoundError:
        print("❌ Error: 'gcloud' command not found.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during gcloud upload: {e.returncode}\n{e.stderr}")
    finally:
        # Clean up the local zip file
        if os.path.exists(archive_path):
            os.remove(archive_path)

def shutdown_runpod_instance():
    """Shuts down the RunPod instance."""
    print("\n" + "="*50 + "\nAll tasks complete. Shutting down the RunPod instance now.\n" + "="*50)
    pod_id = os.getenv("RUNPOD_POD_ID")
    if not pod_id:
        print("⚠️  Warning: RUNPOD_POD_ID not found. Cannot shut down instance.")
        return
    command = [f"runpodctl remove pod {pod_id}"]
    try:
        print(f"Executing shutdown command: {command}")
        subprocess.run(command, check=True, shell=True)
    except FileNotFoundError:
        print("❌ Error: 'runpodctl' command not found.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error shutting down pod: {e.returncode}\n{e.stderr}")

# --- Main Logic ---
def main():
    parser = argparse.ArgumentParser(description="Run ComfyUI image generation batch jobs.")
    parser.add_argument('--start-at', type=int, default=1, help='Job number to start from.')
    args = parser.parse_args()
    start_at_job = args.start_at

    try:
        with open(JSON_WORKFLOW_FILE, 'r') as f:
            base_workflow = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Workflow file not found at '{JSON_WORKFLOW_FILE}'")
        return
        
    # --- Read prompt files ---
    if not os.path.exists(INPUT_PROMPT_DIR):
        print(f"❌ Error: Input directory '{INPUT_PROMPT_DIR}' not found.")
        return
    prompt_files = [f for f in os.listdir(INPUT_PROMPT_DIR) if f.endswith('.txt')]
    if not prompt_files:
        print(f"❌ Error: No .txt files found in '{INPUT_PROMPT_DIR}'.")
        return

    ws = websocket.WebSocket()
    try:
        ws.connect(f"ws://{SERVER_ADDRESS}/ws?clientId={CLIENT_ID}")
        print("✅ Websocket connection established.")
    except Exception as e:
        print(f"❌ Failed to connect to websocket: {e}")
        return

    total_jobs = len(prompt_files) * len(OFA1M1_STRENGTHS) * len(SAMPLER_PAIRS) * len(CFG_SCALES) * len(STEPS)
    current_job = 0
    
    print(f"✅ Starting batch job. Found {len(prompt_files)} prompts. Total combinations: {total_jobs}")
    if start_at_job > 1:
        print(f"⏩ Resuming from job number {start_at_job}.")

    try:
        for txt_filename in prompt_files:
            for strength in OFA1M1_STRENGTHS:
                for sampler, scheduler in SAMPLER_PAIRS:
                    for cfg in CFG_SCALES:
                        for step_count in STEPS:
                            current_job += 1
                            
                            if current_job < start_at_job:
                                if current_job % 100 == 0:
                                    print(f"⏭️  Skipping Job {current_job}/{total_jobs}...")
                                continue

                            start_time = time.monotonic()
                            print("\n" + "-"*50)
                            print(f"Processing Job {current_job}/{total_jobs} at {datetime.now().strftime('%H:%M:%S')}")
                            
                            # Read prompt from file
                            with open(os.path.join(INPUT_PROMPT_DIR, txt_filename), 'r') as f:
                                positive_prompt = f.read().strip()

                            prompt_workflow = copy.deepcopy(base_workflow)
                            
                            # Update workflow with current iteration values
                            prompt_workflow["23"]["inputs"]["text"] = positive_prompt # Update prompt
                            prompt_workflow["39"]["inputs"]["strength_model"] = strength
                            prompt_workflow["13"]["inputs"]["cfg"] = cfg
                            prompt_workflow["13"]["inputs"]["sampler_name"] = sampler
                            prompt_workflow["13"]["inputs"]["scheduler"] = scheduler
                            prompt_workflow["13"]["inputs"]["steps"] = step_count
                            prompt_workflow["13"]["inputs"]["seed"] = 124587
                            
                            # Create unique filename prefix
                            prompt_name = os.path.splitext(txt_filename)[0]
                            filename_prefix = f"wan-image/{sampler}_{scheduler}/str{strength}_cfg{cfg}_step{step_count}_{prompt_name}"
                            prompt_workflow["15"]["inputs"]["filename_prefix"] = filename_prefix
                            prompt_workflow["49"]["inputs"]["filename_prefix"] = f"{filename_prefix}_post"

                            print(f"  - Prompt File: {txt_filename}")
                            print(f"  - LoRA Strength: {strength}, CFG: {cfg}, Steps: {step_count}")
                            print(f"  - Sampler: {sampler}, Scheduler: {scheduler}")
                                    
                            prompt_id = str(uuid.uuid4())
                            queue_prompt(prompt_workflow, prompt_id)
                            wait_for_prompt_completion(ws, prompt_id)

                            duration = time.monotonic() - start_time
                            minutes, seconds = divmod(duration, 60)
                            print(f"Job took {int(minutes)} minutes and {seconds:.2f} seconds")

    finally:
        print("\nClosing websocket connection.")
        ws.close()

    # After all images are generated, zip the output and upload
    zip_and_upload_output(IMAGE_OUTPUT_DIR, GCS_BUCKET_PATH)

    # Finally, shut down the instance
    #shutdown_runpod_instance()

if __name__ == "__main__":
    main()