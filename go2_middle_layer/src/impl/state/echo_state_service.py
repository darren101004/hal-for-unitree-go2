import logging
import subprocess
import threading
import time
from typing import Optional, Any, Dict

import yaml

from interfaces.state import StateService
import service_registry
from models.state import RobotState


logger = logging.getLogger("State:Ros2EchoSportStateService")


class Ros2EchoSportStateService(StateService):
    def __init__(
        self,
        sport_topic: str = "/lf/sportmodestate",
        lowstate_topic: str = "/lowstate",
        lowstate_min_update_interval_sec: float = 120.0,
    ) -> None:
        self._sport_topic = sport_topic
        self._lowstate_topic = lowstate_topic
        self._lowstate_min_update_interval_sec = float(lowstate_min_update_interval_sec)
        self._lowstate_last_update_ts = 0.0
        self._latest_sport_state: Optional[Dict[str, Any]] = None
        self._latest_low_state: Optional[Dict[str, Any]] = None
        self._state_lock = threading.Lock()
        self._sport_reader_proc: Optional[subprocess.Popen[str]] = None
        self._low_reader_proc: Optional[subprocess.Popen[str]] = None
        self._reader_proc_lock = threading.Lock()
        self._sport_thread: Optional[threading.Thread] = None
        self._low_thread: Optional[threading.Thread] = None

    def _parse_sport_msg(self, msg: dict) -> Dict[str, Any]:
        return {
            "stamp": {
                "sec": msg["stamp"]["sec"],
                "nanosec": msg["stamp"]["nanosec"],
            },
            "error_code": msg["error_code"],
            "imu_state": {
                "quaternion": msg["imu_state"]["quaternion"],
                "gyroscope": msg["imu_state"]["gyroscope"],
                "accelerometer": msg["imu_state"]["accelerometer"],
                "rpy": msg["imu_state"]["rpy"],
                "temperature": msg["imu_state"]["temperature"],
            },
            "mode": msg["mode"],
            "progress": msg["progress"],
            "gait_type": msg["gait_type"],
            "foot_raise_height": msg["foot_raise_height"],
            "position": msg["position"],
            "body_height": msg["body_height"],
            "velocity": msg["velocity"],
            "yaw_speed": msg["yaw_speed"],
            "range_obstacle": msg["range_obstacle"],
            "foot_force": msg["foot_force"],
            "foot_position_body": msg["foot_position_body"],
            "foot_speed_body": msg["foot_speed_body"],
        }

    def _parse_low_msg(self, msg: dict) -> Dict[str, Any]:
        # ros2 topic echo outputs YAML-ish dict already; normalize to a JSON-friendly shape
        imu = msg.get("imu_state") or {}
        bms = msg.get("bms_state") or {}
        motor_state = msg.get("motor_state") or []

        return {
            "head": msg.get("head", []),
            "level_flag": msg.get("level_flag", 0),
            "frame_reserve": msg.get("frame_reserve", 0),
            "sn": msg.get("sn", []),
            "version": msg.get("version", []),
            "bandwidth": msg.get("bandwidth", 0),
            "imu_state": {
                "quaternion": imu.get("quaternion", []),
                "gyroscope": imu.get("gyroscope", []),
                "accelerometer": imu.get("accelerometer", []),
                "rpy": imu.get("rpy", []),
                "temperature": imu.get("temperature", 0),
            },
            "motor_state": motor_state,
            "bms_state": {
                "version_high": bms.get("version_high", 0),
                "version_low": bms.get("version_low", 0),
                "status": bms.get("status", 0),
                "soc": bms.get("soc", 0),
                "current": bms.get("current", 0),
                "cycle": bms.get("cycle", 0),
                "bq_ntc": bms.get("bq_ntc", []),
                "mcu_ntc": bms.get("mcu_ntc", []),
                "cell_vol": bms.get("cell_vol", []),
            },
            "foot_force": msg.get("foot_force", []),
            "foot_force_est": msg.get("foot_force_est", []),
            "tick": msg.get("tick", 0),
            "wireless_remote": msg.get("wireless_remote", []),
            "bit_flag": msg.get("bit_flag", 0),
            "adc_reel": msg.get("adc_reel", 0.0),
            "temperature_ntc1": msg.get("temperature_ntc1", 0),
            "temperature_ntc2": msg.get("temperature_ntc2", 0),
            "power_v": msg.get("power_v", 0.0),
            "power_a": msg.get("power_a", 0.0),
            "fan_frequency": msg.get("fan_frequency", []),
            "reserve": msg.get("reserve", 0),
            "crc": msg.get("crc", 0),
        }

    def _reader_loop(self, topic: str, kind: str) -> None:
        cmd = [
            "ros2",
            "topic",
            "echo",
            topic,
            "--qos-reliability",
            "best_effort",
        ]

        logger.info("Starting ros2 topic echo for %s on %s", kind, topic)
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            msg = "ros2 command not found. Install ROS2 to enable robot state reading."
            logger.warning(msg)
            service_registry.register("state_echo", False, msg)
            return

        with self._reader_proc_lock:
            if kind == "sportmodestate":
                self._sport_reader_proc = proc
            else:
                self._low_reader_proc = proc

        service_registry.register("state_echo", True)

        current_lines = []

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip()

                if (not current_lines and not line.strip()) or (
                    ":" not in line and line.strip() != "---"
                ):
                    continue

                # End of a message
                if line.strip() == "---":
                    if not current_lines:
                        continue

                    raw = "\n".join(current_lines)
                    current_lines.clear()

                    try:
                        if kind == "lowstate":
                            now = time.time()
                            if (
                                self._lowstate_min_update_interval_sec > 0
                                and now - self._lowstate_last_update_ts
                                < self._lowstate_min_update_interval_sec
                            ):
                                continue
                            self._lowstate_last_update_ts = now

                        msg = yaml.safe_load(raw)
                        if msg:
                            if kind == "sportmodestate":
                                state = self._parse_sport_msg(msg)
                            else:
                                state = self._parse_low_msg(msg)
                            with self._state_lock:
                                if kind == "sportmodestate":
                                    self._latest_sport_state = state
                                else:
                                    self._latest_low_state = state
                    except Exception:
                        logger.exception(
                            "Failed to parse %s from ros2 echo output",
                            kind,
                        )
                    continue

                current_lines.append(line)
        except Exception:
            logger.exception("Exception in Ros2EchoSportStateService reader loop")
        finally:
            with self._reader_proc_lock:
                if kind == "sportmodestate":
                    self._sport_reader_proc = None
                else:
                    self._low_reader_proc = None
            logger.info("ros2 topic echo process ended for %s", kind)

    def is_healthy(self) -> bool:
        """Return True if at least one reader thread is alive."""
        return (self._sport_thread is not None and self._sport_thread.is_alive()) or (
            self._low_thread is not None and self._low_thread.is_alive()
        )

    def restart(self) -> None:
        """Stop and re-start the state reader."""
        self.stop()
        self.start()

    def start(self) -> None:
        if self.is_healthy():
            logger.debug(
                "Ros2EchoSportStateService already running (one or more threads)"
            )
            return

        service_registry.register("state_echo", True)
        self._sport_thread = threading.Thread(
            target=self._reader_loop,
            args=(self._sport_topic, "sportmodestate"),
            daemon=True,
            name="sportmodestate-echo-reader",
        )
        self._low_thread = threading.Thread(
            target=self._reader_loop,
            args=(self._lowstate_topic, "lowstate"),
            daemon=True,
            name="lowstate-echo-reader",
        )
        self._sport_thread.start()
        self._low_thread.start()

    def stop(self) -> None:
        """
        Attempt to terminate the ros2 topic echo processes if running.
        """
        with self._reader_proc_lock:
            procs = [self._sport_reader_proc, self._low_reader_proc]
            for proc in procs:
                if proc is not None and proc.poll() is None:
                    logger.info(
                        "Terminating ros2 topic echo process (pid=%s)", proc.pid
                    )
                    try:
                        proc.terminate()
                    except Exception:
                        logger.exception("Failed to terminate ros2 topic echo process")

        if self._sport_thread is not None:
            self._sport_thread.join(timeout=1.0)
            self._sport_thread = None
        if self._low_thread is not None:
            self._low_thread.join(timeout=1.0)
            self._low_thread = None

    def get_latest_state(self) -> Optional[RobotState]:
        with self._state_lock:
            if self._latest_sport_state is None and self._latest_low_state is None:
                return None
            return RobotState(
                sportmodestate=self._latest_sport_state or {},
                lowstate=self._latest_low_state or {},
            )
