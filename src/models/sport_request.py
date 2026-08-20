from __future__ import annotations

from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Optional, Dict, Any

from models.sport_option import SportOption, get_response_message

if TYPE_CHECKING:
    from unitree_sdk2py.go2.sport.sport_client import SportClient


class SportRequest(BaseModel):
    option: SportOption
    params: Dict[str, Any] = Field(default_factory=dict)


class SportResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class SportHandler:
    def __init__(self, sport_client: "SportClient"):
        self.sport_client = sport_client

        self._method_mapping = {
            # Updated mapping according to provided ROBOT_SPORT_API_ID_* list.
            SportOption.DAMP: self.sport_client.Damp,  # 1001
            SportOption.BALANCE_STAND: self.sport_client.BalanceStand,  # 1002
            SportOption.STOP_MOVE: self.sport_client.StopMove,  # 1003
            SportOption.STAND_UP: self.sport_client.StandUp,  # 1004
            SportOption.STAND_DOWN: self.sport_client.StandDown,  # 1005
            SportOption.RECOVERY_STAND: self.sport_client.RecoveryStand,  # 1006
            SportOption.EULER: self.sport_client.Euler,  # 1007
            SportOption.MOVE: self.sport_client.Move,  # 1008
            SportOption.SIT: self.sport_client.Sit,  # 1009
            SportOption.RISE_SIT: self.sport_client.RiseSit,  # 1010
            SportOption.SPEED_LEVEL: self.sport_client.SpeedLevel,  # 1015
            SportOption.HELLO: self.sport_client.Hello,  # 1016
            SportOption.STRETCH: self.sport_client.Stretch,  # 1017
            SportOption.CONTENT: self.sport_client.Content,  # 1020
            SportOption.DANCE1: self.sport_client.Dance1,  # 1022
            SportOption.DANCE2: self.sport_client.Dance2,  # 1023
            SportOption.SWITCH_JOYSTICK: self.sport_client.SwitchJoystick,  # 1027
            SportOption.POSE: self.sport_client.Pose,  # 1028
            SportOption.SCRAPE: self.sport_client.Scrape,  # 1029
            SportOption.FRONT_FLIP: self.sport_client.FrontFlip,  # 1030
            SportOption.FRONT_JUMP: self.sport_client.FrontJump,  # 1031
            SportOption.FRONT_POUNCE: self.sport_client.FrontPounce,  # 1032
            SportOption.HEART: self.sport_client.Heart,  # 1036
            SportOption.STATIC_WALK: self.sport_client.StaticWalk,  # 1061
            SportOption.TROT_RUN: self.sport_client.TrotRun,  # 1062
            # SportOption.ECONOMIC_GAIT: self.sport_client.EconomicGait,       # 1063 # NOT SUPPORTED CURRENTLY
            SportOption.LEFT_FLIP: self.sport_client.LeftFlip,  # 2041
            SportOption.BACK_FLIP: self.sport_client.BackFlip,  # 2043
            SportOption.HAND_STAND: self.sport_client.HandStand,  # 2044
            SportOption.FREE_WALK: self.sport_client.FreeWalk,  # 2045
            SportOption.FREE_BOUND: self.sport_client.FreeBound,  # 2046
            SportOption.FREE_JUMP: self.sport_client.FreeJump,  # 2047
            SportOption.FREE_AVOID: self.sport_client.FreeAvoid,  # 2048
            SportOption.CLASSIC_WALK: self.sport_client.ClassicWalk,  # 2049
            SportOption.WALK_UPRIGHT: self.sport_client.WalkUpright,  # 2050
            SportOption.CROSS_STEP: self.sport_client.CrossStep,  # 2051
            SportOption.AUTO_RECOVERY_SET: self.sport_client.AutoRecoverySet,  # 2054
            SportOption.AUTO_RECOVERY_GET: self.sport_client.AutoRecoveryGet,  # 2055
            SportOption.SWITCH_AVOID_MODE: self.sport_client.SwitchAvoidMode,  # 2058
            # For GO2W
            # SportOption.GET_STATE: self.sport_client.GetState,     # NOT SUPPORTED CURRENTLY
            # SportOption.SWITCH_GAIT: self.sport_client.SwitchGait, # NOT SUPPORTED CURRENTLY
        }

    def handle(self, request: SportRequest) -> SportResponse:

        try:
            if request.option in self._method_mapping:
                method = self._method_mapping[request.option]
                response = method(**request.params) if request.params else method()
                if isinstance(response, int) or isinstance(response, str):
                    code = int(response)
                else:
                    code, _ = response
                    code = int(code)
                if code == 0:
                    return SportResponse(
                        success=True,
                        message=f"Sport command {request.option} executed successfully.",
                        data=None,
                        code=code,
                    )
                else:
                    return SportResponse(
                        success=False,
                        message=f"Sport command {request.option} failed with error {get_response_message(code)}",
                        data=None,
                        code=code,
                    )
            else:
                return SportResponse(
                    success=False,
                    message=f"Sport command {request.option} not found",
                    data=None,
                    code=3203,
                )
        except Exception as e:
            return SportResponse(
                success=False, message=f"Error: {str(e)}", data=None, code=3001
            )
