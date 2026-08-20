"""Read robot state straight from DDS through unitree_sdk2py — no ROS2, no rclpy.

CycloneDDS is the same bus the ROS2 layer used, so the packets on the wire are
identical; only the Python class that decodes them differs. Topic names are
configured in ROS2 form (``/lf/sportmodestate``) and mapped to their DDS form
(``rt/lf/sportmodestate``) here, so ``.env`` stays unchanged.

Compared to the old rclpy implementation this needs no subprocess and no spin
loop: ChannelSubscriber delivers callbacks on its own thread.
"""

import logging
import threading
import time
from typing import Optional

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_

from interfaces.state import StateService
import service_registry
from models.state import RobotState

logger = logging.getLogger("State:SdkSportStateService")

# The sport topic publishes at 10Hz. Treat a longer gap as "link lost" so the
# DeviceWatcher can restart us.
STALE_AFTER_SEC = 5.0


def _as_float_list(xs) -> list[float]:
    return [float(x) for x in xs]


def _as_int_list(xs) -> list[int]:
    return [int(x) for x in xs]


def _to_dds_topic(name: str) -> str:
    """Map a ROS2 topic name to the DDS name ROS2 would use on the wire.

    ROS2 prefixes every topic with ``rt/``; the SDK talks raw DDS so we must
    add it ourselves. ``/lf/sportmodestate`` -> ``rt/lf/sportmodestate``
    """
    if name.startswith("rt/"):
        return name
    return "rt/" + name.lstrip("/")


def _imu_to_dict(imu) -> dict:
    return {
        "quaternion": _as_float_list(imu.quaternion),
        "gyroscope": _as_float_list(imu.gyroscope),
        "accelerometer": _as_float_list(imu.accelerometer),
        "rpy": _as_float_list(imu.rpy),
        "temperature": float(imu.temperature),
    }


def _sport_to_dict(msg: SportModeState_) -> dict:
    return {
        "stamp": {"sec": int(msg.stamp.sec), "nanosec": int(msg.stamp.nanosec)},
        "error_code": int(msg.error_code),
        "imu_state": _imu_to_dict(msg.imu_state),
        "mode": int(msg.mode),
        "progress": float(msg.progress),
        "gait_type": int(msg.gait_type),
        "foot_raise_height": float(msg.foot_raise_height),
        "position": _as_float_list(msg.position),
        "body_height": float(msg.body_height),
        "velocity": _as_float_list(msg.velocity),
        "yaw_speed": float(msg.yaw_speed),
        # Present in the SDK IDL but dropped by the old rclpy implementation.
        "range_obstacle": _as_float_list(msg.range_obstacle),
        "foot_force": _as_float_list(msg.foot_force),
        "foot_position_body": _as_float_list(msg.foot_position_body),
        "foot_speed_body": _as_float_list(msg.foot_speed_body),
    }


def _low_to_dict(msg: LowState_) -> dict:
    motor_state = [
        {
            "mode": int(m.mode),
            "q": float(m.q),
            "dq": float(m.dq),
            "ddq": float(m.ddq),
            "tau_est": float(m.tau_est),
            "q_raw": float(m.q_raw),
            "dq_raw": float(m.dq_raw),
            "ddq_raw": float(m.ddq_raw),
            "temperature": int(m.temperature),
            "lost": int(m.lost),
            "reserve": _as_int_list(m.reserve),
        }
        for m in msg.motor_state
    ]

    bms = msg.bms_state
    bms_state = {
        "version_high": int(bms.version_high),
        "version_low": int(bms.version_low),
        "status": int(bms.status),
        "soc": int(bms.soc),
        "current": int(bms.current),
        "cycle": int(bms.cycle),
        "bq_ntc": _as_int_list(bms.bq_ntc),
        "mcu_ntc": _as_int_list(bms.mcu_ntc),
        "cell_vol": _as_int_list(bms.cell_vol),
    }

    return {
        "head": _as_int_list(msg.head),
        "level_flag": int(msg.level_flag),
        "frame_reserve": int(msg.frame_reserve),
        "sn": _as_int_list(msg.sn),
        "version": _as_int_list(msg.version),
        "bandwidth": int(msg.bandwidth),
        "imu_state": _imu_to_dict(msg.imu_state),
        "motor_state": motor_state,
        "bms_state": bms_state,
        "foot_force": _as_int_list(msg.foot_force),
        "foot_force_est": _as_int_list(msg.foot_force_est),
        "tick": int(msg.tick),
        "wireless_remote": _as_int_list(msg.wireless_remote),
        "bit_flag": int(msg.bit_flag),
        "adc_reel": float(msg.adc_reel),
        "temperature_ntc1": int(msg.temperature_ntc1),
        "temperature_ntc2": int(msg.temperature_ntc2),
        "power_v": float(msg.power_v),
        "power_a": float(msg.power_a),
        "fan_frequency": _as_int_list(msg.fan_frequency),
        "reserve": int(msg.reserve),
        "crc": int(msg.crc),
    }


class SdkSportStateService(StateService):
    """Subscribe to sportmodestate + lowstate over DDS and keep the latest of each."""

    def __init__(
        self,
        sport_topic: str = "/lf/sportmodestate",
        lowstate_topic: str = "/lowstate",
        lowstate_min_update_interval_sec: float = 120.0,
        network_interface: str = "end0",
        queue_size: int = 10,
    ) -> None:
        self._sport_topic = _to_dds_topic(sport_topic)
        self._lowstate_topic = _to_dds_topic(lowstate_topic)
        self._lowstate_min_update_interval_sec = float(lowstate_min_update_interval_sec)
        self._network_interface = network_interface
        self._queue_size = int(queue_size)

        self._lock = threading.Lock()
        self._latest_sport_state: Optional[dict] = None
        self._latest_low_state: Optional[dict] = None
        self._last_sport_ts = 0.0
        self._last_low_ts = 0.0

        self._sport_sub: Optional[ChannelSubscriber] = None
        self._low_sub: Optional[ChannelSubscriber] = None
        self._initialized = False

    def _info(self) -> dict:
        """Context attached to every service_registry entry."""
        return {
            "network_interface": self._network_interface,
            "sport_topic": self._sport_topic,
            "lowstate_topic": self._lowstate_topic,
        }

    # ── DDS callbacks ─────────────────────────────────────────────

    def _on_sport(self, msg: SportModeState_) -> None:
        try:
            state = _sport_to_dict(msg)
        except Exception:
            logger.exception("Failed to decode SportModeState")
            return
        with self._lock:
            self._latest_sport_state = state
            self._last_sport_ts = time.time()

    def _on_lowstate(self, msg: LowState_) -> None:
        now = time.time()
        if (
            self._lowstate_min_update_interval_sec > 0
            and now - self._last_low_ts < self._lowstate_min_update_interval_sec
        ):
            return
        try:
            state = _low_to_dict(msg)
        except Exception:
            logger.exception("Failed to decode LowState")
            return
        with self._lock:
            self._latest_low_state = state
            self._last_low_ts = now

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        if self._initialized:
            logger.warning("Service already initialized")
            return

        try:
            # ChannelFactory is a singleton whose Init() returns True as soon as
            # it is already initialized, so it is safe to call again after the
            # sport service did. That also means an exception here is never
            # "already initialized" — DDS genuinely could not bind, which in
            # practice means the robot is off and end0 has no carrier/IP.
            ChannelFactoryInitialize(0, self._network_interface)
        except Exception as e:
            msg = (
                f"DDS init failed on interface {self._network_interface}: "
                f"{str(e).rstrip('.')}. "
                "Is the robot powered on and the Ethernet link up?"
            )
            logger.error(msg)
            service_registry.register("state", False, msg, extra_data=self._info())
            return

        try:
            self._sport_sub = ChannelSubscriber(self._sport_topic, SportModeState_)
            self._sport_sub.Init(self._on_sport, self._queue_size)

            self._low_sub = ChannelSubscriber(self._lowstate_topic, LowState_)
            self._low_sub.Init(self._on_lowstate, self._queue_size)
        except Exception as e:
            logger.error("Failed to start SdkSportStateService: %s", e, exc_info=True)
            service_registry.register("state", False, str(e), extra_data=self._info())
            self.stop()
            return

        self._initialized = True
        logger.info(
            "SdkSportStateService started on %s (sport=%s lowstate=%s)",
            self._network_interface,
            self._sport_topic,
            self._lowstate_topic,
        )
        service_registry.register("state", True, extra_data=self._info())

    def stop(self) -> None:
        for name, sub in (("sport", self._sport_sub), ("lowstate", self._low_sub)):
            if sub is None:
                continue
            try:
                sub.Close()
            except Exception:
                logger.debug("Error closing %s subscriber", name, exc_info=True)
        self._sport_sub = None
        self._low_sub = None
        self._initialized = False
        logger.info("SdkSportStateService stopped.")

    # ── DeviceWatcher interface ───────────────────────────────────

    def is_healthy(self) -> bool:
        """Healthy means: started AND a sport packet arrived recently."""
        if not self._initialized:
            return False
        with self._lock:
            last = self._last_sport_ts
        return last > 0 and (time.time() - last) < STALE_AFTER_SEC

    def restart(self) -> None:
        logger.info("Restarting SdkSportStateService...")
        self.stop()
        self.start()

    # ── Read ──────────────────────────────────────────────────────

    def get_latest_state(self) -> Optional[RobotState]:
        with self._lock:
            if self._latest_sport_state is None and self._latest_low_state is None:
                return None
            return RobotState(
                sportmodestate=self._latest_sport_state or {},
                lowstate=self._latest_low_state or {},
            )

    def is_running(self) -> bool:
        return self._initialized

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
