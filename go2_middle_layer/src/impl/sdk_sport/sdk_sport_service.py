import logging
from typing import Optional
from models.sport_request import SportRequest
from models.response import Response
from models.sport_option import SportOption
from unitree_sdk2py.go2.sport.sport_client import SportClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
import time
from models.sport_option import get_response_message
from interfaces.sport import SportService
import service_registry

logger = logging.getLogger("Sport:SdkSportService")


class SdkSportService(SportService):
    """Sport service backed by the Unitree SDK.

    Supports ``is_healthy`` / ``restart`` so the DeviceWatcher can
    auto-recover when the robot boots after the server.
    """

    def __init__(self, network_interface: str = "eth0") -> None:
        self._available = False
        self._init_error: Optional[str] = None
        self.sport_client: Optional[SportClient] = None
        self.mapping_api: dict = {}
        self._network_interface = network_interface

        self._init_sdk()

    # ── SDK init / reconnect ───────────────────────────────────────

    def _init_sdk(self) -> None:
        """Attempt to initialize the Unitree Sport SDK.

        Safe to call multiple times (e.g. from ``restart``).
        """
        try:
            ChannelFactoryInitialize(0, self._network_interface)
            time.sleep(1)
            client = SportClient()
            client.SetTimeout(10.0)
            client.Init()
            self.sport_client = client
            self._available = True
            self._init_error = None
        except Exception as e:
            logger.error("Failed to initialize SdkSportService: %s", e)
            self._init_error = str(e)
            self._available = False
            service_registry.register("sport", False, str(e))
            return

        service_registry.register("sport", True)
        self._build_mapping_api()

    def _build_mapping_api(self) -> None:
        """Rebuild the option → SDK method mapping after (re)init."""
        if self.sport_client is None:
            self.mapping_api = {}
            return
        self.mapping_api = {
            SportOption.DAMP: self.sport_client.Damp,
            SportOption.BALANCE_STAND: self.sport_client.BalanceStand,
            SportOption.STOP_MOVE: self.sport_client.StopMove,
            SportOption.STAND_UP: self.sport_client.StandUp,
            SportOption.STAND_DOWN: self.sport_client.StandDown,
            SportOption.RECOVERY_STAND: self.sport_client.RecoveryStand,
            SportOption.EULER: self.sport_client.Euler,
            SportOption.MOVE: self.sport_client.Move,
            SportOption.SIT: self.sport_client.Sit,
            SportOption.RISE_SIT: self.sport_client.RiseSit,
            SportOption.SPEED_LEVEL: self.sport_client.SpeedLevel,
            SportOption.HELLO: self.sport_client.Hello,
            SportOption.STRETCH: self.sport_client.Stretch,
            SportOption.CONTENT: self.sport_client.Content,
            SportOption.DANCE1: self.sport_client.Dance1,
            SportOption.DANCE2: self.sport_client.Dance2,
            SportOption.SWITCH_JOYSTICK: self.sport_client.SwitchJoystick,
            SportOption.POSE: self.sport_client.Pose,
            SportOption.SCRAPE: self.sport_client.Scrape,
            SportOption.FRONT_FLIP: self.sport_client.FrontFlip,
            SportOption.FRONT_JUMP: self.sport_client.FrontJump,
            SportOption.FRONT_POUNCE: self.sport_client.FrontPounce,
            SportOption.HEART: self.sport_client.Heart,
            SportOption.STATIC_WALK: self.sport_client.StaticWalk,
            SportOption.TROT_RUN: self.sport_client.TrotRun,
            # SportOption.ECONOMIC_GAIT: self.sport_client.EconomicGait,
            SportOption.LEFT_FLIP: self.sport_client.LeftFlip,
            SportOption.BACK_FLIP: self.sport_client.BackFlip,
            SportOption.HAND_STAND: self.sport_client.HandStand,
            SportOption.FREE_WALK: self.sport_client.FreeWalk,
            SportOption.FREE_BOUND: self.sport_client.FreeBound,
            SportOption.FREE_JUMP: self.sport_client.FreeJump,
            SportOption.FREE_AVOID: self.sport_client.FreeAvoid,
            SportOption.CLASSIC_WALK: self.sport_client.ClassicWalk,
            SportOption.WALK_UPRIGHT: self.sport_client.WalkUpright,
            SportOption.CROSS_STEP: self.sport_client.CrossStep,
            SportOption.AUTO_RECOVERY_SET: self.sport_client.AutoRecoverySet,
            SportOption.AUTO_RECOVERY_GET: self.sport_client.AutoRecoveryGet,
            SportOption.SWITCH_AVOID_MODE: self.sport_client.SwitchAvoidMode,
        }

    # ── DeviceWatcher interface ─────────────────────────────────

    def is_healthy(self) -> bool:
        """Return True when the SDK client is initialised and usable."""
        return self._available and self.sport_client is not None

    def restart(self) -> None:
        """Re-initialise the SDK connection (called by DeviceWatcher)."""
        logger.info("Restarting SdkSportService...")
        self.sport_client = None
        self._available = False
        self.mapping_api = {}
        self._init_sdk()

    # ── Command handling ──────────────────────────────────────────

    def handle(self, request: SportRequest) -> Response:
        if not self._available:
            return Response(
                success=False,
                message=f"Sport service not available: {self._init_error}",
                code=503,
            )

        logger.debug(f"Handling sport command: {request}")

        try:
            if request.option in self.mapping_api:
                api_function = self.mapping_api[request.option]
                params = request.params
                res = api_function(**params) if params else api_function()
                code = 0
                data = None
                if isinstance(res, int) or isinstance(res, str):
                    code = int(res)
                else:
                    code, _ = res
                    code = int(code)
                if res != 0:
                    return Response(
                        success=False,
                        message=f"Sport command {request.option} failed: {get_response_message(code)}",
                        data=data,
                        code=code,
                    )
                else:
                    return Response(
                        success=True,
                        message=f"Sport command {request.option} executed successfully",
                        data=data,
                        code=0,
                    )  # Success
            else:
                return Response(
                    success=False,
                    message=f"Sport command {request.option} not found",
                    data=None,
                    code=3203,
                )  # API not implemented on the server
        except Exception as e:
            return Response(
                success=False, message=str(e), data=None, code=3202
            )  # Internal server error
