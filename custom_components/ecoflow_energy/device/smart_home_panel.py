import json
import logging

from enum import IntEnum

from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import BaseDevice, DataValue, EntitySensorKey

from ..sensor import InfoSensor, RemainSensorEntity, LevelSensorEntity, AmpSensorEntity, WattsSensorEntity, TempSensorEntity, BaseSensor
from ..switch import EnableSwitch
from ..select import BreakerModeSelect

_LOGGER = logging.getLogger(__name__)

breakers_count = 10
battery_start_index = 10

switch_mode = {
    0: "Auto",
    1: "Manual"
}
power_mode = {
    0: "Use grid",
    1: "Use battery",
    2: "OFF"
}
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

    async def connect_mqtt(self, hass):
        await super().connect_mqtt(hass)
        async_dispatcher_connect(hass, f"device_update_{self.sn}", self._handle_mqtt_message)
        self.api_client.mqtt_client.subscribe_to_device(self.sn, "quota")

    async def _handle_mqtt_message(self, message):
        """Handle incoming MQTT message specifically for power calculation."""
        if self.data.mapped_data["sensors"] is None:
            return

        try:
            topic_command_key = message.topic.split("/")[-1]

            value_str = message.payload.decode("utf-8", errors='ignore')
            value = json.loads(value_str)
            _LOGGER.info(f"sub resp: {value}")
            if topic_command_key != "set_reply":
                if "params" in value:
                    params = value["params"]
                    if mqtt_breaker_value_key in params:
                        self._parse_breakers_power_info(params[mqtt_breaker_value_key])
                    elif "heartbeat" in params:
                        heartbeat = params["heartbeat"]
                        if mqtt_breaker_ctrls_key in heartbeat:
                            self._parse_breakers_control_info(heartbeat[mqtt_breaker_ctrls_key])
                        if mqtt_battery_info_key in heartbeat:
                            self._parse_battery_info(heartbeat[mqtt_battery_info_key])
                    elif "cmdSet" in params and "id" in params: # handle mqtt set command response
                        pass
                await self.coordinator.async_request_refresh()
        except UnicodeDecodeError as error:
            _LOGGER.warning(f"UnicodeDecodeError: {error}. Trying to load json.")
        except Exception as error:
            _LOGGER.warning(f"Exception: {error}. Trying to load json.")

    def _parse_breakers_control_info(self, params):
        for index, breaker in enumerate(params):
            consume_type = PowerType(breaker["ctrlSta"])
            base_key = f"{EntitySensorKey.BREAKER}{index}"

            self.data.mapped_data["sensors"][f"{base_key}_priority"] = DataValue(f"Breaker {index + 1} priority",
                                                                             breaker["priority"])

            self.data.mapped_data["sensors"][f"{base_key}_mode"] = DataValue(f"Breaker {index + 1} mode",
                                                                             breaker["ctrlMode"])
            self.data.mapped_data["sensors"][f"{base_key}_source_type"] = DataValue(f"Breaker {index + 1} mode",
                                                                             consume_type)

            self.data.mapped_data["sensors"][f"{base_key}_source"] = DataValue(f"Breaker {index + 1} source",
                                                                             power_output_type[consume_type])

    def _parse_breakers_power_info(self, params):
        total_grid_power = 0
        for index, breaker in enumerate(params):
            power_value = breaker["chWatt"]
            consume_type = PowerType(breaker["powType"])

            if index < breakers_count:
                base_key = f"{EntitySensorKey.BREAKER}{index}"
                self.data.mapped_data["sensors"][base_key] = DataValue(f"Breaker {index + 1}", power_value)
                if consume_type.is_grid():
                    total_grid_power += power_value
            else:
                bat_index = index - breakers_count + 1
                base_key = f"{EntitySensorKey.BATTERY}{bat_index}"
                input_power = power_value if consume_type == PowerType.OFF else 0
                output_power = power_value if consume_type != PowerType.OFF else 0
                battery_name = f"Battery {bat_index}"

                total_grid_power += input_power

                self.data.mapped_data["sensors"][f"{base_key}_input"] = DataValue(name=f"{battery_name} Input",
                                                                                  value=input_power)

                self.data.mapped_data["sensors"][f"{base_key}_output"] = DataValue(name=f"{battery_name} Output",
                                                                                   value=output_power)
        self.data.mapped_data["sensors"][EntitySensorKey.SHP_GRID] = DataValue(name="Grid Usage", value=total_grid_power)

    def _parse_battery_info(self, data):
        shp_max_output = 0
        for index, battery_info in enumerate(data):
            battery_name = f"Battery {index + 1}"
            battery_states = battery_info["stateBean"]
            is_connected = bool(battery_states["isConnect"])
            battery_rate_power = battery_info["ratePower"]
            shp_max_output += battery_rate_power
            base_key = f"{EntitySensorKey.BATTERY}{index + 1}"

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
                                                                                       value=battery_info["dischargeTime"])

            self.data.mapped_data["sensors"][f"{base_key}_charge_time"] = DataValue(name=f"{battery_name} Charge Time",
                                                                                        value=battery_info["chargeTime"])

            self.data.mapped_data["sensors"][f"{base_key}"] = DataValue(name=battery_name,
                                                                        value=battery_info["batteryPercentage"])

            self.data.mapped_data["sensors"][f"{base_key}_power_rate"] = DataValue(name=f"{battery_name} Power Rate",
                                                                                   value=battery_rate_power)

            self.data.mapped_data["sensors"][f"{base_key}_bat_temp"] = DataValue(name=f"{battery_name} Battery Temperature",
                                                                                 value=battery_info["emsBatTemp"])

            # switches
            self.data.mapped_data["switches"][f"{base_key}_charge_switch"] = DataValue(name=f"{battery_name} Charging",
                                                                                      value=bool(battery_states["isGridCharge"]))

            self.data.entity_visibility[base_key] = is_connected
            for suffix in battery_suffixes:
                self.data.entity_visibility[f"{base_key}{suffix}"] = is_connected

        self.data.mapped_data["sensors"][f"{EntitySensorKey.SHP_GRID}_max_output"] = DataValue(name="Grid Max Output Power",
                                                                                               value=shp_max_output)

    def _parse_eps_info(self, status):
        self.data.mapped_data["switches"]["eps"] = DataValue(name="EPS Mode",
                                                             value=status)

    def _build_structure(self):
        if self.data.response_data is not None:
            local_data = self.data.response_data
            _LOGGER.info(local_data)

            breakers_controls_info = local_data[http_breaker_ctrls_key]
            breaker_names_data = local_data["loadChInfo"]["info"]
            breakers_power_values = local_data[http_breaker_value_key]
            breakers_enablement = local_data["chUseInfo.isEnable"]
            batteries_info = local_data[http_battery_info_key]
            breaker_current_limit = local_data["loadChCurInfo.cur"]

            self.data.mapped_data["sensors"] = {}
            self.data.mapped_data["switches"] = {}
            self.data.mapped_data["selects"] = {}

            self._parse_breakers_control_info(breakers_controls_info)
            self._parse_breakers_power_info(breakers_power_values)
            self._parse_eps_info(local_data["epsModeInfo.eps"])

            # one time data, not comes from mqtt (for now)
            for index, info in enumerate(breaker_names_data):
                base_key = f"{EntitySensorKey.BREAKER}{index}"
                custom_name = info["chName"]
                self.data.mapped_custom_attrs[base_key] = {
                    "Custom Name": custom_name
                }

                visible = breakers_enablement[index]
                self.data.entity_visibility[base_key] = visible
                for suffix in breaker_suffixes:
                    self.data.entity_visibility[f"{base_key}{suffix}"] = visible

            for index, limit in enumerate(breaker_current_limit):
                if index < breakers_count:
                    base_key = f"{EntitySensorKey.BREAKER}{index}"
                    self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(f"Breaker {index + 1} current limit",
                                                                                          value=limit)
                else:
                    bat_index = index - breakers_count + 1
                    base_key = f"{EntitySensorKey.BATTERY}{bat_index}"
                    self.data.mapped_data["sensors"][f"{base_key}_cur_limit"] = DataValue(f"Battery {bat_index} current limit",
                                                                                          value=limit)

            self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT] = len(batteries_info)

            self._parse_battery_info(batteries_info)


    def _sensors(self) -> list[BaseSensor]:
        sensors = list()
        all_data = self.data.mapped_data["sensors"]
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

        batteries_count = self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT]
        for i in range(batteries_count):
            base_key = f"{EntitySensorKey.BATTERY}{i + 1}"
            for suffix, cls in battery_suffixes_and_classes:
                sensor_key = f"{base_key}{suffix}"
                _LOGGER.info(f"getting {sensor_key}")
                if sensor_key in self.data.mapped_data["sensors"]:
                    sensor = cls(self, sensor_key)
                    sensors.append(sensor)

        return sensors

    def switches(self) -> list[SwitchEntity]:
        switches = [
            EnableSwitch(self, "eps", 11, 24, { "eps": 1 }, { "eps": 0 })
        ]
        batteries_count = self.data.mapped_data["sensors"][EntitySensorKey.BATTERIES_COUNT]
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
        return selects