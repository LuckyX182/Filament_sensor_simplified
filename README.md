# Filament sensor simplified

This plugin reacts to short lever microswitch output like [this](https://chinadaier.en.made-in-china.com/product/ABVJkvyMAqcT/China-1A-125VAC-on-off-Kw10-Mini-Micro-Mouse-Switch.html)
If triggered it issues configured command to printer.

Let's check some features:
* pop-up notification when printer runs out of filament
* very handy pop-up when printer requires user input while changing filament
* test button so you know if your sensor really works or not
* filament check at the start of the print - if no filament present it won't start printing, again pop-up will appear
* filament check at the end of filament change - just to be sure you won't start printing with no filament
* check if printer supports M600 when printer connected and gcode starts with M600 - if not user will be notified through pop-up
* info pop-up when plugin hasn't been configured
* filament runouts can be repeatable which didn't work with other plugins I tried
* user-friendly and easy to configure
* pin validation so you don't accidentally save wrong pin number
* detection of used GPIO mode - this makes it compatible with other plugins
* runs on OctoPrint 1.3.0 and higher

Configurable fields:
* mode - BOARD/BCM
* pin number
* gcode sent on filament runout
* sensor power input
* trigger mode

**NOTE: this plugin won't work if you use OctoPrint only to start printing from SD card**

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/luckyx182/Filament_sensor_simplified/archive/master.zip

## Configuration

Configuration couldn't be simpler, all you need is to configure listening board pin (board mode) and if the second switch terminal is connected to ground or 3.3V.

Default pin is -1 (not configured) and ground (as it is safer, read below).

**WARNING! Never connect the switch input to 5V as it could fry the GPIO section of your Raspberry!**

**WARNING! When using test button on input pin used by other application it will reset internal pull up/down resistor**

#### Advice

You might experience the same problem as I experienced - the sensor was randomly triggered. Turns out that if running sensor wires along motor wires, it was enough to interfere with sensor reading.

To solve this connect a shielded wire to your sensor and ground the shielding, ideally on both ends.

If you are unsure about your sensor being triggered, check [OctoPrint logs](https://community.octoprint.org/t/where-can-i-find-octoprints-and-octopis-log-files/299)

## Support me

This plugin was developed in my spare time.
If you find it useful and like it, you can support me by clicking the button below :)

[![More coffee, more code](https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=5L758LYSUGHW4&source=url)

## Screenshots

Plugin settings:
![plugin_settings](screenshots/settings.png "Plugin settings")

No configuration pop-up:
![no_config_pop-up](screenshots/no_conf_popup.png "No configuration pop-up")

Pop-up for M600 disabled:
![M600_not_enabled](screenshots/M600_disabled.png "M600 not enabled pop-up")

No filament when starting print pop-up:
![start_no_filament_popup](screenshots/no_filament.png "Start with no filament pop-up")

Filament runout pop-up:
![no_filament_popup](screenshots/filament_runout.png "No filament pop-up")

Waiting for user input pop-up:
![user_input_popup](screenshots/waiting_for_user_input.png "User input required pop-up")
