import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.select import SelectEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, UnitOfPower

from . import BaseDevice, DataValue
from .command import CommandId, CommandSet
from ..sensor import (
    CapacitySensorEntity,
    EnergySensorEntity,
    FrequencySensorEntity,
    InfoSensor,
    LevelSensorEntity,
    MilliAmpSensorEntity,
    MilliVoltSensorEntity,
    TempSensorEntity,
    WattsSensorEntity,
    BaseSensor,
    RemainSensorEntity,
    BoolSensorEntity,
)
from ..switch import EnableSwitch
from ..select import MappedSelectEntity
from ..number import ConfigNumber

_LOGGER = logging.getLogger(__name__)

AC_SWITCH_KEY = "inv.cfgAcEnabled"
XBOOST_SWITCH_KEY = "inv.cfgAcXboost"
BEEP_SWITCH_KEY = "pd.beepState"
DC_SWITCH_KEY = "mppt.carState"
AC_ALWAYS_SWITCH_KEY = "pd.acautooutConfig"

BASE_SENSOR_DEFINITIONS: list[tuple[str, str, type[BaseSensor]]] = [
    ("pd.soc", "PD SOC", LevelSensorEntity),
    ("bmsMaster.soc", "BMS SOC", LevelSensorEntity),
    ("bmsMaster.f32ShowSoc", "BMS SOC (float)", LevelSensorEntity),
    ("ems.lcdShowSoc", "Battery Level", LevelSensorEntity),
    ("ems.f32LcdShowSoc", "Battery Level (float)", LevelSensorEntity),
    ("pd.wattsInSum", "PD Total Input Power", WattsSensorEntity),
    ("pd.wattsOutSum", "PD Total Output Power", WattsSensorEntity),
    ("inv.inputWatts", "Inverter Input Power", WattsSensorEntity),
    ("inv.outputWatts", "Inverter Output Power", WattsSensorEntity),
    ("mppt.inWatts", "MPPT Input Power", WattsSensorEntity),
    ("mppt.outWatts", "MPPT Output Power", WattsSensorEntity),
    ("mppt.carOutWatts", "Car Port Output Power", WattsSensorEntity),
    ("mppt.dcdc12vWatts", "Anderson Output Power", WattsSensorEntity),
    ("pd.carWatts", "Car Output Power (PD)", WattsSensorEntity),
    ("pd.typec1Watts", "Type-C 1 Output Power", WattsSensorEntity),
    ("pd.typec2Watts", "Type-C 2 Output Power", WattsSensorEntity),
    ("pd.usb1Watts", "USB 1 Output Power", WattsSensorEntity),
    ("pd.usb2Watts", "USB 2 Output Power", WattsSensorEntity),
    ("pd.qcUsb1Watts", "USB QC 1 Output Power", WattsSensorEntity),
    ("pd.qcUsb2Watts", "USB QC 2 Output Power", WattsSensorEntity),
    ("pd.wirelessWatts", "Wireless Output Power", WattsSensorEntity),
    ("bmsMaster.temp", "BMS Temperature", TempSensorEntity),
    ("bmsMaster.minCellTemp", "BMS Min Cell Temp", TempSensorEntity),
    ("bmsMaster.maxCellTemp", "BMS Max Cell Temp", TempSensorEntity),
    ("bmsMaster.vol", "BMS Voltage (mV)", MilliVoltSensorEntity),
    ("bmsMaster.amp", "BMS Current (mA)", MilliAmpSensorEntity),
    ("bmsMaster.minCellVol", "BMS Min Cell Volt (mV)", MilliVoltSensorEntity),
    ("bmsMaster.maxCellVol", "BMS Max Cell Volt (mV)", MilliVoltSensorEntity),
    ("inv.acInVol", "AC In Voltage (mV)", MilliVoltSensorEntity),
    ("inv.invOutVol", "AC Out Voltage (mV)", MilliVoltSensorEntity),
    ("inv.acInAmp", "AC In Current (mA)", MilliAmpSensorEntity),
    ("inv.invOutAmp", "AC Out Current (mA)", MilliAmpSensorEntity),
    ("mppt.inVol", "Solar In Voltage (mV)", MilliVoltSensorEntity),
    ("mppt.outVol", "DC Out Voltage (mV)", MilliVoltSensorEntity),
    ("mppt.carOutVol", "Car Out Voltage (mV)", MilliVoltSensorEntity),
    ("mppt.dcdc12vVol", "Anderson Out Voltage (mV)", MilliVoltSensorEntity),
    ("mppt.inAmp", "Solar In Current (mA)", MilliAmpSensorEntity),
    ("mppt.outAmp", "DC Out Current (mA)", MilliAmpSensorEntity),
    ("mppt.carOutAmp", "Car Out Current (mA)", MilliAmpSensorEntity),
    ("mppt.dcdc12vAmp", "Anderson Out Current (mA)", MilliAmpSensorEntity),
    ("pd.chgSunPower", "Solar Charge Energy", EnergySensorEntity),
    ("pd.chgPowerAc", "AC Charge Energy", EnergySensorEntity),
    ("pd.chgPowerDc", "DC Charge Energy", EnergySensorEntity),
    ("pd.dsgPowerAc", "AC Discharge Energy", EnergySensorEntity),
    ("pd.dsgPowerDc", "DC Discharge Energy", EnergySensorEntity),
    ("ems.chgRemainTime", "Charge Remaining Time", RemainSensorEntity),
    ("ems.dsgRemainTime", "Discharge Remaining Time", RemainSensorEntity),
    ("bmsMaster.designCap", "BMS Design Capacity", CapacitySensorEntity),
    ("bmsMaster.fullCap", "BMS Full Capacity", CapacitySensorEntity),
    ("bmsMaster.remainCap", "BMS Remain Capacity", CapacitySensorEntity),
    ("inv.acInFreq", "AC In Frequency", FrequencySensorEntity),
    ("inv.invOutFreq", "AC Out Frequency", FrequencySensorEntity),
    ("inv.outTemp", "Inverter Temperature", TempSensorEntity),
    ("mppt.mpptTemp", "MPPT Temperature", TempSensorEntity),
    ("mppt.carTemp", "Car Temperature", TempSensorEntity),
    ("mppt.dc24vTemp", "DC 24V Temperature", TempSensorEntity),
    ("bmsMaster.soh", "BMS Health", InfoSensor),
    ("bmsMaster.cycles", "BMS Cycles", InfoSensor),
    ("inv.cfgAcEnabled", "AC Enabled", BoolSensorEntity),
    ("inv.cfgAcXboost", "X-Boost Enabled", BoolSensorEntity),
]

@dataclass
class SelectDefinition:
    data_key: str
    name: str
    options: dict[str, int]
    cmd_set: CommandSet
    cmd_id: CommandId
    param_key: str

@dataclass
class NumberDefinition:
    data_key: str
    name: str
    min_value: int
    max_value: int
    step: int
    unit: str | None
    cmd_set: CommandSet
    cmd_id: CommandId
    param_builder: Callable[[int], dict[str, Any]]

SELECT_DEFINITIONS: list[SelectDefinition] = [
    SelectDefinition(
        data_key="mppt.cfgDcChgCurrent",
        name="DC Charge Current",
        options={"4A": 4000, "6A": 6000, "8A": 8000},
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.DC_CHARGE_CURRENT,
        param_key="currMa",
    ),
    SelectDefinition(
        data_key="pd.lcdOffSec",
        name="Screen Timeout",
        options={"Never": 0, "10 sec": 10, "30 sec": 30, "1 min": 60, "5 min": 300, "30 min": 1800},
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.LCD_TIMEOUT,
        param_key="lcdTime",
    ),
    SelectDefinition(
        data_key="pd.standByMode",
        name="Unit Timeout",
        options={"Never": 0, "30 min": 30, "1 hr": 60, "2 hr": 120, "6 hr": 360, "12 hr": 720},
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.STANDBY_MODE,
        param_key="standByMode",
    ),
    SelectDefinition(
        data_key="inv.cfgStandbyMin",
        name="AC Timeout",
        options={
            "Never": 0,
            "30 min": 30,
            "1 hr": 60,
            "2 hr": 120,
            "4 hr": 240,
            "6 hr": 360,
            "12 hr": 720,
            "24 hr": 1440,
        },
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.AC_TIMEOUT,
        param_key="standByMins",
    ),
]

NUMBER_DEFINITIONS: list[NumberDefinition] = [
    NumberDefinition(
        data_key="ems.maxChargeSoc",
        name="Max Charge Level",
        min_value=50,
        max_value=100,
        step=1,
        unit=PERCENTAGE,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.MAX_CHARGE_SOC,
        param_builder=lambda value: {"maxChgSoc": int(value)},
    ),
    NumberDefinition(
        data_key="ems.minDsgSoc",
        name="Min Discharge Level",
        min_value=0,
        max_value=30,
        step=1,
        unit=PERCENTAGE,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.MIN_DISCHARGE_SOC,
        param_builder=lambda value: {"minDsgSoc": int(value)},
    ),
    NumberDefinition(
        data_key="pd.bppowerSoc",
        name="Backup Reserve Level",
        min_value=5,
        max_value=100,
        step=1,
        unit=PERCENTAGE,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.BACKUP_RESERVE,
        param_builder=lambda value: {
            "isConfig": 1,
            "bpPowerSoc": int(value),
            "minDsgSoc": 0,
            "maxChgSoc": 0,
        },
    ),
    NumberDefinition(
        data_key="ems.minOpenOilEbSoc",
        name="Generator Auto Start Level",
        min_value=0,
        max_value=30,
        step=1,
        unit=PERCENTAGE,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.GEN_AUTO_START,
        param_builder=lambda value: {"openOilSoc": int(value)},
    ),
    NumberDefinition(
        data_key="ems.maxCloseOilEbSoc",
        name="Generator Auto Stop Level",
        min_value=50,
        max_value=100,
        step=1,
        unit=PERCENTAGE,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.GEN_AUTO_STOP,
        param_builder=lambda value: {"closeOilSoc": int(value)},
    ),
    NumberDefinition(
        data_key="inv.cfgSlowChgWatts",
        name="AC Charging Power",
        min_value=200,
        max_value=2900,
        step=50,
        unit=UnitOfPower.WATT,
        cmd_set=CommandSet.POWER_STATION,
        cmd_id=CommandId.AC_CHARGING_POWER,
        param_builder=lambda value: {"slowChgPower": int(value)},
    ),
]


class PortablePowerStationBase(BaseDevice):
    sensor_definitions: list[tuple[str, str, type[BaseSensor]]] = BASE_SENSOR_DEFINITIONS
    select_definitions: list[SelectDefinition] = SELECT_DEFINITIONS
    number_definitions: list[NumberDefinition] = NUMBER_DEFINITIONS
    optional_sensor_keys: set[str] = set()

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
        if "numbers" not in self.data.mapped_data or self.data.mapped_data["numbers"] is None:
            self.data.mapped_data["numbers"] = {}

    def _init_default_values(self):
        sensors = self.data.mapped_data["sensors"]
        switches = self.data.mapped_data["switches"]
        selects = self.data.mapped_data["selects"]
        numbers = self.data.mapped_data["numbers"]
        for key, name, _cls in self.sensor_definitions:
            sensors.setdefault(key, DataValue(name=name, value=None))
            if key in self.optional_sensor_keys:
                self.data.entity_visibility.setdefault(key, False)
        switches.setdefault(AC_SWITCH_KEY, DataValue(name="AC Switch", value=None))
        switches.setdefault(XBOOST_SWITCH_KEY, DataValue(name="X-Boost Switch", value=None))
        switches.setdefault(BEEP_SWITCH_KEY, DataValue(name="Beeper", value=None))
        switches.setdefault(DC_SWITCH_KEY, DataValue(name="DC Output", value=None))
        switches.setdefault(AC_ALWAYS_SWITCH_KEY, DataValue(name="AC Always On", value=None))
        for definition in self.select_definitions:
            selects.setdefault(definition.data_key, DataValue(name=definition.name, value=None))
        for definition in self.number_definitions:
            numbers.setdefault(definition.data_key, DataValue(name=definition.name, value=None))

    def _sensors(self) -> list[BaseSensor]:
        self._ensure_data_maps()
        sensors: list[BaseSensor] = []
        for key, _name, cls in self.sensor_definitions:
            if key in self.data.mapped_data["sensors"]:
                sensors.append(cls(self, key))
        return sensors

    def switches(self) -> list[SwitchEntity]:
        return [
            EnableSwitch(
                self,
                AC_SWITCH_KEY,
                CommandSet.POWER_STATION,
                CommandId.AC_XBOOST,
                {"enabled": 1},
                {"enabled": 0},
                icon="mdi:power-plug",
            ),
            EnableSwitch(
                self,
                XBOOST_SWITCH_KEY,
                CommandSet.POWER_STATION,
                CommandId.AC_XBOOST,
                {"xboost": 1},
                {"xboost": 0},
                icon="mdi:rocket",
            ),
            EnableSwitch(
                self,
                BEEP_SWITCH_KEY,
                CommandSet.POWER_STATION,
                CommandId.BEEP,
                {"enabled": 1},
                {"enabled": 0},
                icon="mdi:volume-high",
            ),
            EnableSwitch(
                self,
                DC_SWITCH_KEY,
                CommandSet.POWER_STATION,
                CommandId.DC_12V,
                {"enabled": 1},
                {"enabled": 0},
                icon="mdi:car-battery",
            ),
            EnableSwitch(
                self,
                AC_ALWAYS_SWITCH_KEY,
                CommandSet.POWER_STATION,
                CommandId.AC_ALWAYS,
                {"acautooutConfig": 1},
                {"acautooutConfig": 0},
                icon="mdi:power-plug-outline",
            ),
        ]

    def selects(self) -> list[SelectEntity]:
        return [
            MappedSelectEntity(
                self,
                definition.data_key,
                definition.name,
                definition.options,
                definition.cmd_set,
                definition.cmd_id,
                definition.param_key,
            )
            for definition in self.select_definitions
        ]

    def numbers(self) -> list[NumberEntity]:
        return [
            ConfigNumber(
                self,
                definition.data_key,
                definition.name,
                definition.min_value,
                definition.max_value,
                definition.step,
                definition.unit,
                definition.cmd_set,
                definition.cmd_id,
                definition.param_builder,
            )
            for definition in self.number_definitions
        ]

    async def apply_quota_all(self, data: dict):
        self._update_from_flat_params(data)

    async def handle_mqtt_params(self, params: dict):
        if not params:
            return
        self._update_from_flat_params(params)

    def _update_from_flat_params(self, params: dict):
        self._ensure_data_maps()
        sensors = self.data.mapped_data["sensors"]
        switches = self.data.mapped_data["switches"]
        selects = self.data.mapped_data["selects"]
        numbers = self.data.mapped_data["numbers"]
        for key, name, _cls in self.sensor_definitions:
            if key not in params:
                continue
            value = params.get(key)
            data_value = sensors.get(key)
            if data_value is None:
                data_value = DataValue(name=name, value=value)
                sensors[key] = data_value
            else:
                data_value.value = value

            if key == AC_SWITCH_KEY:
                switches[key] = DataValue(name="AC Switch", value=bool(value))
            if key == XBOOST_SWITCH_KEY:
                switches[key] = DataValue(name="X-Boost Switch", value=bool(value))
            if key == BEEP_SWITCH_KEY:
                switches[key] = DataValue(name="Beeper", value=bool(value))
            if key == DC_SWITCH_KEY:
                switches[key] = DataValue(name="DC Output", value=bool(value))
            if key == AC_ALWAYS_SWITCH_KEY:
                switches[key] = DataValue(name="AC Always On", value=bool(value))
            if key in self.optional_sensor_keys:
                self.data.entity_visibility[key] = True

        for definition in self.select_definitions:
            if definition.data_key in params:
                selects[definition.data_key] = DataValue(
                    name=definition.name,
                    value=params.get(definition.data_key),
                )

        for definition in self.number_definitions:
            if definition.data_key in params:
                numbers[definition.data_key] = DataValue(
                    name=definition.name,
                    value=params.get(definition.data_key),
                )


DELTA_PRO_EXTRA_DEFINITIONS: list[tuple[str, str, type[BaseSensor]]] = [
    ("bmsSlave1.soc", "Slave 1 SOC", LevelSensorEntity),
    ("bmsSlave1.temp", "Slave 1 Temperature", TempSensorEntity),
    ("bmsSlave1.inputWatts", "Slave 1 Input Power", WattsSensorEntity),
    ("bmsSlave1.outputWatts", "Slave 1 Output Power", WattsSensorEntity),
    ("bmsSlave1.soh", "Slave 1 SOH", InfoSensor),
    ("bmsSlave1.cycles", "Slave 1 Cycles", InfoSensor),
    ("bmsSlave2.soc", "Slave 2 SOC", LevelSensorEntity),
    ("bmsSlave2.temp", "Slave 2 Temperature", TempSensorEntity),
    ("bmsSlave2.inputWatts", "Slave 2 Input Power", WattsSensorEntity),
    ("bmsSlave2.outputWatts", "Slave 2 Output Power", WattsSensorEntity),
    ("bmsSlave2.soh", "Slave 2 SOH", InfoSensor),
    ("bmsSlave2.cycles", "Slave 2 Cycles", InfoSensor),
]


class DeltaProFamilyStation(PortablePowerStationBase):
    sensor_definitions = BASE_SENSOR_DEFINITIONS + DELTA_PRO_EXTRA_DEFINITIONS
    optional_sensor_keys = {key for key, _name, _cls in DELTA_PRO_EXTRA_DEFINITIONS}


DELTA_2_MAX_EXTRA_DEFINITIONS: list[tuple[str, str, type[BaseSensor]]] = [
    ("bms_slave_bmsSlaveStatus_1.soc", "Slave 1 SOC", LevelSensorEntity),
    ("bms_slave_bmsSlaveStatus_1.temp", "Slave 1 Temperature", TempSensorEntity),
    ("bms_slave_bmsSlaveStatus_1.inputWatts", "Slave 1 Input Power", WattsSensorEntity),
    ("bms_slave_bmsSlaveStatus_1.outputWatts", "Slave 1 Output Power", WattsSensorEntity),
    ("bms_slave_bmsSlaveStatus_1.soh", "Slave 1 SOH", InfoSensor),
    ("bms_slave_bmsSlaveStatus_1.cycles", "Slave 1 Cycles", InfoSensor),
    ("bms_slave_bmsSlaveStatus_2.soc", "Slave 2 SOC", LevelSensorEntity),
    ("bms_slave_bmsSlaveStatus_2.temp", "Slave 2 Temperature", TempSensorEntity),
    ("bms_slave_bmsSlaveStatus_2.inputWatts", "Slave 2 Input Power", WattsSensorEntity),
    ("bms_slave_bmsSlaveStatus_2.outputWatts", "Slave 2 Output Power", WattsSensorEntity),
    ("bms_slave_bmsSlaveStatus_2.soh", "Slave 2 SOH", InfoSensor),
    ("bms_slave_bmsSlaveStatus_2.cycles", "Slave 2 Cycles", InfoSensor),
    ("bms_slave_bmsSlaveInfo_1.accuChgCap", "Slave 1 Accu Charge Cap", InfoSensor),
    ("bms_slave_bmsSlaveInfo_1.accuDsgCap", "Slave 1 Accu Discharge Cap", InfoSensor),
    ("bms_slave_bmsSlaveInfo_1.accuChgEnergy", "Slave 1 Accu Charge Energy", InfoSensor),
    ("bms_slave_bmsSlaveInfo_1.accuDsgEnergy", "Slave 1 Accu Discharge Energy", InfoSensor),
    ("bms_slave_bmsSlaveInfo_2.accuChgCap", "Slave 2 Accu Charge Cap", InfoSensor),
    ("bms_slave_bmsSlaveInfo_2.accuDsgCap", "Slave 2 Accu Discharge Cap", InfoSensor),
    ("bms_slave_bmsSlaveInfo_2.accuChgEnergy", "Slave 2 Accu Charge Energy", InfoSensor),
    ("bms_slave_bmsSlaveInfo_2.accuDsgEnergy", "Slave 2 Accu Discharge Energy", InfoSensor),
]


class Delta2MaxStation(PortablePowerStationBase):
    sensor_definitions = BASE_SENSOR_DEFINITIONS + DELTA_2_MAX_EXTRA_DEFINITIONS
    optional_sensor_keys = {key for key, _name, _cls in DELTA_2_MAX_EXTRA_DEFINITIONS}
