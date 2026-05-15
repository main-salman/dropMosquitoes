import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import subprocess
import threading
from queue import Queue, Empty

# ==============================================================================
# Sentry Control Center
# A Streamlit UI for tuning Scout OpenCV parameters and training Sniper YOLO models
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
        
    with col2:
        if uploaded_file is not None:
            # Save uploaded video to a temp file
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded_file.read())
            
            st.markdown("### Live Preview")
            frame_placeholder = st.empty()
            
            # Init video capture
            cap = cv2.VideoCapture(tfile.name)
            
            # Create subtractor
            backSub = cv2.createBackgroundSubtractorMOG2(history=history, varThreshold=threshold, detectShadows=detect_shadows)
            
            # Read and process frames
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    # Loop the video
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Apply background subtraction
                fgMask = backSub.apply(frame)
                
                # Clean up mask
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                fgMask = cv2.morphologyEx(fgMask, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(fgMask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Draw bounding boxes
                for contour in contours:
                    if cv2.contourArea(contour) >= min_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(frame, "Motion", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Convert BGR to RGB for Streamlit
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Display in Streamlit
                frame_placeholder.image(frame_rgb, channels="RGB", use_column_width=True)
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
            
        log_placeholder = st.empty()
        log_placeholder.code(st.session_state.training_logs, language="bash")
        
        if start_button:
            if not dataset_yaml or not os.path.exists(dataset_yaml):
                st.error("Please provide a valid path to data.yaml.")
            else:
                st.session_state.training_logs = "Starting YOLO training subprocess...\n"
                log_placeholder.code(st.session_state.training_logs, language="bash")
                
                # Build YOLO command
                cmd = [
                    "yolo", "detect", "train",
                    f"data={dataset_yaml}",
                    f"model={base_model}",
                    f"epochs={epochs}",
                    f"batch={batch_size}",
                    f"imgsz={img_size}",
                    "device=0" # Force GPU 0
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
                    
                    st.info("Training started! Polling logs...")
                    
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
                                
                                # Keep logs manageable length (e.g. last 10000 chars)
                                if len(st.session_state.training_logs) > 20000:
                                    st.session_state.training_logs = "... [truncated] ...\n" + st.session_state.training_logs[-15000:]
                                    
                                log_placeholder.code(st.session_state.training_logs, language="bash")
                                
                        except Empty:
                            pass
                            
                    # Final update
                    st.success("Training process completed!")
                    
                except Exception as e:
                    st.error(f"Error starting training: {e}")
