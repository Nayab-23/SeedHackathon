#!/usr/bin/env python3
"""Capture a short video while commanding Reachy Mini through a full turn."""

from __future__ import annotations

import argparse
import math
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
from reachy_mini import ReachyMini


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record a video while commanding Reachy Mini to rotate 360 degrees."
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Reachy Mini daemon host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Reachy Mini daemon port.",
    )
    parser.add_argument(
        "--connection-mode",
        default="localhost_only",
        choices=["auto", "localhost_only", "network"],
        help="How to connect to the Reachy Mini daemon.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Video duration in seconds.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=20.0,
        help="Target video FPS.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output video path. Defaults to ./captures/reachy-360-<timestamp>.mp4",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="Seconds to let the robot move to neutral yaw before recording.",
    )
    parser.add_argument(
        "--return-home",
        action="store_true",
        help="Return the robot body yaw to zero after recording.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Reachy SDK log level.",
    )
    return parser


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("captures") / f"reachy-360-{timestamp}.mp4"


def move_robot(robot: ReachyMini, duration: float, errors: list[str]) -> None:
    checkpoints = [math.pi / 2, math.pi, 3 * math.pi / 2, 2 * math.pi]
    step_duration = duration / len(checkpoints)

    try:
        for target in checkpoints:
            robot.goto_target(body_yaw=target, duration=step_duration)
    except Exception as exc:
        errors.append(str(exc))


def capture_video(
    robot: ReachyMini,
    output_path: Path,
    duration: float,
    fps: float,
) -> tuple[int, float, float, float]:
    frame = robot.media.get_frame()
    if frame is None:
        raise RuntimeError("No camera frame available from Reachy Mini.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    height, width = frame.shape[:2]
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open video writer for {output_path}")

    frame_count = 0
    start_time = time.time()
    next_frame_at = start_time
    yaw_samples: list[float] = []

    try:
        while True:
            now = time.time()
            elapsed = now - start_time
            if elapsed >= duration:
                break

            frame = robot.media.get_frame()
            if frame is not None:
                writer.write(frame)
                frame_count += 1

            head, _ = robot.get_current_joint_positions()
            yaw_samples.append(head[0])

            next_frame_at += 1.0 / fps
            sleep_for = next_frame_at - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        writer.release()

    if not yaw_samples:
        raise RuntimeError("No body yaw samples were collected during recording.")

    return frame_count, yaw_samples[0], max(yaw_samples), yaw_samples[-1]


def main() -> int:
    args = build_parser().parse_args()
    output_path = (args.output or default_output_path()).expanduser()

    robot = ReachyMini(
        host=args.host,
        port=args.port,
        connection_mode=args.connection_mode,
        automatic_body_yaw=False,
        log_level=args.log_level,
    )
    robot.set_automatic_body_yaw(False)

    movement_errors: list[str] = []

    try:
        robot.goto_target(body_yaw=0.0, duration=max(0.5, args.settle_seconds))

        movement_thread = threading.Thread(
            target=move_robot,
            args=(robot, args.duration, movement_errors),
            daemon=True,
        )
        movement_thread.start()

        frame_count, start_yaw, max_yaw, end_yaw = capture_video(
            robot=robot,
            output_path=output_path,
            duration=args.duration,
            fps=args.fps,
        )

        movement_thread.join(timeout=args.duration + 2.0)

        if args.return_home:
            robot.goto_target(body_yaw=0.0, duration=max(2.0, args.settle_seconds))

        print(f"Saved video to {output_path.resolve()}")
        print(f"Frames written: {frame_count}")
        print(
            "Yaw summary (rad): "
            f"start={start_yaw:.3f}, max={max_yaw:.3f}, end={end_yaw:.3f}"
        )

        if movement_errors:
            print(f"Movement warning: {movement_errors[0]}")

        return 0
    finally:
        robot.media.close()


if __name__ == "__main__":
    raise SystemExit(main())
