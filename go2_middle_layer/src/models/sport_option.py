from enum import Enum


class SportOption(Enum):
    DAMP = "damp"
    BALANCE_STAND = "balance_stand"
    STOP_MOVE = "stop_move"
    STAND_UP = "stand_up"
    STAND_DOWN = "stand_down"
    RECOVERY_STAND = "recovery_stand"
    EULER = "euler"
    MOVE = "move"
    SIT = "sit"
    RISE_SIT = "rise_sit"
    SPEED_LEVEL = "speed_level"
    HELLO = "hello"
    STRETCH = "stretch"
    CONTENT = "content"
    DANCE1 = "dance1"
    DANCE2 = "dance2"
    SWITCH_JOYSTICK = "switch_joystick"
    POSE = "pose"
    SCRAPE = "scrape"
    FRONT_FLIP = "front_flip"
    FRONT_JUMP = "front_jump"
    FRONT_POUNCE = "front_pounce"
    HEART = "heart"
    LEFT_FLIP = "left_flip"
    BACK_FLIP = "back_flip"
    FREE_WALK = "free_walk"
    FREE_BOUND = "free_bound"
    FREE_JUMP = "free_jump"
    FREE_AVOID = "free_avoid"
    WALK_UPRIGHT = "walk_upright"
    CROSS_STEP = "cross_step"
    STATIC_WALK = "static_walk"
    TROT_RUN = "trot_run"
    ECONOMIC_GAIT = "economic_gait"
    HAND_STAND = "hand_stand"
    CLASSIC_WALK = "classic_walk"
    AUTO_RECOVERY_SET = "auto_recovery_set"
    AUTO_RECOVERY_GET = "auto_recovery_get"
    SWITCH_AVOID_MODE = "switch_avoid_mode"

    # For GO2W
    GET_STATE = "get_state"
    SWITCH_GAIT = "switch_gait"


API_ID_MAP = {
    SportOption.DAMP: 1001,
    SportOption.BALANCE_STAND: 1002,
    SportOption.STOP_MOVE: 1003,
    SportOption.STAND_UP: 1004,
    SportOption.STAND_DOWN: 1005,
    SportOption.RECOVERY_STAND: 1006,
    SportOption.EULER: 1007,
    SportOption.MOVE: 1008,
    SportOption.SIT: 1009,
    SportOption.RISE_SIT: 1010,
    SportOption.SPEED_LEVEL: 1015,
    SportOption.HELLO: 1016,
    SportOption.STRETCH: 1017,
    SportOption.CONTENT: 1020,
    SportOption.DANCE1: 1022,
    SportOption.DANCE2: 1023,
    SportOption.SWITCH_JOYSTICK: 1027,
    SportOption.POSE: 1028,
    SportOption.SCRAPE: 1029,
    SportOption.FRONT_FLIP: 1030,
    SportOption.FRONT_JUMP: 1031,
    SportOption.FRONT_POUNCE: 1032,
    SportOption.HEART: 1036,
    SportOption.STATIC_WALK: 1061,
    SportOption.TROT_RUN: 1062,
    SportOption.ECONOMIC_GAIT: 1063,
    SportOption.LEFT_FLIP: 2041,
    SportOption.BACK_FLIP: 2043,
    SportOption.HAND_STAND: 2044,
    SportOption.FREE_WALK: 2045,
    SportOption.FREE_BOUND: 2046,
    SportOption.FREE_JUMP: 2047,
    SportOption.FREE_AVOID: 2048,
    SportOption.CLASSIC_WALK: 2049,
    SportOption.WALK_UPRIGHT: 2050,
    SportOption.CROSS_STEP: 2051,
    SportOption.AUTO_RECOVERY_SET: 2054,
    SportOption.AUTO_RECOVERY_GET: 2055,
    SportOption.SWITCH_AVOID_MODE: 2058,
    # For GO2W
    SportOption.GET_STATE: 9999,
    SportOption.SWITCH_GAIT: 9998,
}

GO2W_SUPPORTED_OPTIONS = [
    SportOption.DAMP,
    SportOption.BALANCE_STAND,
    SportOption.STOP_MOVE,
    SportOption.STAND_UP,
    SportOption.STAND_DOWN,
    SportOption.RECOVERY_STAND,
    SportOption.MOVE,
    SportOption.SWITCH_GAIT,  # NOT SUPPORTED CURRENTLY
    SportOption.GET_STATE,  # NOT SUPPORTED CURRENTLY
    SportOption.SPEED_LEVEL,
]


RESPONSE_CODE_MAP = {
    0: "Success",
    3001: "Unknown error",
    3102: "Request sending error",
    3103: "API not registered",
    3104: "Request timeout",
    3105: "Request and response data do not match",
    3106: "Invalid response data",
    3107: "Invalid lease",
    3201: "Response sending error",
    3202: "Internal server error",
    3203: "API not implemented on the server",
    3204: "API parameter error",
    3205: "Request rejected",
    3206: "Invalid lease",
    3207: "Lease already exists",
}


def get_response_message(code: int) -> str:
    return RESPONSE_CODE_MAP.get(code, "Unknown error")
