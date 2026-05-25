"""Electra RC-3 infrared protocol encoder."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)

from .compat import InfraredCommand

TIME_UNIT_US = 1000
DEFAULT_MODULATION = 38000
PAYLOAD_BITS = 34
MIN_TARGET_TEMPERATURE = 16
MAX_TARGET_TEMPERATURE = 30

BIT_FIXED_ONE = 1
BIT_TEMPERATURE = 19
BIT_AUTO_SWING = 25
BIT_FAN = 28
BIT_MODE = 30
BIT_POWER = 33


class ElectraRc3Mode(IntEnum):
    """Electra RC-3 HVAC mode values."""

    COOL = 0b001
    HEAT = 0b010
    AUTO = 0b011
    DRY = 0b100
    FAN_ONLY = 0b101
    OFF = 0b111


class ElectraRc3Fan(IntEnum):
    """Electra RC-3 fan values."""

    LOW = 0b00
    MEDIUM = 0b01
    HIGH = 0b10
    AUTO = 0b11


HVAC_MODE_TO_PROTOCOL: dict[HVACMode, ElectraRc3Mode] = {
    HVACMode.COOL: ElectraRc3Mode.COOL,
    HVACMode.HEAT: ElectraRc3Mode.HEAT,
    HVACMode.AUTO: ElectraRc3Mode.AUTO,
    HVACMode.DRY: ElectraRc3Mode.DRY,
    HVACMode.FAN_ONLY: ElectraRc3Mode.FAN_ONLY,
    HVACMode.OFF: ElectraRc3Mode.OFF,
}

FAN_MODE_TO_PROTOCOL: dict[str, ElectraRc3Fan] = {
    FAN_LOW: ElectraRc3Fan.LOW,
    FAN_MEDIUM: ElectraRc3Fan.MEDIUM,
    FAN_HIGH: ElectraRc3Fan.HIGH,
    FAN_AUTO: ElectraRc3Fan.AUTO,
}


@dataclass(frozen=True, slots=True)
class ElectraRc3State:
    """State encoded into an Electra RC-3 command."""

    hvac_mode: HVACMode
    target_temperature: int
    fan_mode: str | None = None
    swing_mode: str | None = None
    power: bool = False


class ElectraRc3Command(InfraredCommand):
    """Electra RC-3 infrared command."""

    def __init__(
        self,
        state: ElectraRc3State,
        *,
        modulation: int = DEFAULT_MODULATION,
        repeat_count: int = 0,
    ) -> None:
        """Initialize the Electra RC-3 command."""
        super().__init__(modulation=modulation, repeat_count=repeat_count)
        self.state = state

    def get_raw_timings(self) -> list[int]:
        """Return raw timings for the Electra RC-3 command."""
        frame = _simplify(_build_frame(_build_payload(self.state)))
        return frame + frame + frame + [4 * TIME_UNIT_US]


def _build_payload(state: ElectraRc3State) -> int:
    """Build the 34-bit Electra RC-3 payload."""
    _validate_target_temperature(state.target_temperature)

    payload = 0
    payload |= 1 << BIT_FIXED_ONE
    payload |= (state.target_temperature - 15) << BIT_TEMPERATURE

    if state.swing_mode == "on":
        payload |= 1 << BIT_AUTO_SWING

    if state.fan_mode is not None:
        payload |= int(FAN_MODE_TO_PROTOCOL[state.fan_mode]) << BIT_FAN

    payload |= int(HVAC_MODE_TO_PROTOCOL[state.hvac_mode]) << BIT_MODE

    if state.power:
        payload |= 1 << BIT_POWER

    return payload


def _validate_target_temperature(target_temperature: int) -> None:
    """Validate the target temperature can be encoded safely."""
    if MIN_TARGET_TEMPERATURE <= target_temperature <= MAX_TARGET_TEMPERATURE:
        return

    raise ValueError(
        "Electra RC-3 target temperature must be between "
        f"{MIN_TARGET_TEMPERATURE} and {MAX_TARGET_TEMPERATURE} C"
    )


def _build_frame(payload: int) -> list[int]:
    """Build one raw Electra RC-3 frame before simplification."""
    timings = [3 * TIME_UNIT_US, -3 * TIME_UNIT_US]

    for bit_index in range(PAYLOAD_BITS - 1, -1, -1):
        if payload & (1 << bit_index):
            timings.extend([-TIME_UNIT_US, TIME_UNIT_US])
        else:
            timings.extend([TIME_UNIT_US, -TIME_UNIT_US])

    return timings


def _simplify(timings: list[int]) -> list[int]:
    """Combine adjacent timings with the same sign."""
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
            continue
        simplified.append(current)
        current = timing

    if current != 0:
        simplified.append(current)

    return simplified
