import ctypes as ct
import struct
from contextlib import suppress
from dataclasses import dataclass
from enum import IntFlag, Enum
from typing import ClassVar, Type

import dearpygui.dearpygui as dpg
import hid
from dearpygui.demo import _hsv_to_rgb


class OutputFlag0(IntFlag):
    DS4_COMPATIBILITY_MODE = 1 << 0
    DS5_MODE = 1 << 1
    TRIGGER_RIGHT = 1 << 2
    TRIGGER_LEFT = 1 << 3


class OutputFlag1(IntFlag):
    MIC_MUTE_LED_CONTROL_ENABLE = 1 << 0
    POWER_SAVE_CONTROL_ENABLE = 1 << 1
    LIGHTBAR_CONTROL_ENABLE = 1 << 2
    RELEASE_LEDS = 1 << 3
    PLAYER_INDICATOR_CONTROL_ENABLE = 1 << 4


class OutputFlag2(IntFlag):
    LIGHTBAR_CONTROL_ENABLE = 1 << 2


class OutputFlag3(IntFlag):
    ENABLE_HAPTICS = 1 << 0 | 1 << 1


class HeaderFlags(IntFlag):
    # byte 0
    COMPATIBLE_VIBRATION = OutputFlag0.DS4_COMPATIBILITY_MODE << 16
    HAPTICS_SELECT = OutputFlag0.DS5_MODE << 16
    TRIGGER_RIGHT = OutputFlag0.TRIGGER_RIGHT << 16
    TRIGGER_LEFT = OutputFlag0.TRIGGER_LEFT << 16

    # byte 1
    MIC_MUTE_LED_CONTROL_ENABLE = OutputFlag1.MIC_MUTE_LED_CONTROL_ENABLE << 8
    POWER_SAVE_CONTROL_ENABLE = OutputFlag1.POWER_SAVE_CONTROL_ENABLE << 8
    RELEASE_LEDS = OutputFlag1.RELEASE_LEDS << 8
    PLAYER_INDICATOR_CONTROL_ENABLE = OutputFlag1.PLAYER_INDICATOR_CONTROL_ENABLE << 8

    # byte 2
    LIGHTBAR_CONTROL_ENABLE = 1 << 0x02


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
    CENTER = 1 << 2
    INNER = 1 << 1 | 1 << 3
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


@dataclass
class ContinuousResistanceTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.CONTINUOUS_RESISTANCE

    start_pos: int
    force: int

    def data(self) -> bytearray:
        return bytearray([self.start_pos, self.force])


@dataclass
class SectionResistanceTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.SECTION_RESISTANCE

    start_pos: int
    force: int

    def data(self) -> bytearray:
        return bytearray([self.start_pos, self.force])


@dataclass
class VibratingTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.VIBRATING

    frequency: int
    off_time: int

    def data(self) -> bytearray:
        return bytearray([self.frequency, self.off_time])


@dataclass
class EffectExtendedTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.EFFECT_EXTENDED

    start_pos: int
    keep_effect: bool
    begin_force: int
    middle_force: int
    end_force: int
    frequency: int

    def data(self) -> bytearray:
        return bytearray([
            0xff - self.start_pos,
            0x02 if self.keep_effect else 0x00,
            0x00,
            self.begin_force,
            self.middle_force,
            self.end_force,
            0x00,
            0x00,
            max(1, self.frequency // 2),
        ])


@dataclass
class CalibrateTriggerEffect(TriggerEffect):
    TYPE = TriggerEffectType.CALIBRATE


class DualSenseHIDOutput(ct.Structure):
    _fields_ = [
        ('flag0', ct.c_ubyte),
        ('flag3', ct.c_ubyte),
        ('flag1', ct.c_ubyte),

        ('motor_right', ct.c_ubyte),
        ('motor_left', ct.c_ubyte),

        ('unknown2', ct.c_ubyte * 4),
        ('mute_button_led', ct.c_ubyte),            # 0x08 — CONFIRMED
        ('power_save_control', ct.c_ubyte),
        ('right_trigger_effect', ct.c_ubyte * 11),
        ('left_trigger_effect', ct.c_ubyte * 11),

        ('unknown3', ct.c_ubyte * 8),

        ('flag2', ct.c_ubyte),
        ('lightbar_setup', ct.c_ubyte),
        ('led_brightness', ct.c_ubyte),

        ('player_leds', ct.c_ubyte),                # 0x2c — CONFIRMED
        ('lightbar_red', ct.c_ubyte),               # 0x2d — CONFIRMED
        ('lightbar_green', ct.c_ubyte),             # 0x2e — CONFIRMED
        ('lightbar_blue', ct.c_ubyte),              # 0x2f — CONFIRMED
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
    flag0: OutputFlag0 = 0,
    flag1: OutputFlag1 = 0,
    flag3: OutputFlag3 = 0,
    motor_right: int = 0,
    motor_left: int = 0,
    unknown2: bytes = b'',
    mute_button_led: MuteButton | int = 0,
    power_save_control: PowerSaveControl = 0,
    right_trigger_effect: TriggerEffect = TriggerEffect(),
    left_trigger_effect: TriggerEffect = TriggerEffect(),
    unknown3: bytes = b'',
    flag2: OutputFlag2 = 0,
    lightbar_setup: LightbarSetup = 0,
    led_brightness: int = 0,
    player_leds: PlayerLED | int = 0,
    lightbar_red: int = 0,
    lightbar_green: int = 0,
    lightbar_blue: int = 0,
):
    # 0007001717000000000110000000000000000000000000000000000000000000000000000002017e0dff0000
    return DualSenseHIDOutput(
        flag0,
        flag3,
        flag1,
        motor_right,
        motor_left,
        (ct.c_ubyte * 4)(*unknown2),
        mute_button_led,
        power_save_control,
        right_trigger_effect.as_ctypes_array(),
        left_trigger_effect.as_ctypes_array(),
        (ct.c_ubyte * 8)(*unknown3),
        flag2,
        lightbar_setup,
        led_brightness,
        player_leds,
        lightbar_red,
        lightbar_green,
        lightbar_blue,
    )


def pack_output_data(
    *,
    flag0: OutputFlag0 = 0,
    flag1: OutputFlag1 = 0,
    motor_right: int = 0,
    motor_left: int = 0,
    mute_button_led: bool = None,
    power_save_control: PowerSaveControl = 0,
    right_trigger_effect: TriggerEffect = TriggerEffect(),
    left_trigger_effect: TriggerEffect = TriggerEffect(),
    flag2: OutputFlag2 = 0,
    lightbar_setup: LightbarSetup = 0,
    led_brightness: int = 0,
    player_leds: int = 0,
    lightbar_red: int = 0,
    lightbar_green: int = 0,
    lightbar_blue: int = 0,
    pack_fmt: str = '<BB x BB 4x BB 11s11s 6x B 2x BBBBBB',
):
    return struct.pack(
        pack_fmt,
        flag0,                          # 0x00
        flag1,                          # 0x01
        flag2,                          # 0x02
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


def run_gui():
    dpg.create_context()
    dpg.create_viewport(title='DualSense Controller', width=1024, height=1024)

    params = {
        param: value if value is not None else 0
        for param, value in build_output_data.__kwdefaults__.items()
    }
    hex_data: str = ''

    def on_hex_data_change(value):
        nonlocal hex_data
        hex_data = value

        try:
            data = bytes.fromhex(hex_data)
            data_len = str(len(data))
        except ValueError:
            data = bytes.fromhex(hex_data[:-1])
            data_len = f'{len(data)}/{len(data)+1}'

        dpg.set_value('output_data_length', f'len = {data_len}')

    def update_output_data():

        output_data = build_output_data(**params)
        output_data_bytes = bytes(output_data)
        on_hex_data_change(output_data_bytes.hex())

        dpg.set_value('Output Data', hex_data)

    def on_output_data_change(sender, value):
        on_hex_data_change(value)

    def on_change(sender, value, param):
        print(f'Changing {param} = {value}')
        params[param] = value
        update_output_data()

    def on_bit_flag_change(sender, is_checked, param_flag_info):
        param, flag = param_flag_info

        value = params[param]
        if is_checked:
            value |= flag
        else:
            value &= ~flag

        print(f'{"Adding" if is_checked else "Removing"} {flag} {"to" if is_checked else "from"} {is_checked}')
        on_change(sender, value, param)

    def _add_flag_group(label: str, param: str, flag_cls: Type[IntFlag]):
        current_value = params[param]

        with dpg.collapsing_header(label=label, default_open=True):
            for flag in flag_cls:
                is_checked = current_value & flag > 0
                dpg.add_checkbox(
                    label=f'{flag.name} ({flag.value} = {flag.value:08b})',
                    callback=on_bit_flag_change,
                    user_data=(param, flag),
                    default_value=is_checked,
                )

    def _add_radio_group(label: str, param: str, options: Type[Enum]):
        current_value = params[param]

        def _on_radio_change(sender, label):
            value = label_values[label]
            on_change(sender, value, param)

        with dpg.collapsing_header(label=label, default_open=True):
            label_values = {
                f'{flag.name} ({flag.value} = {flag.value:08b})': flag.value
                for flag in options
            }
            value_labels = {v: k for k, v in label_values.items()}

            dpg.add_radio_button(
                items=list(label_values),
                label=label,
                tag=param,
                callback=_on_radio_change,
                user_data=param,
                default_value=value_labels.get(current_value),
            )

    def _add_byte_slider(label: str, param: str):
        dpg.add_slider_int(
            label=label,
            user_data=param,
            callback=on_change,
            min_value=0,
            max_value=255,
            default_value=params[param],
        )

    def _add_button_theme(tag: str, base_hue: float, *, rounding: int = 1, padding: int = 12):
        with dpg.theme(tag=tag), dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, _hsv_to_rgb(base_hue, 0.6, 0.6))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, _hsv_to_rgb(base_hue, 0.8, 0.8))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, _hsv_to_rgb(base_hue, 0.7, 0.7))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, rounding)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, padding, padding)

    _add_button_theme('primary', 4/7)
    _add_button_theme('secondary', 5/7)
    _add_button_theme('danger', 0)

    d = get_device()

    def reconnect():
        nonlocal d
        with suppress(IOError):
            print('Closing device ...', end=' ')
            d.close()
        print('Closed')

        print('Reconnecting ...', end=' ')
        d = get_device()
        print('Connected')

    def send_to_controller():
        data = bytes.fromhex(hex_data)[:64].ljust(64, b'\x00')

        NUM_ATTEMPTS = 3
        for i in range(NUM_ATTEMPTS):
            print('Writing', data, '=', end=' ')
            try:
                print(d.write(data))
                break
            except IOError:
                print(f'ERROR {i+1/NUM_ATTEMPTS}')
                reconnect()

        else:
            print('Failed to write', data)

    try:
        with dpg.window(tag='DualSense Controller'):
            dpg.set_primary_window('DualSense Controller', True)

            with dpg.group(horizontal=True):
                dpg.add_input_text(tag='Output Data', default_value=hex_data, width=940, callback=on_output_data_change)
                dpg.add_text(tag='output_data_length')
            update_output_data()

            _add_flag_group('Flag0', 'flag0', OutputFlag0)
            _add_flag_group('Flag3', 'flag3', OutputFlag3)
            _add_flag_group('Flag1', 'flag1', OutputFlag1)

            with (
                dpg.collapsing_header(label='Rumble', default_open=True),
                dpg.group(),
            ):
                _add_byte_slider('Rumble Left', 'motor_left')
                _add_byte_slider('Rumble Right', 'motor_right')

            _add_radio_group('Mute Button LED', 'mute_button_led', MuteButton)

            _add_flag_group('Power Save Control', 'power_save_control', PowerSaveControl)

            # TODO: trigger effects

            _add_flag_group('Flag2', 'flag2', OutputFlag2)

            _add_radio_group('Lightbar Setup', 'lightbar_setup', LightbarSetup)
            _add_byte_slider('LED Brightness', 'led_brightness')
            _add_flag_group('Player LEDS', 'player_leds', PlayerLED)

            with dpg.collapsing_header(label='Lightbar Colour', default_open=True):
                _add_byte_slider('Red', 'lightbar_red')
                _add_byte_slider('Green', 'lightbar_green')
                _add_byte_slider('Blue', 'lightbar_blue')

            with dpg.group(horizontal=True):
                dpg.add_button(label='Send', callback=send_to_controller, tag='send')
                dpg.bind_item_theme(dpg.last_item(), 'primary')

                dpg.add_button(label='Reconnect', callback=reconnect, tag='reconnect')
                dpg.bind_item_theme(dpg.last_item(), 'danger')

            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.start_dearpygui()
            dpg.destroy_context()
    finally:
        d.close()


#                   02 <--- mic mute, 1 = on, 2 = pulsing
#                                                                                           RRGGBB
# fff7f7aaaaaaaaaaaa02aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000ff

# fff7f70000000000000000000000000000000000000000000000000000000000000000000000000000000000110000ff
# fff7f70000000000000400000000aaaaaaaaaaaaaa0000000000000000000000000000000000000000000000fff000


# ff0004000000000000020000000000000000000000000000000000000000000000000000000000000000000000ff0000
# 0603050000000000021000000000000000000000000000000000000000000000000000000401ff000000ff
# 0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000

if __name__ == '__main__':
    run_gui()
    # with closing(get_device()) as d:
    #     for i in range(0, 250, 10):
    #         data = build_output_data(
    #             # 0xff, 0xf7,
    #             flag1=OutputFlag1.LIGHTBAR_CONTROL_ENABLE,
    #             # flag2=OutputFlag2.LIGHTBAR_SETUP_CONTROL_ENABLE,
    #             lightbar_setup=LightbarSetup.LIGHT_ON,
    #             led_brightness=i,
    #             lightbar_red=i,
    #             lightbar_green=255 - i,
    #             lightbar_blue=128,
    #         )
    #         # data = build_output_data(0xff, 0xf7, motor_left=20, motor_right=0)
    #         print(data, end='')
    #         print('=', d.write(data))
    #         time.sleep(0.2)
