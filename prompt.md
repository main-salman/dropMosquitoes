# Project: Mosquito Sentry (Edge AI Ballistic Turret)
Act as a Senior Autonomous Robotics Engineer. We are building an edge-AI powered, 2-axis mosquito tracking and extermination turret using an NVIDIA Jetson Orin Nano Super.

## Core Architecture
1. **The Vision Array:** - Scout Camera (MIPI CSI Port 0): Arducam NoIR IMX219 (8MP, no IR-cut filter). Runs at 60FPS doing simple contour/motion tracking to find fast-moving targets. 24/7 day+night via 850nm IR illuminator.
   - Sniper Camera (MIPI CSI Port 1): Arducam IMX477 (12.3MP). Runs at 60FPS using YOLOv8 to verify the target shape and run Human Safety detection.
2. **The Turret:** A custom aluminum gimbal driven by two brushless motors, controlled by a Storm32 32-Bit BGC via Serial UART from the Jetson.
3. **The Weapon:** A 12V 70PSI water line, triggered by a 12V direct-acting solenoid. The solenoid is fired via a MOSFET connected to a Jetson 3.3V GPIO pin.

## The Goal
Create a modular Python architecture that ingests the Scout video feed, identifies a moving target, commands the Storm32 to pan/tilt to the target coordinates, uses the Sniper camera to verify it is an insect, calculates a ballistic lead for a 5-meter water pulse, checks that no humans are in the line of fire, and triggers the GPIO pin for exactly 20 milliseconds.

## Instructions for AI
Read `spec.md`, `agents.md`, and `cursor.md` before generating any code. We will build this one module at a time, starting with the MIPI camera initialization.