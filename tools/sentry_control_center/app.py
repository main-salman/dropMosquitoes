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
    st.markdown("Train your custom mosquito detection model without OOM crashing the RTX 3070.")
    
    col_t1, col_t2 = st.columns([1, 2])
    
    with col_t1:
        st.subheader("Training Configuration")
        dataset_yaml = st.text_input("Absolute Path to data.yaml", placeholder="C:/datasets/mosquito_dataset/data.yaml")
        base_model = st.selectbox("Base Model", ["yolov8n.pt", "yolov8s.pt"])
        
        st.subheader("Hyperparameters (RTX 3070 8GB)")
        epochs = st.number_input("Epochs", min_value=1, max_value=1000, value=100)
        
        # Max 32 to prevent OOM on 8GB VRAM
        batch_size = st.number_input("Batch Size", min_value=1, max_value=32, value=16, 
                                     help="Max 32 to prevent CUDA Out Of Memory on 8GB VRAM.")
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
                st.session_state.training_logs += f"  Model:     {base_model}\n"
                st.session_state.training_logs += f"  Dataset:   {dataset_yaml}\n"
                st.session_state.training_logs += f"  Epochs:    {epochs}\n"
                st.session_state.training_logs += f"  Batch:     {batch_size}\n"
                st.session_state.training_logs += f"  ImgSize:   {img_size}\n"
                st.session_state.training_logs += "─" * 60 + "\n"
                log_placeholder.code(st.session_state.training_logs, language="bash")
                
                # Build YOLO command
                cmd = [
                    "yolo", "detect", "train",
                    f"data={dataset_yaml}",
                    f"model={base_model}",
                    f"epochs={epochs}",
                    f"batch={batch_size}",
                    f"imgsz={img_size}",
                    "device=0"  # Force GPU 0
                ]
                
                # Spawn subprocess to prevent Streamlit UI from freezing
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
                            # Read multiple lines at once to avoid updating UI too frequently
                            lines = []
                            while not q.empty():
                                line = q.get_nowait()
                                lines.append(line)
                                
                            if lines:
                                new_logs = "".join(lines)
                                st.session_state.training_logs += new_logs
                                
                                # Keep logs manageable length (last 20000 chars)
                                if len(st.session_state.training_logs) > 20000:
                                    st.session_state.training_logs = "... [truncated] ...\n" + st.session_state.training_logs[-15000:]
                                    
                                log_placeholder.code(st.session_state.training_logs, language="bash")
                                
                        except Empty:
                            pass
                    
                    st.session_state.training_active = False
                    
                    # Check exit code
                    if process.returncode == 0:
                        st.success("✅ Training completed successfully!")
                        # Show where the model was saved
                        best_pt_path = os.path.join(os.getcwd(), "runs", "detect", "train", "weights", "best.pt")
                        result_placeholder.info(
                            f"**Trained model saved to:**\n\n"
                            f"`{best_pt_path}`\n\n"
                            f"**Next steps:**\n"
                            f"1. Copy `best.pt` to your Jetson: `scp {best_pt_path} jetson@<IP>:/home/jetson/dropMosquitoes/`\n"
                            f"2. SSH into Jetson and convert to TensorRT for max FPS:\n"
                            f"   ```python\n"
                            f"   from ultralytics import YOLO\n"
                            f"   model = YOLO('best.pt')\n"
                            f"   model.export(format='engine', half=True, workspace=4)\n"
                            f"   ```\n"
                            f"3. The system auto-detects `best.engine` — no code changes needed."
                        )
                    else:
                        st.error(f"❌ Training process exited with code {process.returncode}. Check logs above.")
                    
                except FileNotFoundError:
                    st.error("❌ `yolo` CLI not found. Make sure `ultralytics` is installed: `pip install ultralytics`")
                except Exception as e:
                    st.error(f"❌ Error starting training: {e}")
