# ds5ctl

A GUI tool for configuring a DualSense 5 controller (currently only supports direct USB connection)

![Example of GUI](https://user-images.githubusercontent.com/33840/174457044-a3320871-bc76-4f20-9f62-ef854517712e.png)

![Example recording after sending to controller](https://user-images.githubusercontent.com/33840/174456917-81cdcd86-f37e-483c-976f-c6381d1b6469.gif)


# Usage

To run the GUI:

```shell
ds5ctl

# Or
python -m ds5ctl
```

To send commands to the controller, press the Send button at the bottom. This will emit all currently-configured controls. Though all sliders and controls are shown (such as Haptics Left/Right or Lightbar Colour), emitting them will have no effect on the controller unless the appropriate Control flags are also checked.

To send haptics to the device, ensure `DS5_MODE` Operating Mode is checked, and modify the Haptics sliders. The controller appears to spin the motors for 5 seconds before desisting automatically.

To change the adaptive trigger effects, ensure `DS5_MODE` Operating Mode is checked, as well as `TRIGGER_EFFECTS_RIGHT` and/or `TRIGGER_EFFECTS_LEFT` (depending on which sides you wish to modify), then using the trigger effects panes to modify the effect.
