# Ecoflow Energy Integration Context

## Goal
- MQTT-first rewrite of Ecoflow Energy integration (Smart Home Panel only).
- HTTP used only for MQTT creds + device list; `/quota/all` optional best-effort (partial responses OK).
- Preserve entity names/unique_ids.

## Containers/Environment
- HA core debug container: `ha-ecoflow-core-debug` with debugpy on port `5678`.
- HA UI: `http://localhost:28123`.
- Local repo path: `/Users/spolishchuk/Documents/homeassistant/integrations/ecoflow_energy`.

## MQTT topics
- Subscribe: `/open/{certificateAccount}/{sn}/quota`, `/open/{certificateAccount}/{sn}/set_reply`, `/open/{certificateAccount}/{sn}/status`.
- Command publish: `/open/{certificateAccount}/{sn}/set`.

## Important behaviors
- `/quota` payload is authoritative state. Update entities only from `/quota`.
- `loadCmdChCtrlInfos` mapping uses **list index** (0–9). `powCh` is not unique in samples.
- `backupCmdChCtrlInfos` ignored for breaker selects (channels 10–11).
- Power usage: `params.infoList` has no channel id; use index.
- Grid availability: `gridSta` in MQTT heartbeat and HTTP `heartbeat.gridSta` (0/1).

## Key entity changes
- Added breaker current limit select (cmdSet=11, id=20, options 6/13/16/20/30).
- Current limit select has unique_id and device_info.
- Grid status sensor (non-diagnostic) added as `EntitySensorKey.GRID_STATUS`.
- Added shared Portable Power Station base device for DELTA Pro and DELTA 2 Max.
- Portable stations use cmdSet=32; AC/X-Boost switches use cmdSet=32 id=66.
- Refactored Portable Power Station into base + per-family subclasses.
- Extra battery support:
  - Delta/Delta Pro/Delta Max/Delta 2 use `bmsSlave1/2.*`.
  - Delta 2 Max uses `bms_slave_bmsSlaveStatus_*` and `bms_slave_bmsSlaveInfo_*`.
- Added health + cycles diagnostic sensors for main and slave batteries.

## Files changed (high level)
- `custom_components/ecoflow_energy/__init__.py`: MQTT-first setup; optional quota/all; client shutdown.
- `custom_components/ecoflow_energy/api/ecoflow_client.py`: MQTT callback wiring; safe device list.
- `custom_components/ecoflow_energy/api/ecoflow_mqtt.py`: unified MQTT handler; status/quota subscriptions.
- `custom_components/ecoflow_energy/device/__init__.py`: coordinator used only for updates; no polling.
- `custom_components/ecoflow_energy/device/smart_home_panel.py`: MQTT parsing; defaults; grid status; breaker mapping.
- `custom_components/ecoflow_energy/select.py`: breaker mode + current limit select entities.
- `custom_components/ecoflow_energy/switch.py`, `sensor.py`: use hass.data[DOMAIN]["devices"].
- Removed `custom_components/ecoflow_energy/coordinator.py`.
- `custom_components/ecoflow_energy/device/portable_power_station.py`: shared base device and sensors/switches for Delta units.
- `custom_components/ecoflow_energy/api/ecoflow_client.py`: maps Delta variants to per-family classes.

## Sample data
- `mqtt_quota_example_1.json`: heartbeat payload with `loadCmdChCtrlInfos` and `energyInfos`.
- `mqtt_quota_example_breaker_power_usage.json`: `params.infoList` power readings.
- `http_quota_all_example.json`: flattened keys like `heartbeat.loadCmdChCtrlInfos`.
- `examples/delta_pro/http_quota_all_example_1.json`: Delta Pro HTTP quota/all sample (flat keys).
- `examples/delta_pro/mqtt_quota_reply_example_2..5.json`: Delta Pro MQTT partial updates.
