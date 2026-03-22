import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import numpy as np

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reachy")

# Reachy Mini doesn't have arms — it has head (pitch/yaw/roll),
# antennas (two servo ears), and body_yaw (base rotation).
# Gestures are expressed through those actuators.

_NEUTRAL_ANTENNAS = [0.0, 0.0]


class ReachyController:
    def __init__(self):
        self._lock = Lock()
        self._mini = None
        self.connected = False
        self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self):
        try:
            from reachy_mini import ReachyMini
            from reachy_mini.utils import create_head_pose  # noqa: F401

            mini = ReachyMini(
                host=os.getenv("REACHY_HOST", "localhost"),
                port=int(os.getenv("REACHY_PORT", "8001")),
                connection_mode=os.getenv("REACHY_CONNECTION_MODE", "localhost_only"),
                media_backend="no_media",
            )
            mini.__enter__()
            self._mini = mini
            self.connected = True
            log.info("Reachy Mini connected")
            self._goto_rest(duration=1.0)
        except Exception as exc:
            self.connected = False
            self._mini = None
            log.warning("Reachy Mini not available: %s", exc)

    def disconnect(self):
        if self._mini is not None:
            try:
                self._goto_rest(duration=0.8)
                self._mini.__exit__(None, None, None)
            except Exception:
                pass
            self._mini = None
            self.connected = False

    def reconnect(self):
        if self.connected:
            return True
        self.disconnect()
        self._connect()
        return self.connected

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _head_pose(self, pitch=0.0, yaw=0.0, roll=0.0):
        from reachy_mini.utils import create_head_pose
        return create_head_pose(
            pitch=np.deg2rad(pitch),
            yaw=np.deg2rad(yaw),
            roll=np.deg2rad(roll),
            degrees=False,
            mm=False,
        )

    def _goto(self, *, head=None, antennas=None, body_yaw=None,
              duration=0.6, method="minjerk"):
        if not self.connected or self._mini is None:
            return
        kwargs = {"duration": duration, "method": method}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = np.deg2rad(body_yaw)
        self._mini.goto_target(**kwargs)

    def _goto_rest(self, duration=0.6):
        self._goto(
            head=self._head_pose(0, 0, 0),
            antennas=_NEUTRAL_ANTENNAS,
            body_yaw=0,
            duration=duration,
        )

    # ------------------------------------------------------------------
    # Gesture: nod yes
    # ------------------------------------------------------------------

    def nod_yes(self):
        """Nod the head up-down twice to indicate approval."""
        if not self.connected:
            return
        try:
            with self._lock:
                for _ in range(2):
                    self._goto(head=self._head_pose(pitch=-15), duration=0.25)
                    time.sleep(0.3)
                    self._goto(head=self._head_pose(pitch=10), duration=0.25)
                    time.sleep(0.3)
                self._goto(head=self._head_pose(0, 0, 0), duration=0.3)
                time.sleep(0.35)
        except Exception:
            log.exception("nod_yes failed")

    # ------------------------------------------------------------------
    # Gesture: shake no
    # ------------------------------------------------------------------

    def shake_no(self):
        """Shake the head left-right twice to indicate denial."""
        if not self.connected:
            return
        try:
            with self._lock:
                for _ in range(2):
                    self._goto(head=self._head_pose(yaw=-25), duration=0.25)
                    time.sleep(0.3)
                    self._goto(head=self._head_pose(yaw=25), duration=0.25)
                    time.sleep(0.3)
                self._goto(head=self._head_pose(0, 0, 0), duration=0.3)
                time.sleep(0.35)
        except Exception:
            log.exception("shake_no failed")

    # ------------------------------------------------------------------
    # Gesture: alert distracted
    # ------------------------------------------------------------------

    def alert_distracted(self):
        """Attention-getting gesture that stays centered.

        This is used by timed study-monitor alerts, so it must not leave the
        robot looking off to one side.
        """
        if not self.connected:
            return
        try:
            with self._lock:
                antennas_up = [np.deg2rad(35), np.deg2rad(35)]
                antennas_mid = [np.deg2rad(12), np.deg2rad(12)]
                self._goto(
                    head=self._head_pose(pitch=0, yaw=0, roll=0),
                    antennas=antennas_up,
                    body_yaw=0,
                    duration=0.25,
                )
                time.sleep(0.3)
                self._goto(
                    head=self._head_pose(pitch=0, yaw=0, roll=0),
                    antennas=antennas_mid,
                    body_yaw=0,
                    duration=0.2,
                )
                time.sleep(0.25)
                self._goto(
                    head=self._head_pose(pitch=0, yaw=0, roll=0),
                    antennas=antennas_up,
                    body_yaw=0,
                    duration=0.2,
                )
                time.sleep(0.35)
                self._goto_rest(duration=0.6)
                time.sleep(0.65)
        except Exception:
            log.exception("alert_distracted failed")

    # ------------------------------------------------------------------
    # Gesture: return to rest
    # ------------------------------------------------------------------

    def return_to_rest(self):
        """Return head, antennas, and body to neutral position."""
        if not self.connected:
            return
        try:
            with self._lock:
                self._goto_rest(duration=0.8)
                time.sleep(0.85)
        except Exception:
            log.exception("return_to_rest failed")

    # ------------------------------------------------------------------
    # State reactor
    # ------------------------------------------------------------------

    def react_to_state(self, state: str):
        """Trigger a gesture based on the vision state label."""
        if not self.connected:
            return
        if state in ("phone", "distracted"):
            self.alert_distracted()
        elif state == "studying":
            self.return_to_rest()


# ---------------------------------------------------------------------------
# Module-level singleton + async wrappers
# ---------------------------------------------------------------------------

controller = ReachyController()


async def async_nod_yes():
    await asyncio.get_event_loop().run_in_executor(_executor, controller.nod_yes)


async def async_shake_no():
    await asyncio.get_event_loop().run_in_executor(_executor, controller.shake_no)


async def async_alert_distracted():
    await asyncio.get_event_loop().run_in_executor(_executor, controller.alert_distracted)


async def async_return_to_rest():
    await asyncio.get_event_loop().run_in_executor(_executor, controller.return_to_rest)


async def async_react_to_state(state: str):
    await asyncio.get_event_loop().run_in_executor(
        _executor, controller.react_to_state, state
    )
