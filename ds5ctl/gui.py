import logging
from contextlib import suppress
from enum import Enum, IntFlag
from typing import Any, Callable, Type

import dearpygui.dearpygui as dpg
import mopyx
from dearpygui.demo import _hsv_to_rgb

from . import hid
from .hid import (
    DualSenseHIDOutput,
    LightbarSetup,
    MuteButton,
    OperatingMode,
    LightEffectControl,
    LightbarControl,
    PhysicalEffectControl,
    PlayerLED,
    PowerSaveControl,
    TriggerEffect,
    build_output_data,
    get_device,
)

logger = logging.getLogger(__name__)


@mopyx.model
class ContinuousResistanceTriggerEffect(hid.ContinuousResistanceTriggerEffect):
    pass


@mopyx.model
class SectionResistanceTriggerEffect(hid.SectionResistanceTriggerEffect):
    pass


@mopyx.model
class VibratingTriggerEffect(hid.VibratingTriggerEffect):
    pass


@mopyx.model
class EffectExtendedTriggerEffect(hid.EffectExtendedTriggerEffect):
    pass


@mopyx.model
class CalibrateTriggerEffect(hid.CalibrateTriggerEffect):
    pass


@mopyx.model
class TriggerEffects:
    AVAILABLE_EFFECTS = [
        'continuous_resistance',
        'section_resistance',
        'vibrating',
        'effect_extended',
        'calibrate',
    ]

    def __init__(self):
        self.continuous_resistance = ContinuousResistanceTriggerEffect()
        self.section_resistance = SectionResistanceTriggerEffect()
        self.vibrating = VibratingTriggerEffect()
        self.effect_extended = EffectExtendedTriggerEffect()
        self.calibrate = CalibrateTriggerEffect()


@mopyx.model
class DualSenseHIDModel:
    def __init__(self):
        self.right_trigger_effects = TriggerEffects()
        self.selected_right_trigger_effect = 'continuous_resistance'
        self.left_trigger_effects = TriggerEffects()
        self.selected_left_trigger_effect = 'continuous_resistance'

        self.operating_mode: OperatingMode | int = OperatingMode.DS5_MODE
        self.light_effect_control: LightEffectControl | int = 0
        self.physical_effect_control: PhysicalEffectControl | int = 0
        self.motor_right: int = 0
        self.motor_left: int = 0
        self.unknown2: bytes = b''
        self.mute_button_led: MuteButton | int = 0
        self.power_save_control: PowerSaveControl | int = 0
        self.unknown3: bytes = b''
        self.lightbar_control: LightbarControl | int = 0
        self.lightbar_setup: LightbarSetup = LightbarSetup.LIGHT_ON
        self.led_brightness: int = 0
        self.player_leds: PlayerLED | int = 0
        self.lightbar_red: int = 0
        self.lightbar_green: int = 0
        self.lightbar_blue: int = 0

        self.last_num_bytes_written: int = 0
        self.device = get_device()

    @mopyx.computed
    def output_data(self) -> DualSenseHIDOutput:
        return build_output_data(
            operating_mode=self.operating_mode,
            physical_effect_control=self.physical_effect_control,
            light_effect_control=self.light_effect_control,
            motor_right=self.motor_right,
            motor_left=self.motor_left,
            unknown2=self.unknown2,
            mute_button_led=self.mute_button_led,
            power_save_control=self.power_save_control,
            right_trigger_effect=self.right_trigger_effect,
            left_trigger_effect=self.left_trigger_effect,
            unknown3=self.unknown3,
            lightbar_control=self.lightbar_control,
            lightbar_setup=self.lightbar_setup,
            led_brightness=self.led_brightness,
            player_leds=self.player_leds,
            lightbar_red=self.lightbar_red,
            lightbar_green=self.lightbar_green,
            lightbar_blue=self.lightbar_blue,
        )

    @mopyx.computed
    def right_trigger_effect(self) -> TriggerEffect:
        return getattr(self.right_trigger_effects, self.selected_right_trigger_effect)

    @mopyx.computed
    def left_trigger_effect(self) -> TriggerEffect:
        return getattr(self.left_trigger_effects, self.selected_left_trigger_effect)

    @mopyx.computed
    def output_data_bytes(self) -> bytes:
        return bytes(self.output_data)

    @mopyx.computed
    def output_data_len(self) -> int:
        return len(self.output_data_bytes)

    @mopyx.computed
    def hex_data(self) -> str:
        return self.output_data_bytes.hex()

    @mopyx.action
    def send(self):
        self.last_num_bytes_written = self.device.write(self.output_data_bytes)

    @mopyx.action
    def reconnect(self):
        try:
            self.device.close()
        except (IOError, OSError):
            logger.exception('Error closing device handle')

        self.device = get_device()


class DualSenseUI:
    def __init__(self):
        self.model = DualSenseHIDModel()

        self.init_ui()
        self.render()
        self.display()

    def init_ui(self):
        dpg.create_context()
        dpg.create_viewport(title='DualSense Controller', width=1024, height=1024)

        self.init_themes()
        self.init_widgets()

    def init_themes(self):
        _add_button_theme('primary', 4/7)
        _add_button_theme('secondary', 5/7)
        _add_button_theme('danger', 0)

    def init_widgets(self):
        with dpg.window(tag='DualSense Controller'):
            dpg.set_primary_window('DualSense Controller', True)

            with dpg.group(horizontal=True):
                dpg.add_input_text(tag='hex_data', width=940)
                dpg.add_text(tag='hex_data_length')

            self._add_flag_group('Operating Mode', 'operating_mode', OperatingMode)
            self._add_flag_group('Physical Effect Control', 'physical_effect_control', PhysicalEffectControl)
            self._add_flag_group('Light Effect Control', 'light_effect_control', LightEffectControl)

            with (
                dpg.collapsing_header(label='Haptics', default_open=True),
                dpg.group(),
            ):
                self._add_byte_slider('Haptics Left', 'motor_left')
                self._add_byte_slider('Haptics Right', 'motor_right')

            self._add_radio_group('Mute Button LED', 'mute_button_led', MuteButton)

            self._add_flag_group('Power Save Control', 'power_save_control', PowerSaveControl)

            with (
                dpg.collapsing_header(label='Trigger Effects', default_open=True),
                dpg.group(horizontal=True, horizontal_spacing=30),
            ):
                for side in 'left', 'right':
                    with dpg.group(width=400):  # TODO(zk): dynamic width w/o cutting off edges
                        dpg.add_text(side.capitalize())
                        dpg.add_combo(
                            items=TriggerEffects.AVAILABLE_EFFECTS,
                            label='Type',
                            **self._bind(f'selected_{side}_trigger_effect')
                        )

                        trigger_effects: TriggerEffects = getattr(self.model, f'{side}_trigger_effects')

                        with dpg.group(show=False, tag=f'{side}_trigger_effect_continuous_resistance'):
                            model = trigger_effects.continuous_resistance
                            self._add_byte_slider('Start Pos', 'start_pos', model=model)
                            self._add_byte_slider('Force', 'force', model=model)

                        with dpg.group(show=False, tag=f'{side}_trigger_effect_section_resistance'):
                            model = trigger_effects.section_resistance
                            self._add_byte_slider('Start Pos', 'start_pos', model=model)
                            self._add_byte_slider('Force', 'force', model=model)

                        with dpg.group(show=False, tag=f'{side}_trigger_effect_vibrating'):
                            model = trigger_effects.vibrating
                            self._add_byte_slider('Frequency', 'frequency', model=model)
                            self._add_byte_slider('Off Time', 'off_time', model=model)

                        with dpg.group(show=False, tag=f'{side}_trigger_effect_effect_extended'):
                            model = trigger_effects.effect_extended
                            self._add_byte_slider('Start Pos', 'start_pos', model=model)
                            dpg.add_checkbox(label='Keep Effect', **self._bind('keep_effect', model=model))
                            self._add_byte_slider('Begin Force', 'begin_force', model=model)
                            self._add_byte_slider('Middle Force', 'middle_force', model=model)
                            self._add_byte_slider('End Force', 'end_force', model=model)
                            self._add_byte_slider('Frequency', 'frequency', model=model)

                        with dpg.group(show=False, tag=f'{side}_trigger_effect_calibrate'):
                            pass

            self._add_flag_group('Lightbar Control', 'lightbar_control', LightbarControl)

            self._add_radio_group('Lightbar Setup', 'lightbar_setup', LightbarSetup)
            self._add_byte_slider('LED Brightness', 'led_brightness')
            self._add_flag_group('Player LEDS', 'player_leds', PlayerLED)

            with dpg.collapsing_header(label='Lightbar Colour', default_open=True):
                self._add_byte_slider('Red', 'lightbar_red')
                self._add_byte_slider('Green', 'lightbar_green')
                self._add_byte_slider('Blue', 'lightbar_blue')

            with dpg.group(horizontal=True):
                dpg.add_button(label='Send', callback=self.model.send, tag='send')
                dpg.bind_item_theme(dpg.last_item(), 'primary')

                dpg.add_button(label='Reconnect', callback=self.model.reconnect, tag='reconnect')
                dpg.bind_item_theme(dpg.last_item(), 'danger')

    @mopyx.render
    def render(self):
        mopyx.render_call(lambda: dpg.set_value('hex_data', self.model.hex_data))
        mopyx.render_call(lambda: dpg.set_value('hex_data_length', self.model.output_data_len))
        self.show_trigger_effect_config()

    @mopyx.render
    def show_trigger_effect_config(self):
        for side in 'left', 'right':
            selected = getattr(self.model, f'selected_{side}_trigger_effect')
            for effect in TriggerEffects.AVAILABLE_EFFECTS:
                tag = f'{side}_trigger_effect_{effect}'
                if effect == selected:
                    dpg.show_item(tag)
                else:
                    dpg.hide_item(tag)

    def display(self):
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

    def _bind(
        self,
        param_info: str | Any,
        getter: Callable[[object, str], Any] = getattr,
        setter: Callable[[object, str, Any], None] = setattr,
        model: object | None = None,
    ) -> dict[str, Any]:
        if model is None:
            model = self.model

        setter = mopyx.action(setter)

        def on_change(sender, value):
            setter(model, param_info, value)

        return {
            'default_value': getter(model, param_info),
            'callback': on_change,
        }

    def _add_flag_group(
        self, label: str, param: str, flag_cls: Type[IntFlag], *, model: object | None = None
    ):
        def get_value(model, param_flag_info):
            param, flag = param_flag_info

            current_value = getattr(model, param)
            return current_value & flag > 0

        def set_value(model, param_flag_info, is_checked):
            param, flag = param_flag_info

            value = getattr(model, param)
            if is_checked:
                value |= flag
            else:
                value &= ~flag

            logger.debug(f'{"Adding" if is_checked else "Removing"} {flag} {"to" if is_checked else "from"} {is_checked}')
            setattr(model, param, value)

        with dpg.collapsing_header(label=label, default_open=True):
            for flag in flag_cls:
                dpg.add_checkbox(
                    label=f'{flag.name} ({flag.value} = {flag.value:08b})',
                    **self._bind((param, flag), get_value, set_value, model=model),
                )

    def _add_radio_group(
        self, label: str, param: str, options: Type[Enum], *, model: object | None = None
    ):
        label_values = {
            f'{flag.name} ({flag.value} = {flag.value:08b})': flag.value
            for flag in options
        }
        value_labels = {v: k for k, v in label_values.items()}

        def get_value(model, param):
            current_value = getattr(model, param)
            return value_labels.get(current_value)

        def set_value(model, param, item):
            value = label_values[item]
            setattr(model, param, value)

        with dpg.collapsing_header(label=label, default_open=True):
            dpg.add_radio_button(
                items=list(label_values),
                label=label,
                tag=param,
                **self._bind(param, get_value, set_value, model=model)
            )

    def _add_byte_slider(self, label: str, param: str, *, model: object | None = None):
        dpg.add_slider_int(label=label, min_value=0, max_value=255, **self._bind(param, model=model))


def _add_button_theme(tag: str, base_hue: float, *, rounding: int = 1, padding: int = 12):
    with dpg.theme(tag=tag), dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, _hsv_to_rgb(base_hue, 0.6, 0.6))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, _hsv_to_rgb(base_hue, 0.8, 0.8))
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, _hsv_to_rgb(base_hue, 0.7, 0.7))
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, rounding)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, padding, padding)


def run_gui():
    DualSenseUI()


def run_gui_old():
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

            _add_flag_group('Flag0', 'operating_mode', OperatingMode)
            _add_flag_group('Flag3', 'physical_effect_control', PhysicalEffectControl)
            _add_flag_group('Flag1', 'light_effect_control', LightEffectControl)

            with (
                dpg.collapsing_header(label='Rumble', default_open=True),
                dpg.group(),
            ):
                _add_byte_slider('Rumble Left', 'motor_left')
                _add_byte_slider('Rumble Right', 'motor_right')

            _add_radio_group('Mute Button LED', 'mute_button_led', MuteButton)

            _add_flag_group('Power Save Control', 'power_save_control', PowerSaveControl)

            # TODO: trigger effects

            _add_flag_group('Flag2', 'lightbar_control', LightbarControl)

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
