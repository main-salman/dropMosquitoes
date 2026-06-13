#!/usr/bin/env python3
# Implements: HW-001 §8, SW-001 §2.4
"""
test_pressure_drawdown.py — Accumulator Pressure Drawdown Calibration

Interactive calibration script for the ECO-2026-004 accumulator system.
Determines:
  - How many consistent shots per charge at different charge durations
  - Optimal INITIAL_CHARGE_SEC, TOPUP_CHARGE_SEC, TOPUP_INTERVAL_SHOTS
  - Pressure decay curve (shots vs consistency)

Usage:
    python tests/test_pressure_drawdown.py --charge-time 3.0 --shots 25 --pulse-ms 10
    python tests/test_pressure_drawdown.py --sweep  # Test multiple charge durations

IMPORTANT: Run on Jetson with real hardware connected.
           This script fires real water pulses.
"""

import argparse
import json
import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware import RelayController, AccumulatorManager


def run_drawdown_test(relay, accum, charge_sec, num_shots, pulse_ms, delay_between_ms=500):
    """
    Run a single drawdown test:
    1. Charge accumulator for charge_sec
    2. Fire num_shots solenoid pulses
    3. Record timing for each shot
    4. User marks first weak shot visually

    Returns:
        dict with test results
    """
    print(f"\n{'='*60}")
    print(f"  DRAWDOWN TEST: charge={charge_sec}s, shots={num_shots}, pulse={pulse_ms}ms")
    print(f"{'='*60}")

    # Step 1: Charge
    print(f"\n[1/3] Charging accumulator for {charge_sec}s...")
    accum.INITIAL_CHARGE_SEC = charge_sec
    result = accum.arm()
    if result["status"] != "armed":
        print(f"  ❌ ARM FAILED: {result}")
        return {"error": "arm_failed", "detail": result}

    print(f"  ✅ Armed — accumulator at ~30 PSI")
    time.sleep(0.5)  # Brief settle

    # Step 2: Fire shots
    print(f"\n[2/3] Firing {num_shots} shots at {pulse_ms}ms pulse, {delay_between_ms}ms between...")
    print(f"  ⚠ WATCH THE NOZZLE — note which shot first looks weak\n")

    shots = []
    for i in range(num_shots):
        t_start = time.time()

        fire_result = accum.fire(pulse_ms / 1000.0)

        t_end = time.time()
        shot_data = {
            "shot_num": i + 1,
            "timestamp": time.strftime("%H:%M:%S"),
            "fire_time_ms": round((t_end - t_start) * 1000, 2),
            "status": fire_result.get("status", "unknown"),
        }
        shots.append(shot_data)

        # Visual indicator
        bar = "█" * min(i + 1, 50)
        print(f"  Shot {i+1:3d}/{num_shots} {bar} [{fire_result.get('status', '?')}]")

        if i < num_shots - 1:
            time.sleep(delay_between_ms / 1000.0)

    # Step 3: Disarm
    accum.disarm()
    print(f"\n[3/3] Disarmed after {num_shots} shots")

    # Step 4: Get user input
    print(f"\n{'─'*60}")
    print(f"  RESULTS: Fired {num_shots} shots with {charge_sec}s charge")
    print(f"{'─'*60}")

    try:
        weak_shot = input(f"\n  Which shot was the FIRST weak one? (1-{num_shots}, or 'none'): ").strip()
        if weak_shot.lower() == 'none' or weak_shot == '':
            weak_shot_num = None
            consistent_shots = num_shots
            print(f"  → All {num_shots} shots were consistent! ✅")
        else:
            weak_shot_num = int(weak_shot)
            consistent_shots = weak_shot_num - 1
            print(f"  → {consistent_shots} consistent shots before pressure drop")
    except (ValueError, EOFError):
        weak_shot_num = None
        consistent_shots = num_shots
        print(f"  → Assuming all shots consistent (no input)")

    test_result = {
        "charge_sec": charge_sec,
        "pulse_ms": pulse_ms,
        "num_shots": num_shots,
        "delay_between_ms": delay_between_ms,
        "consistent_shots": consistent_shots,
        "first_weak_shot": weak_shot_num,
        "shots": shots,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    return test_result


def run_sweep(relay, accum, pulse_ms, num_shots, delay_between_ms):
    """
    Run drawdown tests at multiple charge durations to find the sweet spot.
    Tests: 1.0s, 1.5s, 2.0s, 2.5s, 3.0s, 4.0s, 5.0s
    """
    charge_durations = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    all_results = []

    print(f"\n{'#'*60}")
    print(f"  SWEEP MODE: Testing {len(charge_durations)} charge durations")
    print(f"  Pulse: {pulse_ms}ms, Max shots per test: {num_shots}")
    print(f"{'#'*60}")

    for i, charge_sec in enumerate(charge_durations):
        print(f"\n{'─'*60}")
        print(f"  TEST {i+1}/{len(charge_durations)}: {charge_sec}s charge")
        print(f"{'─'*60}")

        # Wait between tests for pump to cool
        if i > 0:
            cooldown = 10
            print(f"\n  ⏳ Cooling pump for {cooldown}s before next test...")
            time.sleep(cooldown)

        result = run_drawdown_test(relay, accum, charge_sec, num_shots, pulse_ms, delay_between_ms)
        all_results.append(result)

    # Summary
    print(f"\n\n{'='*60}")
    print(f"  SWEEP RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Charge (s)':>12} │ {'Consistent Shots':>18} │ {'First Weak':>12}")
    print(f"  {'─'*12}─┼─{'─'*18}─┼─{'─'*12}")
    for r in all_results:
        if "error" in r:
            print(f"  {r.get('charge_sec', '?'):>12} │ {'ERROR':>18} │ {'─':>12}")
        else:
            weak = str(r["first_weak_shot"]) if r["first_weak_shot"] else "none"
            print(f"  {r['charge_sec']:>12.1f} │ {r['consistent_shots']:>18} │ {weak:>12}")

    # Recommend optimal settings
    best = max([r for r in all_results if "error" not in r],
               key=lambda r: r["consistent_shots"], default=None)

    if best:
        print(f"\n  ✅ RECOMMENDED SETTINGS:")
        # Use 80% of consistent shots as the top-up interval (safety margin)
        recommended_topup = max(1, int(best["consistent_shots"] * 0.8))
        print(f"     INITIAL_CHARGE_SEC = {best['charge_sec']}")
        print(f"     TOPUP_CHARGE_SEC = {min(best['charge_sec'], 2.0)}")
        print(f"     TOPUP_INTERVAL_SHOTS = {recommended_topup}")
        print(f"     DEFAULT_PULSE_SEC = {pulse_ms / 1000.0}")

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Accumulator Pressure Drawdown Calibration (ECO-2026-004)")
    parser.add_argument("--charge-time", type=float, default=3.0,
                        help="Pump charge duration in seconds (default: 3.0)")
    parser.add_argument("--shots", type=int, default=25,
                        help="Number of shots to fire per test (default: 25)")
    parser.add_argument("--pulse-ms", type=float, default=10.0,
                        help="Solenoid pulse duration in ms (default: 10)")
    parser.add_argument("--delay-ms", type=float, default=500.0,
                        help="Delay between shots in ms (default: 500)")
    parser.add_argument("--sweep", action="store_true",
                        help="Run sweep mode: test multiple charge durations")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    args = parser.parse_args()

    print(f"\n  ╔══════════════════════════════════════════════════╗")
    print(f"  ║  ACCUMULATOR PRESSURE DRAWDOWN CALIBRATION      ║")
    print(f"  ║  ECO-2026-004                                   ║")
    print(f"  ╚══════════════════════════════════════════════════╝\n")

    # Initialize hardware
    print("[Init] Creating RelayController...")
    relay = RelayController()
    print("[Init] Creating AccumulatorManager...")
    accum = AccumulatorManager(relay)

    try:
        if args.sweep:
            results = run_sweep(relay, accum, args.pulse_ms, args.shots, args.delay_ms)
        else:
            results = run_drawdown_test(
                relay, accum, args.charge_time, args.shots, args.pulse_ms, args.delay_ms)

        # Save results
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", f"calibration_drawdown_{time.strftime('%Y%m%d_%H%M%S')}.json")

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n  📄 Results saved to: {output_path}")

    except KeyboardInterrupt:
        print("\n\n  ⚠ Interrupted — disarming...")
        accum.disarm()
    finally:
        accum.cleanup()
        relay.cleanup()
        print("\n  ✅ Hardware cleaned up. Done.")


if __name__ == "__main__":
    main()
