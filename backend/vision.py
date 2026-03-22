import asyncio
import base64
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from io import BytesIO
from threading import Lock

import cv2
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

from backend.database import Event, Session, SessionLocal

load_dotenv()

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CAMERA_SOURCE = os.getenv(
    "CAMERA_SOURCE",
    "/dev/video1",
)
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "1"))
CAPTURE_INTERVAL = float(os.getenv("VISION_INTERVAL_SECONDS", "10"))
DASHBOARD_FPS = float(os.getenv("DASHBOARD_FPS", "30"))
CAMERA_RETRY_DELAY = float(os.getenv("CAMERA_RETRY_DELAY_SECONDS", "2"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "424"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "240"))
DASHBOARD_STREAM_WIDTH = int(os.getenv("DASHBOARD_STREAM_WIDTH", "640"))
DASHBOARD_STREAM_HEIGHT = int(os.getenv("DASHBOARD_STREAM_HEIGHT", "360"))
DASHBOARD_JPEG_QUALITY = int(os.getenv("DASHBOARD_JPEG_QUALITY", "50"))
CAMERA_FOURCC = (os.getenv("CAMERA_FOURCC", "MJPG") or "").strip().upper()[:4]
CAMERA_FLUSH_GRABS = max(0, int(os.getenv("CAMERA_FLUSH_GRABS", "2")))
CAMERA_WARMUP_FRAMES = max(0, int(os.getenv("CAMERA_WARMUP_FRAMES", "6")))
CAMERA_CAPTURE_BACKEND = (os.getenv("CAMERA_CAPTURE_BACKEND", "ffmpeg") or "ffmpeg").strip().lower()
CAMERA_INPUT_FORMAT = (os.getenv("CAMERA_INPUT_FORMAT", "mjpeg") or "mjpeg").strip().lower()
CAMERA_READ_TIMEOUT = float(os.getenv("CAMERA_READ_TIMEOUT_SECONDS", "0.75"))

VISION_SYSTEM_PROMPT = (
    "You are monitoring a child at a desk to see if they are studying. "
    "Look at the image and classify what the child is doing. "
    "Respond with ONLY one of these exact lowercase words and nothing else: studying, distracted, phone.\n"
    "- studying: child is looking at books, writing, or looking at a computer "
    "screen with educational content\n"
    "- phone: child is visibly holding or looking at a phone\n"
    "- distracted: child is looking away, sleeping, eating, talking, or "
    "otherwise not studying"
)

VALID_STATES = {"studying", "distracted", "phone"}

client = OpenAI(api_key=OPENAI_API_KEY)

_vision_failures = 0
MAX_VISION_FAILURES_LOG = 3


class FrameBuffer:
    def __init__(self):
        self._lock = Lock()
        self._jpeg: bytes | None = None
        self._frame = None
        self._timestamp: float = 0.0

    def update(self, frame) -> None:
        display_frame = frame
        if frame is not None and (
            frame.shape[1] != DASHBOARD_STREAM_WIDTH
            or frame.shape[0] != DASHBOARD_STREAM_HEIGHT
        ):
            display_frame = cv2.resize(
                frame,
                (DASHBOARD_STREAM_WIDTH, DASHBOARD_STREAM_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )

        ok, buf = cv2.imencode(
            ".jpg",
            display_frame,
            [cv2.IMWRITE_JPEG_QUALITY, DASHBOARD_JPEG_QUALITY],
        )
        if not ok:
            return

        with self._lock:
            self._frame = display_frame.copy()
            self._jpeg = buf.tobytes()
            self._timestamp = time.time()

    def get_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def get_frame(self):
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_timestamp(self) -> float:
        with self._lock:
            return self._timestamp


frame_buffer = FrameBuffer()


class StateManager:
    def __init__(self):
        self._lock = Lock()
        self._state: str = "studying"
        self._state_since: float = time.time()
        self._study_seconds_today: float = 0
        self._distracted_seconds_today: float = 0
        self._day_anchor: str = self._today_str()
        self._session_id: int | None = None
        self._callbacks: list = []

    @staticmethod
    def _today_str() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_roll_day(self):
        today = self._today_str()
        if today != self._day_anchor:
            self._study_seconds_today = 0
            self._distracted_seconds_today = 0
            self._day_anchor = today

    def _flush_elapsed(self):
        now = time.time()
        elapsed = now - self._state_since
        if self._state == "studying":
            self._study_seconds_today += elapsed
        else:
            self._distracted_seconds_today += elapsed
        self._state_since = now
        return elapsed

    def start_session(self):
        db = SessionLocal()
        try:
            sess = Session()
            db.add(sess)
            db.commit()
            db.refresh(sess)
            self._session_id = sess.id
            log.info("Started study session %d", sess.id)
        finally:
            db.close()

    def end_session(self):
        if self._session_id is None:
            return
        self._flush_elapsed()
        db = SessionLocal()
        try:
            sess = db.query(Session).get(self._session_id)
            if sess:
                sess.end_time = datetime.now(timezone.utc)
                sess.total_study_seconds = int(self._study_seconds_today)
                sess.total_distracted_seconds = int(self._distracted_seconds_today)
                db.commit()
            log.info("Ended study session %d", self._session_id)
        finally:
            db.close()
        self._session_id = None

    def update(self, new_state: str):
        if new_state not in VALID_STATES:
            return

        with self._lock:
            self._maybe_roll_day()
            prev = self._state
            self._flush_elapsed()

            if new_state != prev:
                self._state = new_state
                self._state_since = time.time()
                self._record_event(new_state)
                log.info("State changed: %s -> %s", prev, new_state)
                for cb in self._callbacks:
                    try:
                        cb(new_state, prev)
                    except Exception:
                        log.exception("State-change callback error")

    def _record_event(self, new_state: str):
        db = SessionLocal()
        try:
            evt = Event(
                session_id=self._session_id,
                event_type=new_state,
            )
            db.add(evt)
            db.commit()
        except Exception:
            log.exception("Failed to record event")
        finally:
            db.close()

    def on_state_change(self, callback):
        self._callbacks.append(callback)

    def get_current_state(self) -> str:
        with self._lock:
            return self._state

    def get_state_duration_seconds(self) -> float:
        with self._lock:
            return max(0.0, time.time() - self._state_since)

    def get_study_seconds_today(self) -> float:
        with self._lock:
            self._maybe_roll_day()
            extra = 0.0
            if self._state == "studying":
                extra = time.time() - self._state_since
            return self._study_seconds_today + extra

    def get_distracted_seconds_today(self) -> float:
        with self._lock:
            self._maybe_roll_day()
            extra = 0.0
            if self._state != "studying":
                extra = time.time() - self._state_since
            return self._distracted_seconds_today + extra


state_manager = StateManager()


class FFmpegSnapshotCamera:
    def __init__(self, device_path: str):
        self.device_path = device_path
        self._ffmpeg_exe = "/usr/bin/ffmpeg" if os.path.exists("/usr/bin/ffmpeg") else shutil.which("ffmpeg")

    def open(self) -> bool:
        if self._ffmpeg_exe is None and imageio_ffmpeg is not None:
            self._ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        return self._ffmpeg_exe is not None and os.path.exists(self.device_path)

    def isOpened(self) -> bool:
        return self._ffmpeg_exe is not None and os.path.exists(self.device_path)

    def read(self):
        if not self.isOpened():
            return False, None

        cmd = [
            self._ffmpeg_exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "video4linux2",
            "-input_format",
            CAMERA_INPUT_FORMAT,
            "-framerate",
            str(max(1, int(round(DASHBOARD_FPS)))),
            "-video_size",
            f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}",
            "-i",
            self.device_path,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=max(1.0, CAMERA_READ_TIMEOUT + 0.5),
        )
        if proc.returncode != 0 or not proc.stdout:
            return False, None
        arr = np.frombuffer(proc.stdout, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        return


def _frame_to_base64(frame) -> str:
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    img.thumbnail((512, 512))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return base64.b64encode(buf.getvalue()).decode()


def classify_frame(frame) -> str:
    global _vision_failures
    b64 = _frame_to_base64(frame)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=10,
            temperature=0,
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Classify this frame. Reply with exactly one word: studying, distracted, or phone.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",
                            },
                        }
                    ],
                },
            ],
        )
        raw = resp.choices[0].message.content.strip().lower()

        if _vision_failures > 0:
            log.info("Vision API recovered after %d failures", _vision_failures)
        _vision_failures = 0

        if raw in VALID_STATES:
            return raw
        for token in VALID_STATES:
            if token in raw:
                return token
        log.warning("Unexpected vision response: %s — keeping current state", raw)
        return state_manager.get_current_state()

    except Exception as exc:
        _vision_failures += 1
        if _vision_failures <= MAX_VISION_FAILURES_LOG:
            log.error("Vision API call failed (#%d): %s", _vision_failures, exc)
        elif _vision_failures == MAX_VISION_FAILURES_LOG + 1:
            log.error("Vision API still failing — suppressing repeated logs")
        current = state_manager.get_current_state()
        log.debug("Keeping last known state: %s", current)
        return current


def _camera_device_paths() -> list[str]:
    paths: list[str] = []
    seen = set()

    def add_path(path: str):
        if not path or path in seen:
            return
        seen.add(path)
        paths.append(path)

    source_text = str(CAMERA_SOURCE or "").strip()
    if source_text:
        match = re.search(r"/dev/video(\d+)$", source_text)
        if match:
            add_path(f"/dev/video{match.group(1)}")
        elif source_text.startswith("/dev/video"):
            add_path(source_text)

    add_path(f"/dev/video{CAMERA_INDEX}")
    return paths


def _open_camera():
    if CAMERA_CAPTURE_BACKEND in {"auto", "ffmpeg"}:
        for device_path in _camera_device_paths():
            cap = FFmpegSnapshotCamera(device_path)
            if cap.open():
                ok, frame = cap.read()
                if not ok or frame is None:
                    cap.release()
                    continue
                frame_buffer.update(frame)
                log.info(
                    "Camera source %s opened successfully via ffmpeg at target %.1f fps (%dx%d, input=%s)",
                    device_path,
                    DASHBOARD_FPS,
                    CAMERA_WIDTH,
                    CAMERA_HEIGHT,
                    CAMERA_INPUT_FORMAT,
                )
                return cap

    candidates = []
    seen = set()

    def add_candidate(source):
        key = repr(source)
        if key in seen:
            return
        seen.add(key)
        candidates.append(source)

    source_text = str(CAMERA_SOURCE or "").strip()
    if source_text:
        match = re.search(r"/dev/video(\d+)$", source_text)
        if match:
            add_candidate(int(match.group(1)))
        add_candidate(source_text)

    add_candidate(CAMERA_INDEX)

    for source in candidates:
        try:
            cap = cv2.VideoCapture(source)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if CAMERA_FOURCC:
                    cap.set(
                        cv2.CAP_PROP_FOURCC,
                        cv2.VideoWriter_fourcc(*CAMERA_FOURCC),
                    )
                cap.set(cv2.CAP_PROP_FPS, DASHBOARD_FPS)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                for _ in range(CAMERA_WARMUP_FRAMES):
                    ok, _ = cap.read()
                    if not ok:
                        break
                backend_name = "opencv"
                try:
                    backend_name = cap.getBackendName().lower()
                except Exception:
                    pass
                log.info(
                    "Camera source %s opened successfully via %s at target %.1f fps (%dx%d, fourcc=%s)",
                    source,
                    backend_name,
                    DASHBOARD_FPS,
                    CAMERA_WIDTH,
                    CAMERA_HEIGHT,
                    CAMERA_FOURCC or "default",
                )
                return cap
            cap.release()
        except Exception as exc:
            log.error("Camera open error for %s: %s", source, exc)
    log.warning("Camera sources %s and %s not available", CAMERA_SOURCE, CAMERA_INDEX)
    return None


def _close_camera(cap) -> None:
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass


_running = False


async def _sleep_with_stop(delay: float) -> None:
    end = time.time() + max(delay, 0.0)
    while _running and time.time() < end:
        await asyncio.sleep(min(0.1, end - time.time()))


async def _capture_loop() -> None:
    cap = None

    try:
        while _running:
            if cap is None or not cap.isOpened():
                cap = await asyncio.to_thread(_open_camera)
                if cap is None:
                    log.info("Camera not found — retrying in %.1fs", CAMERA_RETRY_DELAY)
                    await _sleep_with_stop(CAMERA_RETRY_DELAY)
                    continue

            loop_started = time.time()
            try:
                if isinstance(cap, FFmpegSnapshotCamera):
                    ret, frame = await asyncio.wait_for(
                        asyncio.to_thread(cap.read),
                        timeout=CAMERA_READ_TIMEOUT,
                    )
                else:
                    if CAMERA_FLUSH_GRABS:
                        for _ in range(CAMERA_FLUSH_GRABS):
                            grabbed = await asyncio.wait_for(
                                asyncio.to_thread(cap.grab),
                                timeout=CAMERA_READ_TIMEOUT,
                            )
                            if not grabbed:
                                break
                    ret, frame = await asyncio.wait_for(
                        asyncio.to_thread(cap.retrieve),
                        timeout=CAMERA_READ_TIMEOUT,
                    )
                    if not ret:
                        ret, frame = await asyncio.wait_for(
                            asyncio.to_thread(cap.read),
                            timeout=CAMERA_READ_TIMEOUT,
                        )
            except asyncio.TimeoutError:
                log.warning(
                    "Camera read timed out after %.2fs — reopening camera",
                    CAMERA_READ_TIMEOUT,
                )
                _close_camera(cap)
                cap = None
                await _sleep_with_stop(CAMERA_RETRY_DELAY)
                continue
            except Exception as exc:
                log.error("Frame read exception: %s — reopening camera", exc)
                _close_camera(cap)
                cap = None
                await _sleep_with_stop(CAMERA_RETRY_DELAY)
                continue

            if not ret:
                log.warning("Frame grab returned False — reopening camera")
                _close_camera(cap)
                cap = None
                await _sleep_with_stop(CAMERA_RETRY_DELAY)
                continue

            frame_buffer.update(frame)
            await asyncio.sleep(0)
    finally:
        _close_camera(cap)


async def _classification_loop() -> None:
    while _running:
        frame = frame_buffer.get_frame()
        if frame is None:
            await _sleep_with_stop(0.2)
            continue

        started = time.time()
        label = await asyncio.to_thread(classify_frame, frame)
        state_manager.update(label)
        elapsed = time.time() - started
        await _sleep_with_stop(max(0.0, CAPTURE_INTERVAL - elapsed))


async def vision_loop():
    global _running
    _running = True

    state_manager.start_session()
    log.info(
        "Vision loop started (vision_interval=%.1fs, dashboard_fps=%.1f, camera_source=%s, size=%dx%d)",
        CAPTURE_INTERVAL,
        DASHBOARD_FPS,
        CAMERA_SOURCE,
        CAMERA_WIDTH,
        CAMERA_HEIGHT,
    )

    capture_task = asyncio.create_task(_capture_loop())
    classify_task = asyncio.create_task(_classification_loop())

    try:
        await asyncio.gather(capture_task, classify_task)
    except asyncio.CancelledError:
        log.info("Vision loop cancelled")
        raise
    except Exception:
        log.exception("Unexpected error in vision loop")
    finally:
        _running = False
        for task in (capture_task, classify_task):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        state_manager.end_session()
        log.info("Vision loop stopped, session ended")


def stop_vision_loop():
    global _running
    _running = False
