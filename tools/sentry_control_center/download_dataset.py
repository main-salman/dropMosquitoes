# Implements: SW-001 §7.2 — Sniper Training Dataset Ingestion
import os
import sys
from dotenv import load_dotenv

def main():
    print("[Dataset Downloader] Initializing Roboflow multi-bug dataset download...")
    
    # 1. Resolve paths and load .env file
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env_path = os.path.join(project_root, ".env")
    
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print(f"[Dataset Downloader] Loaded environment secrets from: {env_path}")
    else:
        print(f"[Dataset Downloader] ERROR: .env file not found at: {env_path}")
        sys.exit(1)
        
    # 2. Extract API Key
    api_key = os.getenv("ROBOFLOW_API_KEY")
    if not api_key:
        print("[Dataset Downloader] ERROR: ROBOFLOW_API_KEY is not defined in your .env file.")
        sys.exit(1)
        
    print("[Dataset Downloader] Authenticating with Roboflow API...")
    
    # 3. Import roboflow (ensure installed)
    try:
        from roboflow import Roboflow
    except ImportError:
        print("[Dataset Downloader] roboflow package not found. Attempting to install...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "roboflow"])
        from roboflow import Roboflow
        
    # 4. Download dataset
    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "dataset"))
    target_location = os.path.join(dataset_dir, "insects")
    
    print(f"[Dataset Downloader] Downloading 'tiger-emltm/insects-9yf6s' version 2 to {target_location}...")
    try:
        rf = Roboflow(api_key=api_key)
        project = rf.workspace("tiger-emltm").project("insects-9yf6s")
        dataset = project.version(2).download(model_format="yolov8", location=target_location)
        
        print("\n" + "=" * 60)
        print("✅ DATASET DOWNLOADED SUCCESSFULLY!")
        print(f"Location: {target_location}")
        yaml_path = os.path.join(target_location, "data.yaml")
        if os.path.exists(yaml_path):
            print(f"data.yaml Path: {yaml_path}")
            
            # Print classes in the dataset
            try:
                import yaml
                with open(yaml_path, "r") as f:
                    data_config = yaml.safe_load(f)
                classes = data_config.get("names", [])
                print(f"Number of classes: {len(classes)}")
                print(f"Class Names: {classes}")
            except Exception as yaml_err:
                print(f"Could not read data.yaml class names: {yaml_err}")
        else:
            print("WARNING: data.yaml was not found in the downloaded dataset folder.")
        print("=" * 60)
        
    except Exception as e:
        print(f"[Dataset Downloader] ERROR: Roboflow download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
