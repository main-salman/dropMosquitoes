import cv2
import time
import queue

class ScoutAgent:
    def __init__(self, output_queue, display=False):
        """
        Scout Vision Agent for Mosquito Sentry.
        Runs at 120 FPS using an Arducam OV9281 (MIPI CSI-2 Port 0).
        Uses Background Subtraction (MOG2) to find fast moving targets.
        
        Args:
            output_queue (queue.Queue or multiprocessing.Queue): Thread-safe queue for tracking coordinates.
            display (bool): If True, shows cv2.imshow windows for debugging.
        """
        self.output_queue = output_queue
        self.display = display
        self.running = False
        
        # MOG2 Background Subtractor:
        # history: 500 frames (adapts over time)
        # varThreshold: 16 (lower = more sensitive to movement)
        # detectShadows: False (mosquitoes move too fast to cast useful shadows, saves compute)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        
        self.prev_x = None
        self.prev_y = None
        self.prev_time = None

    def get_gstreamer_pipeline(self):
        """
        Returns a highly optimized GStreamer string for the Jetson ISP.
        Targets /dev/video0 (sensor-id=0) at 1280x800 @ 120 FPS.
        """
        return (
            "nvarguscamerasrc sensor-id=0 ! "
            "video/x-raw(memory:NVMM), width=1280, height=800, format=NV12, framerate=120/1 ! "
            "nvvidconv ! video/x-raw, format=BGRx ! "
            "videoconvert ! video/x-raw, format=BGR ! "
            "appsink drop=1"
        )

    def run(self):
        """
        Main tracking loop. Reads from the GStreamer pipeline, applies background
        subtraction, finds the largest moving contour, and computes velocity.
        """
        pipeline = self.get_gstreamer_pipeline()
        print(f"[ScoutAgent] Initializing GStreamer Pipeline:\n{pipeline}")
        
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
        if not cap.isOpened():
            print("[ScoutAgent] ERROR: Failed to open camera. Check GStreamer pipeline and MIPI connection.")
            return

        self.running = True
        print("[ScoutAgent] Camera initialized. Starting 120FPS tracking loop...")

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("[ScoutAgent] WARNING: Dropped frame.")
                    continue

                current_time = time.time()
                
                # Pre-process: Slight blur to reduce sensor noise
                blurred = cv2.GaussianBlur(frame, (5, 5), 0)
                
                # Apply Background Subtraction
                fg_mask = self.bg_subtractor.apply(blurred)
                
                # Morphological operations to clean up noisy pixels
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
                
                # Find contours
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                best_contour = None
                max_area = 0
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    # Filter out tiny noise (area < 5) and massive changes (area > 5000)
                    if 5 < area < 5000:
                        if area > max_area:
                            max_area = area
                            best_contour = contour
                            
                if best_contour is not None:
                    # Calculate centroid
                    M = cv2.moments(best_contour)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        vx, vy = 0.0, 0.0
                        
                        # Calculate velocity if we have a previous state
                        if self.prev_x is not None and self.prev_time is not None:
                            dt = current_time - self.prev_time
                            if dt > 0:
                                vx = (cx - self.prev_x) / dt
                                vy = (cy - self.prev_y) / dt
                        
                        # Update state
                        self.prev_x = cx
                        self.prev_y = cy
                        self.prev_time = current_time
                        
                        # Push to Turret Queue (Non-blocking)
                        try:
                            # Push format: (x, y, velocity_x, velocity_y)
                            self.output_queue.put_nowait((cx, cy, vx, vy))
                        except queue.Full:
                            pass # If queue is full, drop the coordinate (turret is behind)
                            
                        if self.display:
                            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                            cv2.putText(frame, f"V: ({vx:.1f}, {vy:.1f})", (cx + 10, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                else:
                    # No target found, reset tracking history to prevent erratic velocity on next pickup
                    self.prev_x = None
                    self.prev_y = None
                    self.prev_time = None
                    # Send None so the Turret knows target is lost
                    try:
                        self.output_queue.put_nowait(None)
                    except queue.Full:
                        pass
                
                if self.display:
                    cv2.imshow("Scout Vision - Tracking", frame)
                    cv2.imshow("Scout Vision - Foreground Mask", fg_mask)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self.running = False

        finally:
            print("[ScoutAgent] Shutting down.")
            cap.release()
            if self.display:
                cv2.destroyAllWindows()

if __name__ == "__main__":
    # Standalone Testing Block
    print("Starting ScoutAgent in Standalone Testing Mode...")
    # Using a standard Queue for testing
    test_queue = queue.Queue(maxsize=10)
    scout = ScoutAgent(output_queue=test_queue, display=True)
    
    # We can run the agent directly in the main thread for simple testing
    try:
        scout.run()
    except KeyboardInterrupt:
        scout.running = False
