import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from dependency_injector.wiring import Provide, inject
from dependencies import Go2MiddleLayerContainer

from interfaces.state import StateService
from interfaces.sport import SportService
from impl.depth_camera import DepthCameraService
from models.response import Response
from models.sport_option import SportOption
from models.sport_request import SportRequest
from models.state import SportModeEnum

logger = logging.getLogger("UseCase:SportsController")

PI = 3.1415926


def d2r(x: float) -> float:
    return x * PI / 180


def r2d(x: float) -> float:
    return x * 180 / PI


@dataclass(frozen=True)
class SportPolicy:
    move_speed_mps: float = 0.4
    yaw_speed_rps: float = 0.5
    loop_interval_sec: float = 0.01
    command_timeout_sec: float = 3.0
    retry_count: int = 1


class MoveTypeEnum(Enum):
    FORWARD = "move forward"
    BACKWARD = "move backward"
    LEFT = "turn left"
    RIGHT = "turn right"
    STEP_LEFT = "step left"
    STEP_RIGHT = "step right"


class SportController:

    def __init__(
        self,
        policy: Optional[SportPolicy] = None,
    ) -> None:
        self._policy = policy or SportPolicy()
        self._lock = asyncio.Lock()
        self._cancel_event: Optional[asyncio.Event] = None

    def _get_mode(self, state_service: StateService) -> Optional[int]:
        try:
            state = state_service.get_latest_state()
            mode = (
                state.sportmodestate.get("mode")
                if state and isinstance(state.sportmodestate, dict)
                else SportModeEnum.STAND_DOWN.value
            )
            logger.info(f"Mode: {mode}")
            return mode
        except Exception as e:
            logger.error(f"Error getting mode: {e}")
            return SportModeEnum.STAND_DOWN.value

    def _send(
        self,
        sport_service: SportService,
        option: SportOption,
        params: Optional[dict] = None,
    ) -> Response:
        req = SportRequest(option=option, params=params or {})
        last_error: Optional[Response] = None
        for _ in range(max(self._policy.retry_count, 1)):
            res = sport_service.handle(req)
            if res.success:
                return res
            last_error = res
        return last_error or Response(success=False, message="Sport command failed")

    async def _send_async(
        self,
        sport_service: SportService,
        option: SportOption,
        params: Optional[dict] = None,
    ) -> Response:
        return await asyncio.to_thread(self._send, sport_service, option, params)

    def _cancel_current_command(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    async def _run_move_loop(
        self,
        sport_service: SportService,
        params: dict,
        duration_sec: float,
        type_move: MoveTypeEnum = MoveTypeEnum.FORWARD,
        depth_camera_service: Optional[DepthCameraService] = None,
    ) -> Response:
        """
        Run move command loop. Can be interrupted by new commands via cancel event.
        """
        self._cancel_event = asyncio.Event()

        start_time = time.time()
        was_cancelled = False
        if depth_camera_service is not None and await self._is_too_close_to_obstacle(
            depth_camera_service
        ):
            logger.warning("Too close to obstacle to start moving forward")
            return Response(
                success=False, message="Too close to obstacle to start moving forward"
            )

        try:
            while time.time() - start_time < duration_sec:
                if self._cancel_event.is_set():
                    was_cancelled = True
                    break
                if (
                    depth_camera_service is not None
                    and await self._is_too_close_to_obstacle(depth_camera_service)
                ):
                    logger.warning("Too close to obstacle to continue moving forward")
                    break
                res = await self._send_async(
                    sport_service, SportOption.MOVE, params=params
                )
                if not res.success:
                    return Response(
                        success=False, message="Failed to send move command"
                    )
                await asyncio.sleep(self._policy.loop_interval_sec)
        finally:
            self._cancel_event = None

        v = 0
        for key, value in params.items():
            logger.debug(f"key: {key}, value: {value}, type: {type(value)}")
            if value is not None:
                v = max(abs(value), v)

        move_value = (time.time() - start_time) * v
        move_str = (
            f"{int(move_value*100)} centimeters"
            if type_move not in (MoveTypeEnum.LEFT, MoveTypeEnum.RIGHT)
            else f"{int(r2d(move_value))} degrees"
        )
        if was_cancelled:
            return Response(
                success=True,
                message=f"{type_move.value} interrupted by new command. Successfully moved {move_str}",
            )

        _ = await self._send_async(sport_service, SportOption.STOP_MOVE)
        return Response(
            success=True,
            message=f"{type_move.value} completed. Successfully moved {move_str}",
        )

    async def _ensure_standing_async(
        self, state_service: StateService, sport_service: SportService
    ) -> None:
        mode = self._get_mode(state_service)
        if mode in (SportModeEnum.STANDING.value, SportModeEnum.WALKING_POS.value):
            return
        if mode == SportModeEnum.STAND_UP.value:
            _ = await self._send_async(sport_service, SportOption.BALANCE_STAND)
            return
        _ = await self._send_async(sport_service, SportOption.RECOVERY_STAND)

    async def _is_too_close_to_obstacle(
        self,
        depth_camera_service: DepthCameraService,
        min_distance_mm: int = 400,
        max_try_check_count: int = 5,
    ) -> bool:
        for _ in range(max_try_check_count):
            distance = await depth_camera_service.get_latest_distance_to_center()
            logger.debug(f"Distance to obstacle: {distance} mm")
            if distance is None:
                continue
            if distance > min_distance_mm:
                return False
        return True

    @inject
    async def stop_move(
        self,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
    ) -> Response:
        self._cancel_current_command()

        async with self._lock:
            res = await self._send_async(sport_service, SportOption.STOP_MOVE)
            if not res.success:
                return Response(
                    success=False, message="Failed to send stop move command"
                )
            return Response(success=True, message="Stop move command sent successfully")

    @inject
    async def stand_up(
        self,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        async with self._lock:
            mode = self._get_mode(state_service)
            if mode in (SportModeEnum.STANDING.value, SportModeEnum.STAND_UP.value):
                return Response(success=True, message="Already in stand up mode")
            _ = await self._send_async(sport_service, SportOption.RECOVERY_STAND)
            res = await self._send_async(sport_service, SportOption.STAND_UP)
            if not res.success:
                return Response(
                    success=False, message="Failed to send stand up command"
                )
            return Response(success=True, message="Stand up command sent successfully")

    @inject
    async def stand_down(
        self,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        async with self._lock:
            mode = self._get_mode(state_service)
            if mode == SportModeEnum.STAND_DOWN.value:
                return Response(success=True, message="Already in stand down mode")
            if mode not in (SportModeEnum.STAND_UP.value, SportModeEnum.DAMPING.value):
                _ = await self._send_async(sport_service, SportOption.STAND_UP)
            res = await self._send_async(sport_service, SportOption.STAND_DOWN)
            if not res.success:
                return Response(
                    success=False, message="Failed to send stand down command"
                )
            return Response(
                success=True, message="Stand down command sent successfully"
            )

    @inject
    async def move_forward(
        self,
        distance_cm: int,
        max_value_cm: int = 300,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
        depth_camera_service: DepthCameraService = Provide[
            Go2MiddleLayerContainer.depth_camera_service
        ],
    ) -> Response:
        self._cancel_current_command()
        distance_cm = min(max(distance_cm, 0), max_value_cm)
        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)

            distance_m = distance_cm / 100
            vx = self._policy.move_speed_mps
            duration_sec = abs(distance_m / vx) if vx else 0
            params = {"vx": vx, "vy": 0, "vyaw": 0}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                depth_camera_service=depth_camera_service,
                type_move=MoveTypeEnum.FORWARD,
            )
            return res

    @inject
    async def move_backward(
        self,
        distance_cm: int,
        max_value_cm: int = 300,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        distance_cm = min(max(distance_cm, 0), max_value_cm)
        self._cancel_current_command()

        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)

            distance_m = distance_cm / 100
            vx = -self._policy.move_speed_mps
            duration_sec = abs(distance_m / vx) if vx else 0
            params = {"vx": vx, "vy": 0, "vyaw": 0}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                type_move=MoveTypeEnum.BACKWARD,
            )
            return res

    @inject
    async def turn_left(
        self,
        angle_deg: int,
        angle_range_deg: tuple[int, int] = (0, 180),
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        angle_deg = min(max(angle_deg, angle_range_deg[0]), angle_range_deg[1])
        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)

            vyaw = self._policy.yaw_speed_rps
            alpha = d2r(abs(angle_deg))
            duration_sec = max(
                alpha / vyaw - self._policy.loop_interval_sec,
                self._policy.loop_interval_sec,
            )
            params = {"vx": 0, "vy": 0, "vyaw": vyaw}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                type_move=MoveTypeEnum.LEFT,
            )
            return res

    @inject
    async def turn_right(
        self,
        angle_deg: int,
        angle_range_deg: tuple[int, int] = (0, 180),
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        angle_deg = min(max(angle_deg, angle_range_deg[0]), angle_range_deg[1])
        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)

            vyaw = -self._policy.yaw_speed_rps
            alpha = d2r(abs(angle_deg))
            duration_sec = max(
                abs(alpha / vyaw) - self._policy.loop_interval_sec,
                self._policy.loop_interval_sec,
            )
            params = {"vx": 0, "vy": 0, "vyaw": vyaw}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                type_move=MoveTypeEnum.RIGHT,
            )
            return res

    @inject
    async def step_left(
        self,
        distance_cm: int,
        max_value_cm: int = 300,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        distance_cm = min(max(distance_cm, 0), max_value_cm)
        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)
            distance_m = distance_cm / 100
            vy = self._policy.move_speed_mps
            duration_sec = abs(distance_m / vy) if vy else 0
            params = {"vx": 0, "vy": vy, "vyaw": 0}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                type_move=MoveTypeEnum.STEP_LEFT,
            )
            return res

    @inject
    async def step_right(
        self,
        distance_cm: int,
        max_value_cm: int = 300,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
    ) -> Response:
        self._cancel_current_command()

        distance_cm = min(max(distance_cm, 0), max_value_cm)
        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)
            distance_m = distance_cm / 100
            vy = -self._policy.move_speed_mps
            duration_sec = abs(distance_m / vy) if vy else 0
            params = {"vx": 0, "vy": vy, "vyaw": 0}
            res = await self._run_move_loop(
                sport_service=sport_service,
                params=params,
                duration_sec=duration_sec,
                type_move=MoveTypeEnum.STEP_RIGHT,
            )
            return res

    @inject
    async def move_to_target_position(
        self,
        angle_deg: float,
        distance_cm: float,
        angle_range_deg: tuple[int, int] = (-180, 180),
        max_distance_cm: int = 300,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
        state_service: StateService = Provide[
            Go2MiddleLayerContainer.state_service_using_ros2
        ],
        depth_camera_service: DepthCameraService = Provide[
            Go2MiddleLayerContainer.depth_camera_service
        ],
    ) -> Response:
        self._cancel_current_command()

        async with self._lock:
            await self._ensure_standing_async(state_service, sport_service)

            angle_deg = min(max(angle_deg, angle_range_deg[0]), angle_range_deg[1])
            distance_cm = min(max(distance_cm, 0), max_distance_cm)

            # Turn to face target direction
            combined_message = None
            if angle_deg != 0:
                alpha = d2r(abs(angle_deg))
                vyaw = (
                    self._policy.yaw_speed_rps
                    if angle_deg > 0
                    else -self._policy.yaw_speed_rps
                )
                duration_sec = max(
                    alpha / abs(vyaw) - self._policy.loop_interval_sec,
                    self._policy.loop_interval_sec,
                )
                params = {"vx": 0, "vy": 0, "vyaw": vyaw}
                res = await self._run_move_loop(
                    sport_service=sport_service,
                    params=params,
                    duration_sec=duration_sec,
                    type_move=(
                        MoveTypeEnum.LEFT if angle_deg > 0 else MoveTypeEnum.RIGHT
                    ),
                )
                if not res.success:
                    return res
                combined_message = res.message

            # Move forward to target
            if distance_cm > 0:
                distance_m = distance_cm / 100
                vx = self._policy.move_speed_mps
                duration_sec = abs(distance_m / vx) if vx else 0
                params = {"vx": vx, "vy": 0, "vyaw": 0}
                res = await self._run_move_loop(
                    sport_service=sport_service,
                    params=params,
                    duration_sec=duration_sec,
                    depth_camera_service=depth_camera_service,
                    type_move=MoveTypeEnum.FORWARD,
                )
                if not res.success:
                    return res

                if combined_message is None:
                    combined_message = res.message
                else:
                    combined_message += f"Then {res.message}"

            return Response(success=True, message=combined_message)

    @inject
    def warm_up(
        self,
        sport_service: SportService = Provide[Go2MiddleLayerContainer.sport_service],
    ) -> None:
        """Force lazy DI instantiation so the service registers its availability status."""
        pass
