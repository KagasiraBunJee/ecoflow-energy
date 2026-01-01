import logging

from enum import IntEnum

from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity

from . import BaseDevice, DataValue, EntitySensorKey

from ..sensor import InfoSensor, RemainSensorEntity, LevelSensorEntity, AmpSensorEntity, WattsSensorEntity, TempSensorEntity, BaseSensor
from ..switch import EnableSwitch
from ..select import BreakerModeSelect, BreakerCurrentLimitSelect

_LOGGER = logging.getLogger(__name__)

breakers_count = 10
battery_start_index = 10
default_batteries_count = 2

power_output_type = {
    0: "Grid",
    1: "Battery",
    2: "OFF"
}

http_breaker_ctrls_key = "heartbeat.loadCmdChCtrlInfos"
mqtt_breaker_ctrls_key = "loadCmdChCtrlInfos"

http_breaker_value_key = "channelPower.infoList"
mqtt_breaker_value_key = "infoList"

http_battery_info_key = "heartbeat.energyInfos"
mqtt_battery_info_key = "energyInfos"

breaker_suffixes = ["_priority", "_mode", "_cur_limit", "_source"]
battery_suffixes = [
    "_input",
    "_output",
    "_connected",
    "_enabled",
    "_grid_charging",
    "_mppt_charging",
    "_ac_open",
    "_discharge_time",
    "_charge_time",
    "_power_rate",
    "_cur_limit",
    "_bat_temp",
    "_charge_switch",
    ""
]

battery_suffixes_and_classes = [
    ("_input", WattsSensorEntity),
    ("_output", WattsSensorEntity),
    ("_connected", InfoSensor),
    ("_enabled", InfoSensor),
    ("_grid_charging", InfoSensor),
    ("_mppt_charging", InfoSensor),
    ("_ac_open", InfoSensor),
    ("_discharge_time", RemainSensorEntity),
    ("_charge_time", RemainSensorEntity),
    ("_power_rate", WattsSensorEntity),
    ("_cur_limit", AmpSensorEntity),
    ("_bat_temp", TempSensorEntity),
    ("", LevelSensorEntity)
]

class PowerType(IntEnum):
    GRID = 0
    BATTERY = 1
    OFF = 2

    def is_grid(self):
        return self == PowerType.GRID

class SmartHomePanel(BaseDevice):
    def calculate_data(self):
        self._build_structure()

    def configure(self, hass):
        super().configure(hass)
        self._ensure_data_maps()
        self._init_default_values()

    def _ensure_data_maps(self):
        if "sensors" not in self.data.mapped_data or self.data.mapped_data["sensors"] is None:
            self.data.mapped_data["sensors"] = {}
        if "switches" not in self.data.mapped_data or self.data.mapped_data["switches"] is None:
            self.data.mapped_data["switches"] = {}
        if "selects" not in self.data.mapped_data or self.data.mapped_data["selects"] is None:
            self.data.mapped_data["selects"] = {}

    def _init_default_values(self):
        sensors = self.data.mapped_data["sensors"]
        switches = self.data.mapped_data["switches"]

        for i in range(breakers_count):
            base_key = f"{EntitySensorKey.BREAKER}{i}"
            sensors.setdefault(base_key, DataValue(f"Breaker {i + 1}", None))
            sensors.setdefault(f"{base_key}_priority", DataValue(f"Breaker {i + 1} priority", None))
            sensors.setdefault(f"{base_key}_mode", DataValue(f"Breaker {i + 1} mode", None))
            sensors.setdefault(f"{base_key}_source_type", DataValue(f"Breaker {i + 1} mode", None))
            sensors.setdefault(f"{base_key}_source", DataValue(f"Breaker {i + 1} source", None))
            sensors.setdefault(f"{base_key}_cur_limit", DataValue(f"Breaker {i + 1} current limit", None))

        sensors.setdefault(EntitySensorKey.SHP_GRID, DataValue(name="Grid Usage", value=None))
        sensors.setdefault(f"{EntitySensorKey.SHP_GRID}_max_output", DataValue(name="Grid Max Output Power", value=None))
        sensors.setdefault(EntitySensorKey.GRID_STATUS, DataValue(name="Grid Available", value=None))
        sensors.setdefault(EntitySensorKey.BATTERIES_COUNT, DataValue(name="Batteries Count", value=default_batteries_count))

        for i in range(default_batteries_count):
            base_key = f"{EntitySensorKey.BATTERY}{i + 1}"
            battery_name = f"Battery {i + 1}"
            sensors.setdefault(f"{base_key}_input", DataValue(name=f"{battery_name} Input", value=None))
            sensors.setdefault(f"{base_key}_output", DataValue(name=f"{battery_name} Output", value=None))
            sensors.setdefault(f"{base_key}_connected", DataValue(name=f"{battery_name} Connected", value=None))
            sensors.setdefault(f"{base_key}_enabled", DataValue(name=f"{battery_name} Enabled", value=None))
            sensors.setdefault(f"{base_key}_grid_charging", DataValue(name=f"{battery_name} Grid Charging", value=None))
            sensors.setdefault(f"{base_key}_mppt_charging", DataValue(name=f"{battery_name} MPPT Charging", value=None))
            sensors.setdefault(f"{base_key}_ac_open", DataValue(name=f"{battery_name} AC Open", value=None))
            sensors.setdefault(f"{base_key}_discharge_time", DataValue(name=f"{battery_name} Discharge Time", value=None))
            sensors.setdefault(f"{base_key}_charge_time", DataValue(name=f"{battery_name} Charge Time", value=None))
            sensors.setdefault(f"{base_key}_power_rate", DataValue(name=f"{battery_name} Power Rate", value=None))
            sensors.setdefault(f"{base_key}_cur_limit", DataValue(name=f"{battery_name} current limit", value=None))
            sensors.setdefault(f"{base_key}_bat_temp", DataValue(name=f"{battery_name} Battery Temperature", value=None))
            sensors.setdefault(base_key, DataValue(name=battery_name, value=None))
            switches.setdefault(f"{base_key}_charge_switch", DataValue(name=f"{battery_name} Charging", value=None))

        switches.setdefault("eps", DataValue(name="EPS Mode", value=None))

    async def connect_mqtt(self, hass):
        await super().connect_mqtt(hass)

    async def handle_mqtt_params(self, params: dict):
        if not params:
            return
        self._ensure_data_maps()

        heartbeat = params.get("heartbeat", {})
        breaker_ctrls = heartbeat.get(mqtt_breaker_ctrls_key) or params.get(mqtt_breaker_ctrls_key)
        if breaker_ctrls:
            self._parse_breakers_control_info(breaker_ctrls)

        # backupCmdChCtrlInfos are channels 10-11; ignore for breaker selects

        battery_infos = heartbeat.get(mqtt_battery_info_key) or params.get(mqtt_battery_info_key)
        if battery_infos:
            self._parse_battery_info(battery_infos)

        grid_status = heartbeat.get("gridSta") or params.get("gridSta")
        if grid_status is not None:
            self._parse_grid_status(grid_status)

        if mqtt_breaker_value_key in params:
            self._parse_breakers_power_info(params[mqtt_breaker_value_key])

        eps_status = params.get("epsModeInfo.eps") or heartbeat.get("epsModeInfo.eps")
        if eps_status is not None:
            self._parse_eps_info(eps_status)

        load_ch_info = params.get("loadChInfo") or heartbeat.get("loadChInfo")
        if load_ch_info and "info" in load_ch_info:
            self._parse_breaker_names(load_ch_info["info"])

        ch_use_info = params.get("chUseInfo") or heartbeat.get("chUseInfo")
        if ch_use_info and "isEnable" in ch_use_info:
            self._parse_breaker_enablement(ch_use_info["isEnable"])

        load_ch_cur = params.get("loadChCurInfo") or heartbeat.get("loadChCurInfo")
        if load_ch_cur and "cur" in load_ch_cur:
            self._parse_current_limits(load_ch_cur["cur"])

    def _parse_breakers_control_info(self, params):
        for index, breaker in enumerate(params):
            self._parse_breaker_control_info(index, breaker)

    def _parse_breakers_power_info(self, params):
        total_grid_power = 0
        for index, breaker in enumerate(params):
            channel = breaker.get("powCh", breaker.get("ch", index))
            total_grid_power += self._parse_breaker_power_info(channel, breaker)
        self.data.mapped_data["sensors"][EntitySensorKey.SHP_GRID] = DataValue(name="Grid Usage", value=total_grid_power)


    def _parse_breaker_control_info(self, index, breaker):
        if index >= breakers_count:
            return
        if "ctrlSta" not in breaker:
            return
        consume_type = PowerType(breaker["ctrlSta"])
        base_key = f"{EntitySensorKey.BREAKER}{index}"

        self.data.mapped_data["sensors"][f"{base_key}_priority"] = DataValue(f"Breaker {index + 1} priority",
                                                                             breaker.get("priority"))

        self.data.mapped_data["sensors"][f"{base_key}_mode"] = DataValue(f"Breaker {index + 1} mode",
                                                                             breaker.get("ctrlMode"))
        self.data.mapped_data["sensors"][f"{base_key}_source_type"] = DataValue(f"Breaker {index + 1} mode",
                                                                             consume_type)

        self.data.mapped_data["sensors"][f"{base_key}_source"] = DataValue(f"Breaker {index + 1} source",
                                                                             power_output_type[consume_type])

    def _parse_breaker_power_info(self, index, breaker) -> int:
        if "chWatt" not in breaker or "powType" not in breaker:
            return 0
        power_value = breaker["chWatt"]
        consume_type = PowerType(breaker["powType"])

        if index < breakers_count:
            base_key = f"{EntitySensorKey.BREAKER}{index}"
            self.data.mapped_data["sensors"][base_key] = DataValue(f"Breaker {index + 1}", power_value)
            if consume_type.is_grid():
                return power_value
        else:
            bat_index = index - breakers_count + 1
            base_key = f"{EntitySensorKey.BATTERY}{bat_index}"
            input_power = power_value if consume_type == PowerType.OFF else 0
            output_power = power_value if consume_type != PowerType.OFF else 0
            battery_name = f"Battery {bat_index}"
            self.data.mapped_data["sensors"][f"{base_key}_input"] = DataValue(name=f"{battery_name} Input",
                                                                                  value=input_power)

            self.data.mapped_data["sensors"][f"{base_key}_output"] = DataValue(name=f"{battery_name} Output",
                                                                                   value=output_power)
            return input_power
        return 0

    def _parse_battery_item_info(self, battery_index, battery_info) -> int:
        battery_name = f"Battery {battery_index + 1}"
        battery_states = battery_info.get("stateBean", {})
        if not battery_states:
            return 0
        is_connected = bool(battery_states.get("isConnect"))
        battery_rate_power = battery_info.get("ratePower", 0)
        base_key = f"{EntitySensorKey.BATTERY}{battery_index + 1}"

        # sensors
        self.data.mapped_data["sensors"][f"{base_key}_connected"] = DataValue(name=f"{battery_name} Connected",
                                                                                  value=is_connected)

        self.data.mapped_data["sensors"][f"{base_key}_enabled"] = DataValue(name=f"{battery_name} Enabled",
                                                                                value=bool(battery_states["isEnable"]))

        self.data.mapped_data["sensors"][f"{base_key}_grid_charging"] = DataValue(name=f"{battery_name} Grid Charging",
                                                                                      value=bool(battery_states["isGridCharge"]))

        self.data.mapped_data["sensors"][f"{base_key}_mppt_charging"] = DataValue(name=f"{battery_name} MPPT Charging",
                                                                                      value=bool(battery_states["isMpptCharge"]))

        self.data.mapped_data["sensors"][f"{base_key}_ac_open"] = DataValue(name=f"{battery_name} AC Open",
                                                                                value=bool(battery_states["isAcOpen"]))

        self.data.mapped_data["sensors"][f"{base_key}_discharge_time"] = DataValue(name=f"{battery_name} Discharge Time",
                                                                                       value=battery_info.get("dischargeTime"))

        self.data.mapped_data["sensors"][f"{base_key}_charge_time"] = DataValue(name=f"{battery_name} Charge Time",
                                                                                        value=battery_info.get("chargeTime"))

        self.data.mapped_data["sensors"][f"{base_key}"] = DataValue(name=battery_name,
                                                                        value=battery_info.get("batteryPercentage"))

        self.data.mapped_data["sensors"][f"{base_key}_power_rate"] = DataValue(name=f"{battery_name} Power Rate",
                                                                                   value=battery_rate_power)

        self.data.mapped_data["sensors"][f"{base_key}_bat_temp"] = DataValue(name=f"{battery_name} Battery Temperature",
                                                                                 value=battery_info.get("emsBatTemp"))

        # switches
        self.data.mapped_data["switches"][f"{base_key}_charge_switch"] = DataValue(name=f"{battery_name} Charging",
                                                                                      value=bool(battery_states["isGridCharge"]))

        self.data.entity_visibility[base_key] = is_connected
        for suffix in battery_suffixes:
            self.data.entity_visibility[f"{base_key}{suffix}"] = is_connected
        return battery_rate_power

    def _parse_breaker_names(self, breaker_names_data):
        for index, info in enumerate(breaker_names_data):
            if index >= breakers_count:
                return
            base_key = f"{EntitySensorKey.BREAKER}{index}"
            custom_name = info.get("chName")
            if custom_name is None:
                continue
            self.data.mapped_custom_attrs[base_key] = {
                "Custom Name": custom_name
            }

    def _parse_breaker_enablement(self, breakers_enablement):
        for index, visible in enumerate(breakers_enablement):
            if index >= breakers_count:
                return
            base_key = f"{EntitySensorKey.BREAKER}{index}"
            self.data.entity_visibility[base_key] = visible
            for suffix in breaker_suffixes:
                self.data.entity_visibility[f"{base_key}{suffix}"] = visible

    def _parse_current_limits(self, breaker_current_limit):
        for index, limit in enumerate(breaker_current_limit):
            if index < breakers_count:
                base_key = f"{EntitySensorKey.BREAKER}{index}"
                self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(
                    f"Breaker {index + 1} current limit",
                    value=limit,
                )
            else:
                battery_index = index - breakers_count
                base_key = f"{EntitySensorKey.BATTERY}{battery_index + 1}"
                self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(
                    f"Battery {battery_index + 1} current limit",
                    value=limit,
                )

    def _parse_battery_info(self, data):
        shp_max_output = 0
        for index, battery_info in enumerate(data):
            shp_max_output += self._parse_battery_item_info(index, battery_info)

        self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT] = len(data)
        self.data.mapped_data["sensors"][f"{EntitySensorKey.SHP_GRID}_max_output"] = DataValue(name="Grid Max Output Power",
                                                                                               value=shp_max_output)

    def _parse_eps_info(self, status):
        self.data.mapped_data["switches"]["eps"] = DataValue(name="EPS Mode",
                                                             value=status)

    def _parse_grid_status(self, grid_status):
        if grid_status is None:
            return
        self.data.mapped_data["sensors"][EntitySensorKey.GRID_STATUS] = DataValue(
            name="Grid Available",
            value=bool(grid_status),
        )

    def _build_structure(self):
        if self.data.response_data is not None:
            local_data = self.data.response_data
            breakers_controls_info = local_data.get(http_breaker_ctrls_key, [])
            breaker_names_data = local_data.get("loadChInfo", {}).get("info", [])
            breakers_power_values = local_data.get(http_breaker_value_key, [])
            breakers_enablement = local_data.get("chUseInfo.isEnable", [])
            batteries_info = local_data.get(http_battery_info_key, [])
            breaker_current_limit = local_data.get("loadChCurInfo.cur", [])

            missing_keys = []
            if http_breaker_ctrls_key not in local_data:
                missing_keys.append(http_breaker_ctrls_key)
            if http_breaker_value_key not in local_data:
                missing_keys.append(http_breaker_value_key)
            if http_battery_info_key not in local_data:
                missing_keys.append(http_battery_info_key)
            if "loadChInfo" not in local_data:
                missing_keys.append("loadChInfo")
            if "chUseInfo.isEnable" not in local_data:
                missing_keys.append("chUseInfo.isEnable")
            if "loadChCurInfo.cur" not in local_data:
                missing_keys.append("loadChCurInfo.cur")
            if missing_keys:
                _LOGGER.warning("Missing keys in device data: %s", missing_keys)

            self._ensure_data_maps()

            # self._parse_breakers_control_info(breakers_controls_info)
            # self._parse_breakers_power_info(breakers_power_values)
            eps_status = local_data.get("epsModeInfo.eps")
            if eps_status is not None:
                self._parse_eps_info(eps_status)
            grid_status = local_data.get("heartbeat.gridSta")
            if grid_status is not None:
                self._parse_grid_status(grid_status)
            total_grid_power = 0
            shp_max_output = 0
            if breaker_names_data:
                self._parse_breaker_names(breaker_names_data)
            if breakers_enablement:
                self._parse_breaker_enablement(breakers_enablement)
            if breaker_current_limit:
                self._parse_current_limits(breaker_current_limit)
            element_count = max(
                breakers_count + len(batteries_info),
                len(breakers_controls_info),
                len(breakers_power_values),
                len(breaker_current_limit),
            )
            for index in range(element_count):
                if index < len(breakers_controls_info):
                    self._parse_breaker_control_info(index, breakers_controls_info[index])
                if index < len(breakers_power_values):
                    total_grid_power += self._parse_breaker_power_info(index, breakers_power_values[index])
                if index >= breakers_count and index - breakers_count < len(batteries_info):
                    battery_index = index - breakers_count
                    shp_max_output += self._parse_battery_item_info(
                        battery_index,
                        batteries_info[battery_index],
                    )

            if batteries_info:
                self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT] = len(batteries_info)
                self.data.mapped_data["sensors"][f"{EntitySensorKey.SHP_GRID}_max_output"] = DataValue(
                    name="Grid Max Output Power",
                    value=shp_max_output,
                )
            if breakers_power_values:
                self.data.mapped_data["sensors"][EntitySensorKey.SHP_GRID] = DataValue(
                    name="Grid Usage",
                    value=total_grid_power,
                )

            # one time data, not comes from mqtt (for now)
            # for index, info in enumerate(breaker_names_data):
            #     base_key = f"{EntitySensorKey.BREAKER}{index}"
            #     custom_name = info["chName"]
            #     self.data.mapped_custom_attrs[base_key] = {
            #         "Custom Name": custom_name
            #     }

            #     visible = breakers_enablement[index]
            #     self.data.entity_visibility[base_key] = visible
            #     for suffix in breaker_suffixes:
            #         self.data.entity_visibility[f"{base_key}{suffix}"] = visible

            # for index, limit in enumerate(breaker_current_limit):
            #     if index < breakers_count:
            #         base_key = f"{EntitySensorKey.BREAKER}{index}"
            #         self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(f"Breaker {index + 1} current limit",
            #                                                                               value=limit)
            #     else:
            #         bat_index = index - breakers_count + 1
            #         base_key = f"{EntitySensorKey.BATTERY}{bat_index}"
            #         self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(f"Battery {bat_index} current limit",
            #                                                                               value=limit)

            # self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT] = len(batteries_info)

            # self._parse_battery_info(batteries_info)


    def _sensors(self) -> list[BaseSensor]:
        self._ensure_data_maps()
        sensors = list()
        # setup breakers sensors
        for i in range(breakers_count):
            base_key = f"{EntitySensorKey.BREAKER}{i}"
            sensors.extend([
                WattsSensorEntity(self, base_key),
                InfoSensor(self, f"{base_key}_priority"),
                InfoSensor(self, f"{base_key}_mode"),
                InfoSensor(self, f"{base_key}_source"),
                AmpSensorEntity(self, f"{base_key}_cur_limit"),
            ])
        sensors.append(WattsSensorEntity(self, EntitySensorKey.SHP_GRID))
        sensors.append(WattsSensorEntity(self, f"{EntitySensorKey.SHP_GRID}_max_output"))
        sensors.append(BaseSensor(self, EntitySensorKey.GRID_STATUS))

        batteries_count = self.data.mapped_data["sensors"].get(EntitySensorKey.BATTERIES_COUNT, default_batteries_count)
        for i in range(batteries_count):
            base_key = f"{EntitySensorKey.BATTERY}{i + 1}"
            for suffix, cls in battery_suffixes_and_classes:
                sensor_key = f"{base_key}{suffix}"
                if sensor_key in self.data.mapped_data["sensors"]:
                    sensor = cls(self, sensor_key)
                    sensors.append(sensor)

        return sensors

    def switches(self) -> list[SwitchEntity]:
        self._ensure_data_maps()
        switches = [
            EnableSwitch(self, "eps", 11, 24, { "eps": 1 }, { "eps": 0 })
        ]
        batteries_count = self.data.mapped_data["sensors"].get(EntitySensorKey.BATTERIES_COUNT, default_batteries_count)
        for i in range(batteries_count):
            base_key = f"{EntitySensorKey.BATTERY}{i + 1}_charge_switch"
            ch = battery_start_index + i
            switches.append(
                EnableSwitch(self, base_key, 11, 17, { "ch": ch, "sta": 2, "ctrlMode": 0 }, { "ch": ch, "sta": 0, "ctrlMode": 0 })
            )

        return switches

    def selects(self) -> list[SelectEntity]:
        selects = []
        for i in range(breakers_count):
            base_key = f"{EntitySensorKey.BREAKER}{i}"
            selects.append(
                BreakerModeSelect(self, f"{base_key}_mode_select", i, f"{base_key}_mode", f"{base_key}_source_type")
            )
            selects.append(
                BreakerCurrentLimitSelect(self, f"{base_key}_cur_limit_select", i, f"{base_key}_cur_limit")
            )
        _LOGGER.warning("SHP selects created: %s", len(selects))
        return selects
