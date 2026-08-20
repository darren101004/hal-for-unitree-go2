import logging
import threading
from typing import Callable, Optional

import rclpy
from rclpy.executors import SingleThreadedExecutor, ExternalShutdownException
from rclpy.node import Node
from unitree_go.msg import SportModeState
from unitree_sdk2py.core.channel import ChannelFactoryInitialize

from interfaces.state import StateService
from models.state import IMUStateDict, SportModeStateDict, TimeSpecDict, RobotState

logger = logging.getLogger("State:SDKSubscriberSportStateService")


class SportStateSubscriber(Node):
    def __init__(
        self,
        context: Optional[rclpy.Context] = None,
        topic: str = "/lf/sportmodestate",
        callback: Optional[Callable[[SportModeState], None]] = None,
        queue_length: int = 10,
    ):
        import os

        super().__init__(f"sport_state_subscriber_{os.getpid()}", context=context)

        self.callback = callback

        self.subscription = self.create_subscription(
            SportModeState,
            topic,
            self.listener_callback,
            queue_length,
        )

        logger.info(f"SportStateSubscriber started on topic {topic}")

    def listener_callback(self, msg: SportModeState):
        if self.callback:
            self.callback(msg)


class SDKSubscriberSportStateService(StateService):
    """
    Read sport state by ROS2 subscriber (DDS) through rclpy.
    """

    def __init__(
        self, topic: str = "/lf/sportmodestate", network_interface: str = "end0"
    ) -> None:
        self._topic = topic
        self._network_interface = network_interface

        self._latest_state_lock = threading.Lock()
        self._latest_state: Optional[SportModeStateDict] = None

        self._subscriber: Optional[SportStateSubscriber] = None
        self._executor: Optional[SingleThreadedExecutor] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._spin_stop_event = threading.Event()
        self._context: Optional[rclpy.Context] = None
        self._initialized = False

    def _state_callback(self, msg: SportModeState) -> None:
        try:
            with self._latest_state_lock:
                stamp = TimeSpecDict(
                    sec=msg.stamp.sec,
                    nanosec=msg.stamp.nanosec,
                )
                imu_state = IMUStateDict(
                    quaternion=msg.imu_state.quaternion,
                    gyroscope=msg.imu_state.gyroscope,
                    accelerometer=msg.imu_state.accelerometer,
                    rpy=msg.imu_state.rpy,
                    temperature=msg.imu_state.temperature,
                )
                self._latest_state = SportModeStateDict(
                    stamp=stamp,
                    error_code=msg.error_code,
                    imu_state=imu_state,
                    mode=msg.mode,
                    progress=msg.progress,
                    gait_type=msg.gait_type,
                    foot_raise_height=msg.foot_raise_height,
                    position=msg.position,
                    body_height=msg.body_height,
                    velocity=msg.velocity,
                    yaw_speed=msg.yaw_speed,
                    range_obstacle=msg.range_obstacle,
                    foot_force=msg.foot_force,
                    foot_position_body=msg.foot_position_body,
                    foot_speed_body=msg.foot_speed_body,
                )
        except Exception:
            logger.exception(
                "Failed to update latest sport state in Ros2SubscriberSportStateService"
            )

    def _spin_loop(self) -> None:
        """Spin executor in a loop with stop event check and exception handling."""
        try:
            while not self._spin_stop_event.is_set():
                self._executor.spin_once(timeout_sec=0.1)
        except ExternalShutdownException:
            logger.info("ROS2 external shutdown received in spin loop")
        except Exception:
            logger.exception("Error in ROS2 spin loop")

    def start(self) -> None:
        if self._initialized:
            logger.debug("Ros2SubscriberSportStateService already initialized")
            return

        try:
            # Safe to call multiple times with same arguments.
            # If already initialized somewhere else, this call also does not harm.
            ChannelFactoryInitialize(0, self._network_interface)
            logger.info(
                "ChannelFactoryInitialize success for Ros2SubscriberSportStateService"
            )
        except Exception:
            logger.exception(
                "ChannelFactoryInitialize failed for Ros2SubscriberSportStateService"
            )

        self._context = rclpy.Context()
        self._context.init(args=None)

        self._subscriber = SportStateSubscriber(
            context=self._context, topic=self._topic, callback=self._state_callback
        )
        self._executor = SingleThreadedExecutor(context=self._context)
        self._executor.add_node(self._subscriber)

        self._spin_stop_event.clear()
        self._spin_thread = threading.Thread(
            target=self._spin_loop, daemon=True, name="sdk_state_spin"
        )
        self._spin_thread.start()

        logger.info(
            "Started SportStateSubscriber in background thread on %s", self._topic
        )
        self._initialized = True

    def stop(self) -> None:
        if not self._initialized:
            return

        logger.info("Stopping SDKSubscriberSportStateService...")

        # Signal the spin loop to stop
        self._spin_stop_event.set()

        if self._executor:
            self._executor.shutdown()
            self._executor = None

        if self._spin_thread:
            self._spin_thread.join(timeout=3.0)
            if self._spin_thread.is_alive():
                logger.warning("Spin thread did not stop within timeout")
            self._spin_thread = None

        if self._subscriber:
            self._subscriber.destroy_node()
            self._subscriber = None

        if self._context:
            try:
                self._context.try_shutdown()
            except Exception:
                logger.debug("ROS2 context already shut down")
            self._context = None

        self._initialized = False
        logger.info("SDKSubscriberSportStateService stopped.")

    def get_latest_state(self) -> Optional[RobotState]:
        with self._latest_state_lock:
            if self._latest_state is None:
                return None
            return RobotState(sportmodestate=self._latest_state, lowstate={})
