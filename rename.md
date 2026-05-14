# AI Coding Rules for Jetson Edge Robotics

1. **NO VANILLA PYTORCH:** Do not run inference using `.pt` files. All YOLOv8 models MUST be exported to TensorRT (`.engine`) formats for inference. If writing an inference script, assume the TensorRT engine exists.
2. **GSTREAMER IS MANDATORY:** Do not use `cv2.VideoCapture(0)` for MIPI cameras on Jetson. You MUST write highly optimized GStreamer pipelines inside the `cv2.VideoCapture()` string to utilize the Jetson's hardware ISP (Image Signal Processor).
3. **NON-BLOCKING I/O:** The vision tracking loop cannot be blocked by serial commands. Use `asyncio` or dedicated `threading` for serial communications to the Storm32 gimbal controller.
4. **FAIL-SAFE FIRST:** Every script that touches the GPIO Solenoid pin must have a `try/finally` block that ensures the pin is set to `LOW` if the script crashes. A stuck `HIGH` pin will flood the yard and drain the accumulator.
5. **HUMAN OVERRIDE:** The Human Detection safety loop takes priority over all other logic. If `person_confidence > 0.45` anywhere in the Sniper frame, `is_safe_to_fire` must instantly return `False`.