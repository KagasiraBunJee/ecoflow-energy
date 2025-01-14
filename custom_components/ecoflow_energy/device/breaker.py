
from dataclasses import dataclass


mode_names = ["Auto", "Grid", "Battery", "Off"]

action_property_map = {
    "Auto": {
        "ctrlMode": 0
    },
    "Grid": {
        "ctrlMode": 1,
        "sta": 0,
    },
    "Battery": {
        "ctrlMode": 1,
        "sta": 1,
    },
    "Off": {
        "ctrlMode": 1,
        "sta": 2,
    },
}

@dataclass
class BreakerMode:
    def options(self) -> list[str]:
        return mode_names

    def get_action_settings(self, option) -> dict:
        return action_property_map[option]

    def get_action_name(self, mode: int, sta: int):
        if mode == 1:
            if sta == 0:
                return "Grid"
            elif sta == 1:
                return "Battery"
            else:
                return "Off"
        return "Auto"
