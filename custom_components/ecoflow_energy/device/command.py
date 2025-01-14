from dataclasses import dataclass, field
import json

from enum import IntEnum, StrEnum
from random import randint
from typing import Any, Dict

from dacite import from_dict, Config

class CommandTarget(StrEnum):
    HTTP = "HTTP"
    MQTT = "MQTT"

class CommandSet(IntEnum):
    COMMAND = 11

class CommandId(IntEnum):
    EPS = 24
    BAT_CTRL = 17
    BREAKER_CTRL = 16

@dataclass
class BaseCommandV1:
    id: int
    operateType: str
    version: str
    def __init__(self) -> None:
        self.id = randint(10000, 1000000)
        self.operateType = "TCP"
        self.version = "1.0"

class BaseEntityCommand(BaseCommandV1):
    def __init__(self, sn: str, cmd_set: CommandSet, cmd_id: CommandId, data: dict[str, Any]) -> None:
        super().__init__()
        self.id = randint(10000, 1000000)
        self.moduleType = 1
        self.sn = sn
        self.params = {
            "cmdSet": cmd_set,
            "id": cmd_id,
        }
        self.params.update(data)

    def to_message(self) -> str:
        return json.dumps(self.__dict__)


@dataclass
class BaseEntityCommandResponseData:
    sta: int
    cmdSet: int
    ack: int
    id: int

@dataclass
class BaseEntityCommandResponse(BaseCommandV1):
    code: str
    data: BaseEntityCommandResponseData

    @staticmethod
    def from_dict(dict):
        return from_dict(data_class=BaseEntityCommandResponse, data=dict)