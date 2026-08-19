#!/usr/bin/env python3

import multiprocessing as mp
import threading
import logging
from typing import Optional, Callable
import time

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from unitree_go.msg import SportModeState, LowState

from interfaces.state import StateService
import service_registry
from models.state import RobotState

logger = logging.getLogger("State:Ros2SportStateService")


def _as_float_list(xs) -> list[float]:
    return [float(x) for x in xs]


def _as_int_list(xs) -> list[int]:
    return [int(x) for x in xs]


class SportStateSubscriber(Node):
    def __init__(
        self,
        topic: str = "/lf/sportmodestate",
        on_state_update: Optional[Callable[[dict], None]] = None,
    ):
        super().__init__("sport_state_mcp_subscriber")
        self.subscription = self.create_subscription(
            SportModeState, topic, self.listener_callback, 10
        )
        self._on_state_update = on_state_update
        logger.info("SportState MCP Subscriber is started!")

    def listener_callback(self, msg):
        logger.debug("State received from ROS2 topic")
        imu_state = {
            "quaternion": [float(x) for x in msg.imu_state.quaternion],
            "gyroscope": [float(x) for x in msg.imu_state.gyroscope],
            "accelerometer": [float(x) for x in msg.imu_state.accelerometer],
            "rpy": [float(x) for x in msg.imu_state.rpy],
            "temperature": float(msg.imu_state.temperature),
        }
        stamp = {"sec": int(msg.stamp.sec), "nanosec": int(msg.stamp.nanosec)}
        state = {
            "stamp": stamp,
            "error_code": int(msg.error_code),
            "imu_state": imu_state,
            "mode": int(msg.mode),
            "progress": float(msg.progress),
            "gait_type": int(msg.gait_type),
            "foot_raise_height": float(msg.foot_raise_height),
            "position": [float(x) for x in msg.position],
            "body_height": float(msg.body_height),
            "velocity": [float(x) for x in msg.velocity],
            "yaw_speed": float(msg.yaw_speed),
            "foot_force": [float(x) for x in msg.foot_force],
            "foot_position_body": [float(x) for x in msg.foot_position_body],
            "foot_speed_body": [float(x) for x in msg.foot_speed_body],
        }
        logger.debug(f"State converted: {state}")
        if self._on_state_update is not None:
            self._on_state_update(state)


class LowStateSubscriber(Node):
    def __init__(
        self,
        topic: str = "/lowstate",
        on_state_update: Optional[Callable[[dict], None]] = None,
        min_update_interval_sec: float = 120.0,
    ):
        super().__init__("low_state_mcp_subscriber")
        self.subscription = self.create_subscription(
            LowState, topic, self.listener_callback, 10
        )
        self._on_state_update = on_state_update
        self._min_update_interval_sec = float(min_update_interval_sec)
        self._last_update_ts = 0.0
        logger.info("LowState MCP Subscriber is started!")

    def listener_callback(self, msg):
        now = time.time()
        if (
            self._min_update_interval_sec > 0
            and now - self._last_update_ts < self._min_update_interval_sec
        ):
            return
        self._last_update_ts = now

        logger.debug("LowState received from ROS2 topic")

        imu_state = {
            "quaternion": _as_float_list(msg.imu_state.quaternion),
            "gyroscope": _as_float_list(msg.imu_state.gyroscope),
            "accelerometer": _as_float_list(msg.imu_state.accelerometer),
            "rpy": _as_float_list(msg.imu_state.rpy),
            "temperature": float(msg.imu_state.temperature),
        }

        motor_state = []
        for m in msg.motor_state:
            motor_state.append(
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
            )

        bms_state = {
            "version_high": int(msg.bms_state.version_high),
            "version_low": int(msg.bms_state.version_low),
            "status": int(msg.bms_state.status),
            "soc": int(msg.bms_state.soc),
            "current": int(msg.bms_state.current),
            "cycle": int(msg.bms_state.cycle),
            "bq_ntc": _as_int_list(msg.bms_state.bq_ntc),
            "mcu_ntc": _as_int_list(msg.bms_state.mcu_ntc),
            "cell_vol": _as_int_list(msg.bms_state.cell_vol),
        }

        state = {
            "head": _as_int_list(msg.head),
            "level_flag": int(msg.level_flag),
            "frame_reserve": int(msg.frame_reserve),
            "sn": _as_int_list(msg.sn),
            "version": _as_int_list(msg.version),
            "bandwidth": int(msg.bandwidth),
            "imu_state": imu_state,
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

        if self._on_state_update is not None:
            self._on_state_update(state)


def _ros2_subscriber_process(
    sport_topic: str,
    lowstate_topic: str,
    state_queue: mp.Queue,
    stop_event: mp.Event,
    lowstate_min_update_interval_sec: float,
):
    """
    Run ROS2 subscriber in a separate process
    Args:
        sport_topic: ROS2 topic for SportModeState
        lowstate_topic: ROS2 topic for LowState
        state_queue: Queue to send state to main process
        stop_event: Event to signal when to stop process
    """
    try:
        rclpy.init(args=None)
        logger.info(
            "ROS2 initialized in separate process for topics sport=%s lowstate=%s",
            sport_topic,
            lowstate_topic,
        )

        def _emit(kind: str, state: dict):
            try:
                payload = {"kind": kind, "state": state, "ts": time.time()}
                if not state_queue.full():
                    state_queue.put(payload, block=False)
                else:
                    try:
                        state_queue.get_nowait()
                        state_queue.put(payload, block=False)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error putting state to queue: {e}")

        sport_subscriber = SportStateSubscriber(
            sport_topic,
            on_state_update=lambda s: _emit("sportmodestate", s),
        )
        low_subscriber = LowStateSubscriber(
            lowstate_topic,
            on_state_update=lambda s: _emit("lowstate", s),
            min_update_interval_sec=lowstate_min_update_interval_sec,
        )
        executor = SingleThreadedExecutor()
        executor.add_node(sport_subscriber)
        executor.add_node(low_subscriber)

        logger.info(
            "ROS2 subscriber process started for topics sport=%s lowstate=%s",
            sport_topic,
            lowstate_topic,
        )

        # Spin until stop signal is received
        while not stop_event.is_set():
            executor.spin_once(timeout_sec=0.1)

        # Cleanup
        logger.info(
            "Shutting down ROS2 subscriber process for topics sport=%s lowstate=%s",
            sport_topic,
            lowstate_topic,
        )
        sport_subscriber.destroy_node()
        low_subscriber.destroy_node()
        executor.shutdown()
        rclpy.shutdown()

    except ExternalShutdownException:
        logger.info("ROS2 external shutdown received")
    except Exception as e:
        logger.error(f"Error in ROS2 subscriber process: {e}", exc_info=True)
    finally:
        # Ensure rclpy is shut down even on exceptions
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


class Ros2SportStateService(StateService):
    """
    Service to get state from ROS2 topic through separate process
    """

    def __init__(
        self,
        sport_topic: str = "/lf/sportmodestate",
        lowstate_topic: str = "/lowstate",
        lowstate_min_update_interval_sec: float = 120.0,
        queue_size: int = 10,
    ) -> None:
        self._sport_topic = sport_topic
        self._lowstate_topic = lowstate_topic
        self._lowstate_min_update_interval_sec = float(lowstate_min_update_interval_sec)
        self._queue_size = queue_size

        # Multiprocessing components
        self._state_queue: Optional[mp.Queue] = None
        self._stop_event: Optional[mp.Event] = None
        self._ros2_process: Optional[mp.Process] = None

        # Thread to read from queue
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_stop_event = threading.Event()

        # Latest state storage
        self._latest_state_lock = threading.Lock()
        self._latest_sport_state: Optional[dict] = None
        self._latest_low_state: Optional[dict] = None

        self._initialized = False

    def _state_reader_loop(self):
        """
        Thread to read state from queue and update latest_state
        Run in main process
        """
        logger.info("State reader thread started")
        while not self._reader_stop_event.is_set():
            try:
                if self._state_queue is not None:
                    try:
                        state = self._state_queue.get(timeout=0.1)
                        if isinstance(state, dict) and "kind" in state:
                            kind = state.get("kind")
                            payload = state.get("state")
                            with self._latest_state_lock:
                                if kind == "sportmodestate":
                                    self._latest_sport_state = payload
                                    if isinstance(payload, dict):
                                        logger.debug(
                                            "Latest sport state updated: mode=%s",
                                            payload.get("mode"),
                                        )
                                elif kind == "lowstate":
                                    self._latest_low_state = payload
                                    logger.debug("Latest lowstate updated")
                    except Exception:
                        # Timeout or queue empty
                        pass
            except Exception as e:
                logger.error(f"Error in state reader loop: {e}", exc_info=True)
                time.sleep(0.2)

        logger.info("State reader thread stopped")

    def is_healthy(self) -> bool:
        """Return True if the ROS2 subprocess and reader thread are both alive."""
        return (
            self._initialized
            and self._ros2_process is not None
            and self._ros2_process.is_alive()
            and self._reader_thread is not None
            and self._reader_thread.is_alive()
        )

    def restart(self) -> None:
        """Stop, clean up leaked resources, and re-start the service."""
        self.stop()
        self.start()

    def start(self) -> None:
        """Start service"""
        if self._initialized:
            logger.warning("Service already initialized")
            return

        try:
            ctx = mp.get_context("spawn")

            # Create multiprocessing components
            self._state_queue = ctx.Queue(maxsize=self._queue_size)
            self._stop_event = ctx.Event()

            # Start ROS2 process
            self._ros2_process = ctx.Process(
                target=_ros2_subscriber_process,
                args=(
                    self._sport_topic,
                    self._lowstate_topic,
                    self._state_queue,
                    self._stop_event,
                    self._lowstate_min_update_interval_sec,
                ),
                daemon=True,
                name=(
                    "ros2_subscriber_"
                    f"{self._sport_topic.replace('/', '_')}_"
                    f"{self._lowstate_topic.replace('/', '_')}"
                ),
            )
            self._ros2_process.start()
            logger.info(
                f"Started ROS2 subscriber process (PID: {self._ros2_process.pid})"
            )

            # Start reader thread in main process
            self._reader_stop_event.clear()
            self._reader_thread = threading.Thread(
                target=self._state_reader_loop,
                daemon=True,
                name=(
                    "state_reader_"
                    f"{self._sport_topic.replace('/', '_')}_"
                    f"{self._lowstate_topic.replace('/', '_')}"
                ),
            )
            self._reader_thread.start()
            logger.info("Started state reader thread")

            self._initialized = True
            logger.info(
                "Ros2NodeSportStateService started for topics sport=%s lowstate=%s",
                self._sport_topic,
                self._lowstate_topic,
            )

        except Exception as e:
            logger.error(f"Error starting ROS2 state service: {e}", exc_info=True)
            service_registry.register("state_ros2", False, str(e))
            self.stop()
            return

        service_registry.register("state_ros2", True)

    def stop(self) -> None:
        """Stop service and cleanup resources"""
        if not self._initialized:
            return

        logger.info(
            "Stopping Ros2NodeSportStateService for topics sport=%s lowstate=%s",
            self._sport_topic,
            self._lowstate_topic,
        )

        try:
            # Stop reader thread
            if self._reader_thread is not None:
                self._reader_stop_event.set()
                self._reader_thread.join(timeout=2.0)
                if self._reader_thread.is_alive():
                    logger.warning("Reader thread did not stop gracefully")
                self._reader_thread = None

            # Stop ROS2 process
            if self._ros2_process is not None:
                self._stop_event.set()
                self._ros2_process.join(timeout=3.0)

                if self._ros2_process.is_alive():
                    logger.warning(
                        "ROS2 process did not stop gracefully, terminating..."
                    )
                    self._ros2_process.terminate()
                    self._ros2_process.join(timeout=1.0)

                    if self._ros2_process.is_alive():
                        logger.error("ROS2 process did not terminate, killing...")
                        self._ros2_process.kill()
                        self._ros2_process.join()

                self._ros2_process = None

            # Cleanup queue — robust against crashed child process
            if self._state_queue is not None:
                try:
                    while not self._state_queue.empty():
                        try:
                            self._state_queue.get_nowait()
                        except Exception:
                            break
                except Exception:
                    pass  # queue may be broken after process crash
                try:
                    self._state_queue.cancel_join_thread()
                    self._state_queue.close()
                except Exception as qe:
                    logger.debug("Queue cleanup error (expected after crash): %s", qe)
                self._state_queue = None

            self._stop_event = None
            self._initialized = False

            logger.info(
                "Ros2NodeSportStateService stopped for topics sport=%s lowstate=%s",
                self._sport_topic,
                self._lowstate_topic,
            )

        except Exception as e:
            logger.error(f"Error stopping service: {e}", exc_info=True)

    def get_latest_state(self) -> Optional[RobotState]:
        with self._latest_state_lock:
            if self._latest_sport_state is None and self._latest_low_state is None:
                return None
            return RobotState(
                sportmodestate=self._latest_sport_state or {},
                lowstate=self._latest_low_state or {},
            )

    def is_running(self) -> bool:
        return (
            self._initialized
            and self._ros2_process is not None
            and self._ros2_process.is_alive()
        )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
