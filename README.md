# Filament sensor simplified

This plugin reacts to filament sensor output. If triggered it issues M600 X0 Y0 command to printer.
It is based on Octoprint-Filament-Reloaded by kontakt but the logic behind is different.

This was only tested on my printer running Marlin 2.0.4.4 so sorry if any bugs present.

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/luckyx182/Filament_sensor_simplified/archive/master.zip

## Configuration

Configuration couldn't be simpler, all you need is to configure listening board pin (board mode) and if the switch is normally open or closed.

Default pin is -1 (not configured) and normally closed.
