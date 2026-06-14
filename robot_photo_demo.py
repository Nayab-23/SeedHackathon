#!/usr/bin/env python3
"""Capture a photo from a Reachy Mini robot camera."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from reachy_mini import ReachyMini


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a single photo from a Reachy Mini robot."
    )
    parser.add_argument(
        "--host",
        default="reachy-mini.local",
        help="Reachy Mini host or IP address.",
    )
    parser.add_argument(
        "--port",
        default=8000,
        type=int,
        help="Reachy Mini daemon port.",
    )
    parser.add_argument(
        "--connection-mode",
        default="auto",
        choices=["auto", "localhost_only", "network"],
        help="How to connect to the Reachy Mini daemon.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to save the captured PNG. Defaults to ./captures/reachy-photo-<timestamp>.png",
    )
    parser.add_argument(
        "--retries",
        default=10,
        type=int,
        help="How many frame capture attempts to make before failing.",
    )
    parser.add_argument(
        "--retry-delay",
        default=0.2,
        type=float,
        help="Seconds to wait between frame capture attempts.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Reachy SDK log level.",
    )
    return parser


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("captures") / f"reachy-photo-{timestamp}.png"


def capture_frame(robot: ReachyMini, retries: int, retry_delay: float):
    for attempt in range(1, retries + 1):
        frame = robot.media.get_frame()
        if frame is not None:
            return frame
        time.sleep(retry_delay)
    return None


def main() -> int:
    args = build_parser().parse_args()
    output_path = (args.output or default_output_path()).expanduser()

    try:
        robot = ReachyMini(
            host=args.host,
            port=args.port,
            connection_mode=args.connection_mode,
            timeout=5.0,
            log_level=args.log_level,
        )
    except Exception as exc:
        print(
            f"Failed to connect to Reachy Mini at {args.host}:{args.port}: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        frame = capture_frame(robot, retries=args.retries, retry_delay=args.retry_delay)
        if frame is None:
            print(
                "Connected to Reachy Mini, but no camera frame was received.",
                file=sys.stderr,
            )
            return 2

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(output_path), frame):
            print(f"Failed to write photo to {output_path}", file=sys.stderr)
            return 3

        print(f"Saved Reachy Mini photo to {output_path.resolve()}")
        return 0
    finally:
        robot.media.close()


if __name__ == "__main__":
    raise SystemExit(main())
