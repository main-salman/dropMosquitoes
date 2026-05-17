import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import json
import subprocess
import threading
import time
from queue import Queue, Empty

# ==============================================================================
# Sentry Control Center
# A Streamlit UI for tuning Scout OpenCV parameters and training Sniper YOLO models
#
# Implements: SW-001 — Windows-side tooling for the Sniper Messy Mortar
# ==============================================================================

st.set_page_config(page_title="Sentry Control Center", layout="wide", page_icon="🎯")

st.title("🎯 Sentry Control Center")
st.markdown("Dual-Architecture tuning and training utility for the Sniper Messy Mortar.")

tab1, tab2 = st.tabs(["👁️ Scout Tuner (OpenCV)", "🧠 Sniper Trainer (YOLOv8)"])

# ==============================================================================
# TAB 1: Scout Tuner (OpenCV MOG2)
# ==============================================================================
with tab1:
    st.header("Scout Motion Tuning")
    st.markdown("Upload a sample video to tune the Background Subtractor MOG2 parameters before deploying to the Jetson.")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        uploaded_file = st.file_uploader("Upload Test Video (.mp4)", type=["mp4", "avi", "mov"])
        st.subheader("MOG2 Parameters")
        threshold = st.slider("Threshold", min_value=0, max_value=255, value=16, 
                              help="Variance threshold for the background model. Higher = less noise but misses faint motion.")
        min_area = st.slider("Min Contour Area (pixels)", min_value=10, max_value=5000, value=500, step=10,
                             help="Minimum size of moving object to be considered valid.")
        
        history = st.number_input("History Frames", min_value=10, max_value=1000, value=500)
        detect_shadows = st.checkbox("Detect Shadows", value=False)

        # --- Export scout_config.json ---
        st.divider()
        st.subheader("Export Configuration")
        export_path = st.text_input(
            "Export Path",
            value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "scout_config.json"),
            help="Absolute path where scout_config.json will be saved. Copy this file to the Jetson."
        )
        if st.button("💾 Export scout_config.json", use_container_width=True, type="primary"):
            config_data = {
                "history": int(history),
                "threshold": int(threshold),
                "min_area": int(min_area),
                "detect_shadows": detect_shadows
            }
            try:
                with open(export_path, "w") as f:
                    json.dump(config_data, f, indent=2)
                st.success(f"✅ Saved to `{export_path}`")
                st.code(json.dumps(config_data, indent=2), language="json")
            except Exception as e:
                st.error(f"Failed to save: {e}")
        
    with col2:
        if uploaded_file is not None:
            # Save uploaded video to a temp file
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded_file.read())
            tfile.flush()
            
            st.markdown("### Live Preview")
            frame_placeholder = st.empty()
            status_placeholder = st.empty()
            
            # Init video capture
            cap = cv2.VideoCapture(tfile.name)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Create subtractor
            backSub = cv2.createBackgroundSubtractorMOG2(history=history, varThreshold=threshold, detectShadows=detect_shadows)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            
            frame_num = 0
            detections = 0
            
            # Read and process frames (single pass, no infinite loop)
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_num += 1
                
                # Apply background subtraction
                fgMask = backSub.apply(frame)
                
                # Clean up mask
                fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Draw bounding boxes
                frame_detections = 0
                for contour in contours:
                    if cv2.contourArea(contour) >= min_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(frame, "Motion", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        frame_detections += 1
                
                detections += frame_detections
                
                # Convert BGR to RGB for Streamlit
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Display in Streamlit
                frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
                status_placeholder.caption(f"Frame {frame_num}/{total_frames} · {frame_detections} detections this frame · {detections} total")
            
            cap.release()
            os.unlink(tfile.name)
            st.info(f"Video processing complete. {detections} total detections across {frame_num} frames.")
        else:
            st.info("Please upload a video to start tuning.")

# ==============================================================================
# TAB 2: Sniper Trainer (YOLOv8)
# ==============================================================================

# Helper function to read subprocess output asynchronously
def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()

with tab2:
    st.header("Sniper Model Training")
    st.markdown("Train your custom mosquito detection model across Windows RTX and MacBook M4 Pro.")
    
    # Dynamic Hardware Auto-Detection
    try:
        import torch
        has_cuda = torch.cuda.is_available()
        has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except ImportError:
        has_cuda = False
        has_mps = False

    if has_cuda:
        detected_engine = "cuda"
        engine_label = "NVIDIA CUDA (RTX 3070)"
        default_batch = 16
        max_batch = 32
    elif has_mps:
        detected_engine = "mps"
        engine_label = "Apple Silicon MPS (M4 Pro)"
        default_batch = 32
        max_batch = 64
    else:
        detected_engine = "cpu"
        engine_label = "Standard CPU (Fallback)"
        default_batch = 8
        max_batch = 16

    col_t1, col_t2 = st.columns([1, 2])
    
    with col_t1:
        st.subheader("Training Configuration")
        dataset_yaml = st.text_input("Absolute Path to data.yaml", placeholder="C:/datasets/mosquito_dataset/data.yaml")
        base_model = st.selectbox("Base Model", ["yolov8n.pt", "yolov8s.pt"])
        
        st.subheader("Platform Configuration")
        st.info(f"Auto-Detected Engine: **{engine_label}**")
        
        engine_options = {
            "Auto-Detect": detected_engine,
            "CUDA (NVIDIA)": "cuda",
            "MPS (Apple Silicon)": "mps",
            "CPU": "cpu"
        }
        selected_mode = st.selectbox("Hardware Acceleration Engine Override", list(engine_options.keys()))
        active_engine = engine_options[selected_mode]
        
        # Adjust limits based on override
        if active_engine == "cuda":
            current_max_batch = 32
            current_default_batch = 16
        elif active_engine == "mps":
            current_max_batch = 64
            current_default_batch = 32
        else:
            current_max_batch = 16
            current_default_batch = 8
            
        st.subheader("Hyperparameters")
        epochs = st.number_input("Epochs", min_value=1, max_value=1000, value=100)
        
        batch_size = st.number_input(
            "Batch Size", 
            min_value=1, 
            max_value=current_max_batch, 
            value=min(current_default_batch, current_max_batch),
            help=f"Max {current_max_batch} for {active_engine} architecture."
        )
        img_size = st.number_input("Image Size", min_value=320, max_value=1280, value=640, step=32)
        
        start_button = st.button("🚀 Start Training", use_container_width=True, type="primary")

    with col_t2:
        st.subheader("Live Training Logs")
        
        # Initialize session state for logs if not exists
        if "training_logs" not in st.session_state:
            st.session_state.training_logs = ""
        if "training_active" not in st.session_state:
            st.session_state.training_active = False
            
        log_placeholder = st.empty()
        log_placeholder.code(st.session_state.training_logs or "Waiting for training to start...", language="bash")
        
        result_placeholder = st.empty()
        
        if start_button:
            if not dataset_yaml or not os.path.exists(dataset_yaml):
                st.error("❌ Please provide a valid path to data.yaml.")
            else:
                st.session_state.training_logs = f"[{time.strftime('%H:%M:%S')}] Starting YOLO training subprocess...\n"
                st.session_state.training_logs += f"  Engine:    {active_engine}\n"
                st.session_state.training_logs += f"  Model:     {base_model}\n"
                st.session_state.training_logs += f"  Dataset:   {dataset_yaml}\n"
                st.session_state.training_logs += f"  Epochs:    {epochs}\n"
                st.session_state.training_logs += f"  Batch:     {batch_size}\n"
                st.session_state.training_logs += f"  ImgSize:   {img_size}\n"
                st.session_state.training_logs += "─" * 60 + "\n"
                log_placeholder.code(st.session_state.training_logs, language="bash")
                
                # We will save to a specific project directory to control output
                project_dir = os.path.join(os.getcwd(), "runs", "detect")
                name_dir = "train"
                
                # Build YOLO command
                cmd = [
                    "yolo", "detect", "train",
                    f"data={dataset_yaml}",
                    f"model={base_model}",
                    f"epochs={epochs}",
                    f"batch={batch_size}",
                    f"imgsz={img_size}",
                    f"device={active_engine}",
                    f"project={project_dir}",
                    f"name={name_dir}",
                    "exist_ok=True"
                ]
                
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    q = Queue()
                    t = threading.Thread(target=enqueue_output, args=(process.stdout, q))
                    t.daemon = True
                    t.start()
                    
                    st.info("⏳ Training started! Live logs will stream below.")
                    st.session_state.training_active = True
                    
                    # Loop to read from queue and update UI
                    while process.poll() is None or not q.empty():
                        try:
                            lines = []
                            while not q.empty():
                                line = q.get_nowait()
                                lines.append(line)
                                
                            if lines:
                                new_logs = "".join(lines)
                                st.session_state.training_logs += new_logs
                                
                                if len(st.session_state.training_logs) > 20000:
                                    st.session_state.training_logs = "... [truncated] ...\n" + st.session_state.training_logs[-15000:]
                                    
                                log_placeholder.code(st.session_state.training_logs, language="bash")
                                
                        except Empty:
                            pass
                    
                    st.session_state.training_active = False
                    
                    if process.returncode == 0:
                        st.success("✅ Training completed successfully!")
                        
                        # Copy best.pt to models/trained/best.pt to preserve deploy.sh pipeline
                        import shutil
                        yolo_best_pt = os.path.join(project_dir, name_dir, "weights", "best.pt")
                        deploy_model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "trained")
                        
                        # Note: If running sentry_control_center from its own directory, os.getcwd() could be tools/sentry_control_center
                        # Let's ensure we find the project root properly:
                        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                        deploy_model_dir = os.path.join(project_root, "models", "trained")
                        final_model_path = os.path.join(deploy_model_dir, "best.pt")
                        
                        if os.path.exists(yolo_best_pt):
                            os.makedirs(deploy_model_dir, exist_ok=True)
                            shutil.copy2(yolo_best_pt, final_model_path)
                            
                            result_placeholder.info(
                                f"**Trained model saved cleanly for deployment to:**\n\n"
                                f"`{final_model_path}`\n\n"
                                f"**Deployment is ready!**\n"
                                f"Your `deploy.sh` script will automatically pick up this model."
                            )
                        else:
                            st.warning(f"Training finished, but could not find weights at `{yolo_best_pt}` to copy over.")
                            
                    else:
                        st.error(f"❌ Training process exited with code {process.returncode}. Check logs above.")
                    
                except FileNotFoundError:
                    st.error("❌ `yolo` CLI not found. Make sure `ultralytics` is installed: `pip install ultralytics`")
                except Exception as e:
                    st.error(f"❌ Error starting training: {e}")
