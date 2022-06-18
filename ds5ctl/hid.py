import ctypes as ct
import struct
from dataclasses import dataclass
from enum import IntFlag, Enum
from typing import ClassVar

import hid


class OperatingMode(IntFlag):
    DS4_COMPATIBILITY_MODE = 1 << 0
    DS5_MODE = 1 << 1


class PhysicalEffectControl(IntFlag):
    ENABLE_HAPTICS = 1 << 0 | 1 << 1
    TRIGGER_EFFECTS_RIGHT = 1 << 2
    TRIGGER_EFFECTS_LEFT = 1 << 3


class LightEffectControl(IntFlag):
    MIC_MUTE_LED_CONTROL_ENABLE = 1 << 0
    POWER_SAVE_CONTROL_ENABLE = 1 << 1
    LIGHTBAR_CONTROL_ENABLE = 1 << 2
    RELEASE_LEDS = 1 << 3
    PLAYER_INDICATOR_CONTROL_ENABLE = 1 << 4


class LightbarControl(IntFlag):
    LIGHTBAR_CONTROL_ENABLE = 1 << 2


class PowerSaveControl(IntFlag):
    MIC_MUTE = 1 << 4


class LightbarSetup(int, Enum):
    LIGHT_ON = 1 << 0
    LIGHT_OUT = 1 << 1


class MuteButton(int, Enum):
    OFF = 0
    ON = 1 << 0
    PULSE = 1 << 1


class PlayerLED(IntFlag):
    # Enables the single, center LED
    CENTER = 1 << 2

    # Enables the two LEDs adjacent to and directly surrounding the CENTER LED
    INNER = 1 << 1 | 1 << 3

    # Enables the two outermost LEDs surrounding the INNER LEDs
    OUTER = 1 << 0 | 1 << 4


class TriggerEffectType(IntFlag):
    CONTINUOUS_RESISTANCE = 0x01
    SECTION_RESISTANCE = 0x02
    VIBRATING = 0x06
    EFFECT_EXTENDED = 0x23
    CALIBRATE = 0xfc


class TriggerEffect:
    TYPE: ClassVar[TriggerEffectType] = 0

    def data(self) -> bytes | bytearray:
        return bytes()

    def __bytes__(self) -> bytes:
        return self.TYPE.to_bytes(1, 'little') + bytes(self.data()).ljust(10, b'\x00')

    def as_ctypes_array(self) -> ct.Array:
        return (ct.c_ubyte * 11)(*bytes(self))

    def __hash__(self):
        return hash(id(self))


@dataclass
class ContinuousResistanceTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.CONTINUOUS_RESISTANCE

    start_pos: int = 0
    force: int = 0

    def data(self) -> bytearray:
        return bytearray([self.start_pos, self.force])

    __hash__ = object.__hash__


@dataclass
class SectionResistanceTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.SECTION_RESISTANCE

    start_pos: int = 0
    force: int = 0

    def data(self) -> bytearray:
        return bytearray([self.start_pos, self.force])

    __hash__ = object.__hash__


@dataclass
class VibratingTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.VIBRATING

    frequency: int = 0
    off_time: int = 0

    def data(self) -> bytearray:
        return bytearray([self.frequency, self.off_time])

    __hash__ = object.__hash__


@dataclass
class EffectExtendedTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.EFFECT_EXTENDED

    start_pos: int = 0
    keep_effect: bool = False
    begin_force: int = 0
    middle_force: int = 0
    end_force: int = 0
    frequency: int = 0

    def data(self) -> bytearray:
        return bytearray(
            [
                0xff - self.start_pos,
                0x02 if self.keep_effect else 0x00,
                0x00,
                self.begin_force,
                self.middle_force,
                self.end_force,
                0x00,
                0x00,
                max(1, self.frequency // 2),
            ]
        )

    __hash__ = object.__hash__


@dataclass
class CalibrateTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.CALIBRATE

    __hash__ = object.__hash__


class DualSenseHIDOutput(ct.Structure):
    _fields_ = [
        ('operating_mode', ct.c_ubyte),
        ('physical_effect_control', ct.c_ubyte),
        ('light_effect_control', ct.c_ubyte),

        ('motor_right', ct.c_ubyte),
        ('motor_left', ct.c_ubyte),

        ('unknown2', ct.c_ubyte * 4),
        ('mute_button_led', ct.c_ubyte),  # 0x08 — CONFIRMED
        ('power_save_control', ct.c_ubyte),
        ('right_trigger_effect', ct.c_ubyte * 11),  # 0x11 — CONFIRMED
        ('left_trigger_effect', ct.c_ubyte * 11),

        ('unknown3', ct.c_ubyte * 8),

        ('lightbar_control', ct.c_ubyte),
        ('lightbar_setup', ct.c_ubyte),
        ('led_brightness', ct.c_ubyte),

        ('player_leds', ct.c_ubyte),  # 0x2c — CONFIRMED
        ('lightbar_red', ct.c_ubyte),  # 0x2d — CONFIRMED
        ('lightbar_green', ct.c_ubyte),  # 0x2e — CONFIRMED
        ('lightbar_blue', ct.c_ubyte),  # 0x2f — CONFIRMED
    ]

    @classmethod
    def get_offset_table(cls) -> str:
        entries: list[str] = []

        pos = 0
        for name, typ in cls._fields_:
            size = ct.sizeof(typ)
            entries.append(f'{pos:02x}  {size:02d} {name}')
            pos += size

        return '\n'.join(entries)

    @classmethod
    def print_offset_table(cls):
        print(cls.get_offset_table())


def build_output_data(
    *,
    operating_mode: OperatingMode | int = 0,
    light_effect_control: LightEffectControl | int = 0,
    physical_effect_control: PhysicalEffectControl | int = 0,
    motor_right: int = 0,
    motor_left: int = 0,
    unknown2: bytes = b'',
    mute_button_led: MuteButton | int = 0,
    power_save_control: PowerSaveControl | int = 0,
    right_trigger_effect: TriggerEffect = TriggerEffect(),
    left_trigger_effect: TriggerEffect = TriggerEffect(),
    unknown3: bytes = b'',
    lightbar_control: LightbarControl | int = 0,
    lightbar_setup: LightbarSetup = LightbarSetup.LIGHT_ON,
    led_brightness: int = 0,
    player_leds: PlayerLED | int = 0,
    lightbar_red: int = 0,
    lightbar_green: int = 0,
    lightbar_blue: int = 0,
):
    return DualSenseHIDOutput(
        operating_mode,
        physical_effect_control,
        light_effect_control,
        motor_right,
        motor_left,
        (ct.c_ubyte * 4)(*unknown2),
        mute_button_led,
        power_save_control,
        right_trigger_effect.as_ctypes_array(),
        left_trigger_effect.as_ctypes_array(),
        (ct.c_ubyte * 8)(*unknown3),
        lightbar_control,
        lightbar_setup,
        led_brightness,
        player_leds,
        lightbar_red,
        lightbar_green,
        lightbar_blue,
    )


# TODO(zk): remove me — OLD
def pack_output_data(
    *,
    operating_mode: OperatingMode = 0,
    light_effect_control: LightEffectControl = 0,
    motor_right: int = 0,
    motor_left: int = 0,
    mute_button_led: bool = None,
    power_save_control: PowerSaveControl = 0,
    right_trigger_effect: TriggerEffect = TriggerEffect(),
    left_trigger_effect: TriggerEffect = TriggerEffect(),
    lightbar_control: LightbarControl = 0,
    lightbar_setup: LightbarSetup = 0,
    led_brightness: int = 0,
    player_leds: int = 0,
    lightbar_red: int = 0,
    lightbar_green: int = 0,
    lightbar_blue: int = 0,
    # pack_fmt: str = '<BB x BB 4x BB 11s11s 6x B 2x BBBBBB',
    pack_fmt: str = '<BBBBB 4x BB 11s11s 6x x 2x BBBBBB',
):
    return struct.pack(
        pack_fmt,
        operating_mode,                          # 0x00
        light_effect_control,                          # 0x01
        lightbar_control,                          # 0x02
        motor_right,                    # 0x03
        motor_left,                     # 0x04
                                        # ... [ 4 bytes pad] ...
        mute_button_led or 0,           # 0x08
        power_save_control,             # 0x09
        bytes(right_trigger_effect),    # 0x0a : 0x15
        bytes(left_trigger_effect),     # 0x15 : 0x25
                                        # ... [ 2 bytes pad] ...
        lightbar_setup,                 # 0x2a
        led_brightness,                 # 0x2b
        player_leds,                    # 0x2c — CONFIRMED
        lightbar_red,                   # 0x2d — CONFIRMED
        lightbar_green,                 # 0x2e — CONFIRMED
        lightbar_blue,                  # 0x2f — CONFIRMED
    ).ljust(64, b'\x00')


def get_device() -> hid.device:
    d = hid.device()
    d.open(0x054c, 0x0ce6)
    return d


#                   02 <--- mic mute, 1 = on, 2 = pulsing
#                                                                                           RRGGBB
# fff7f7aaaaaaaaaaaa02aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000ff

# fff7f70000000000000000000000000000000000000000000000000000000000000000000000000000000000110000ff
# fff7f70000000000000400000000aaaaaaaaaaaaaa0000000000000000000000000000000000000000000000fff000


# ff0004000000000000020000000000000000000000000000000000000000000000000000000000000000000000ff0000
# 0603050000000000021000000000000000000000000000000000000000000000000000000401ff000000ff
# 0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
# 0007001717000000000110000000000000000000000000000000000000000000000000000002017e0dff0000

if __name__ == '__main__':
    # run_gui()
    d = get_device()
    try:
        # data = build_output_data(
        #     operating_mode=OutputFlag0.DS5_MODE | OutputFlag0.TRIGGER_LEFT | OutputFlag0.TRIGGER_RIGHT,
        #     physical_effect_control=OutputFlag3.ENABLE_HAPTICS,
        #     right_trigger_effect=SectionResistanceTriggerEffect(240, 255),
        # )
        data = pack_output_data(
            operating_mode=0xff,
            light_effect_control=0xf7,
            right_trigger_effect=SectionResistanceTriggerEffect(240, 255),
            left_trigger_effect=TriggerEffect(),
        )
        raw_data = bytes(data).ljust(64, b'\x00')
        # data = build_output_data(0xff, 0xf7, motor_left=20, motor_right=0)
        print(raw_data.hex(), end=' ')
        print('=', d.write(raw_data))

        import time
        time.sleep(10)
    finally:
        d.close()
