"""Tests for the Electra RC-3 protocol encoder."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _install_protocol_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    package_root = Path(__file__).parents[1].joinpath("custom_components")
    integration_root = package_root.joinpath("electra_ac_ir")

    climate_const = types.ModuleType("homeassistant.components.climate.const")

    class HVACMode(str):
        OFF = "off"
        AUTO = "auto"
        COOL = "cool"
        HEAT = "heat"
        FAN_ONLY = "fan_only"
        DRY = "dry"

    climate_const.HVACMode = HVACMode
    climate_const.FAN_AUTO = "auto"
    climate_const.FAN_LOW = "low"
    climate_const.FAN_MEDIUM = "medium"
    climate_const.FAN_HIGH = "high"

    commands = types.ModuleType("infrared_protocols.commands")

    class Command:
        def __init__(self, *, modulation: int, repeat_count: int = 0) -> None:
            self.modulation = modulation
            self.repeat_count = repeat_count

    commands.Command = Command

    modules = {
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.components": types.ModuleType("homeassistant.components"),
        "homeassistant.components.climate": types.ModuleType(
            "homeassistant.components.climate"
        ),
        "homeassistant.components.climate.const": climate_const,
        "infrared_protocols": types.ModuleType("infrared_protocols"),
        "infrared_protocols.commands": commands,
    }
    modules["custom_components"] = types.ModuleType("custom_components")
    modules["custom_components"].__path__ = [str(package_root)]
    modules["custom_components.electra_ac_ir"] = types.ModuleType(
        "custom_components.electra_ac_ir"
    )
    modules["custom_components.electra_ac_ir"].__path__ = [str(integration_root)]
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture(scope="module")
def protocol():
    """Load the protocol module with tiny external dependency stubs."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        _install_protocol_stubs(monkeypatch)
        module_path = Path(__file__).parents[1].joinpath(
            "custom_components", "electra_ac_ir", "protocol.py"
        )
        spec = importlib.util.spec_from_file_location(
            "custom_components.electra_ac_ir.protocol", module_path
        )
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        yield module


def legacy_simplify(timings: list[int]) -> list[int]:
    """Simplify timings using the legacy SmartIR helper algorithm."""
    simplified: list[int] = []
    current = 0
    for timing in timings:
        if timing == 0:
            continue
        if current == 0:
            if timing > 0:
                current = timing
            continue
        if (current > 0) == (timing > 0):
            current += timing
        else:
            simplified.append(current)
            current = timing
    if current != 0:
        simplified.append(current)
    return simplified


def legacy_timings(
    *,
    protocol,
    hvac_mode: str,
    fan_mode: str,
    target_temperature: int,
    swing_mode: str,
    power: bool,
) -> list[int]:
    """Generate timings using the legacy SmartIR bit layout and timing rules."""
    payload = 0
    payload |= 1 << 1
    payload |= (target_temperature - 15) << 19
    payload |= (swing_mode == "on") << 25
    payload |= int(protocol.FAN_MODE_TO_PROTOCOL[fan_mode]) << 28
    payload |= int(protocol.HVAC_MODE_TO_PROTOCOL[hvac_mode]) << 30
    payload |= power << 33

    frame = [3000, -3000]
    for bit_index in range(33, -1, -1):
        if payload & (1 << bit_index):
            frame.extend([-1000, 1000])
        else:
            frame.extend([1000, -1000])

    frame = legacy_simplify(frame)
    return frame + frame + frame + [4000]


@pytest.mark.parametrize(
    "hvac_mode", ["off", "auto", "cool", "heat", "fan_only", "dry"]
)
@pytest.mark.parametrize("fan_mode", ["auto", "low", "medium", "high"])
@pytest.mark.parametrize("swing_mode", ["off", "on"])
def test_protocol_matches_legacy_smartir(
    protocol, hvac_mode, fan_mode, swing_mode
) -> None:
    """ElectraRc3Command matches the legacy SmartIR encoder."""
    state = protocol.ElectraRc3State(
        hvac_mode=hvac_mode,
        target_temperature=24,
        fan_mode=fan_mode,
        swing_mode=swing_mode,
        power=hvac_mode != "off",
    )

    command = protocol.ElectraRc3Command(state)

    assert command.modulation == 38000
    assert command.get_raw_timings() == legacy_timings(
        protocol=protocol,
        hvac_mode=hvac_mode,
        fan_mode=fan_mode,
        target_temperature=24,
        swing_mode=swing_mode,
        power=hvac_mode != "off",
    )


@pytest.mark.parametrize("temperature", [16, 30])
def test_temperature_boundaries(protocol, temperature) -> None:
    """Minimum and maximum target temperatures are encoded correctly."""
    state = protocol.ElectraRc3State(
        hvac_mode="cool",
        target_temperature=temperature,
        fan_mode="auto",
        swing_mode="off",
        power=False,
    )

    assert protocol.ElectraRc3Command(state).get_raw_timings() == legacy_timings(
        protocol=protocol,
        hvac_mode="cool",
        fan_mode="auto",
        target_temperature=temperature,
        swing_mode="off",
        power=False,
    )


@pytest.mark.parametrize("temperature", [15, 31])
def test_temperature_outside_supported_range_is_rejected(
    protocol, temperature
) -> None:
    """Out-of-range target temperatures cannot leak into reserved payload bits."""
    state = protocol.ElectraRc3State(
        hvac_mode="cool",
        target_temperature=temperature,
        fan_mode="auto",
        swing_mode="off",
        power=False,
    )

    with pytest.raises(ValueError, match="target temperature"):
        protocol.ElectraRc3Command(state).get_raw_timings()


@pytest.mark.parametrize(
    ("state_kwargs", "payload"),
    [
        (
            {
                "hvac_mode": "cool",
                "target_temperature": 24,
                "fan_mode": "auto",
                "swing_mode": "off",
                "power": False,
            },
            0x70480002,
        ),
        (
            {
                "hvac_mode": "heat",
                "target_temperature": 16,
                "fan_mode": "low",
                "swing_mode": "on",
                "power": True,
            },
            0x282080002,
        ),
    ],
)
def test_known_payload_vectors(protocol, state_kwargs, payload) -> None:
    """Known mode, fan, temperature, swing, and power bits stay stable."""
    assert protocol._build_payload(protocol.ElectraRc3State(**state_kwargs)) == payload


def test_power_bit_changes_payload(protocol) -> None:
    """Off-to-on commands differ from regular on-state updates."""
    base_state = protocol.ElectraRc3State(
        hvac_mode="cool",
        target_temperature=24,
        fan_mode="auto",
        swing_mode="off",
        power=False,
    )
    power_state = protocol.ElectraRc3State(
        hvac_mode="cool",
        target_temperature=24,
        fan_mode="auto",
        swing_mode="off",
        power=True,
    )

    assert protocol.ElectraRc3Command(base_state).get_raw_timings() != (
        protocol.ElectraRc3Command(power_state).get_raw_timings()
    )
