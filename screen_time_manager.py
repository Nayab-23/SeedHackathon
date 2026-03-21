from datetime import datetime, time, timedelta
from typing import Dict
from dns_filter import FilterResult, FilterAction

class DeviceScreenTime:
    """Track screen time for a device"""
    def __init__(self, device_id: str, daily_limit_minutes: int):
        self.device_id = device_id
        self.daily_limit_minutes = daily_limit_minutes
        self.usage_today_minutes = 0
        self.last_active = None
        self.session_start = None

    def start_session(self) -> None:
        """Start a new screen time session"""
        self.session_start = datetime.now()

    def end_session(self) -> int:
        """End screen time session and return duration"""
        if self.session_start is None:
            return 0

        duration = (datetime.now() - self.session_start).total_seconds() / 60
        self.usage_today_minutes += duration
        self.session_start = None
        return int(duration)

    def get_remaining_minutes(self) -> int:
        """Get remaining screen time for the day"""
        return max(0, self.daily_limit_minutes - int(self.usage_today_minutes))

    def reset_daily(self) -> None:
        """Reset daily counter (call at midnight)"""
        self.usage_today_minutes = 0

    def is_over_limit(self) -> bool:
        """Check if device has exceeded daily limit"""
        return self.usage_today_minutes >= self.daily_limit_minutes

class ScreenTimeManager:
    """Manages screen time restrictions for devices"""

    def __init__(self):
        self.devices: Dict[str, DeviceScreenTime] = {}
        self.time_based_restrictions: Dict[str, Dict] = {}

    def add_device(self, device_id: str, daily_limit_minutes: int) -> None:
        """Add a device with screen time limit"""
        self.devices[device_id] = DeviceScreenTime(device_id, daily_limit_minutes)

    def set_time_restriction(
        self,
        device_id: str,
        start_time: time,
        end_time: time,
        allowed: bool = False
    ) -> None:
        """
        Set time-based restrictions for a device

        Args:
            device_id: Device identifier
            start_time: Start time of restriction
            end_time: End time of restriction
            allowed: If True, internet is only allowed during this time
        """
        if device_id not in self.time_based_restrictions:
            self.time_based_restrictions[device_id] = []

        self.time_based_restrictions[device_id].append({
            "start": start_time,
            "end": end_time,
            "allowed": allowed
        })

    def _is_within_time_window(self, current_time: time, start: time, end: time) -> bool:
        """Check if current time is within window"""
        if start <= end:
            return start <= current_time <= end
        else:
            # Handles overnight ranges (e.g., 22:00 to 06:00)
            return current_time >= start or current_time <= end

    def check_device(self, device_id: str, domain: str = "") -> FilterResult:
        """
        Check if device can access internet

        Args:
            device_id: Device to check
            domain: Domain being accessed (for logging)

        Returns:
            FilterResult indicating if access is allowed
        """
        if device_id not in self.devices:
            return FilterResult(FilterAction.ALLOW, "Device not registered")

        device = self.devices[device_id]

        # Check if device exceeded daily limit
        if device.is_over_limit():
            return FilterResult(
                FilterAction.BLOCK,
                f"Daily screen time limit exceeded for {device_id}"
            )

        # Check time-based restrictions
        current_time = datetime.now().time()
        if device_id in self.time_based_restrictions:
            for restriction in self.time_based_restrictions[device_id]:
                within_window = self._is_within_time_window(
                    current_time,
                    restriction["start"],
                    restriction["end"]
                )

                if restriction["allowed"] and not within_window:
                    # Internet allowed only during specified time
                    return FilterResult(
                        FilterAction.BLOCK,
                        f"Device {device_id} can only access internet between "
                        f"{restriction['start']} and {restriction['end']}"
                    )

                if not restriction["allowed"] and within_window:
                    # Internet blocked during specified time
                    return FilterResult(
                        FilterAction.BLOCK,
                        f"Device {device_id} is blocked from {restriction['start']} "
                        f"to {restriction['end']}"
                    )

        return FilterResult(FilterAction.ALLOW, "Device within screen time limits")

    def get_device_stats(self, device_id: str) -> Dict | None:
        """Get screen time stats for a device"""
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]
        return {
            "device_id": device_id,
            "usage_today_minutes": int(device.usage_today_minutes),
            "daily_limit_minutes": device.daily_limit_minutes,
            "remaining_minutes": device.get_remaining_minutes(),
            "is_over_limit": device.is_over_limit(),
        }
