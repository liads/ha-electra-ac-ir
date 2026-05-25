# Electra AC IR

Home Assistant custom integration for Electra RC-3 air conditioners controlled through Home Assistant's infrared integration layer.

This integration creates an assumed-state `climate` entity. It does not talk directly to a Broadlink, ESPHome, MQTT, or other transmitter. Instead, it consumes an existing `infrared` emitter entity and sends a generated Electra RC-3 raw IR command through that entity.

## Requirements

- Home Assistant 2026.4 or newer.
- An infrared transmitter integration that exposes an `infrared` emitter entity.
- An Electra AC unit compatible with the RC-3 protocol.

## Installation

### HACS

1. Add `https://github.com/liads/ha-electra-ac-ir` as a custom integration repository in HACS.
2. Install **Electra AC IR**.
3. Restart Home Assistant.

### Manual

Copy `custom_components/electra_ac_ir` into your Home Assistant `custom_components` directory and restart Home Assistant.

## Setup

1. Go to **Settings > Devices & services > Add integration**.
2. Search for **Electra AC IR**.
3. Select the infrared transmitter entity.
4. Optionally select temperature, humidity, and binary power sensors.

The entity supports HVAC modes `off`, `auto`, `cool`, `heat`, `fan_only`, and `dry`; fan modes `auto`, `low`, `medium`, and `high`; swing modes `off` and `on`; and target temperatures from 16 C to 30 C.

## Development

Run the pure protocol tests with:

```bash
pytest tests/test_protocol.py
```

Home Assistant integration tests require Home Assistant test dependencies.
