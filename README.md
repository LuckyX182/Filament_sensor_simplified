## Please note:

This is a fork of the [original Filament Sensor Simplified plugin.](https://github.com/LuckyX182/Filament_sensor_simplified)

# Filament sensor simplified

This plugin reacts to short lever microswitch output like [this](https://chinadaier.en.made-in-china.com/product/ABVJkvyMAqcT/China-1A-125VAC-on-off-Kw10-Mini-Micro-Mouse-Switch.html)
If triggered it issues configured command to printer.

Let's check some features:
* pop-up notification when printer runs out of filament
* very handy pop-up when printer requires user input while changing filament
* test button so you know if your sensor really works or not
* filament check at the start of the print - if no filament present it won't start printing, again pop-up will appear
* filament check at the end of filament change - just to be sure you won't start printing with no filament
* navbar icon where you can immediately see if the filament's in
* info pop-up when plugin hasn't been configured
* filament runouts can be repeatable
* user-friendly and easy to configure
* pin validation so you don't accidentally save wrong pin number
* detection of used GPIO mode - this makes it compatible with other plugins
* handles delibrate M600 filament change
* if your printer doesn't support M600 you have option to use Octoprint pause
* runs on OctoPrint 1.3.0 and higher

**NOTE: this plugin won't work if you use OctoPrint only to start printing from SD card**

## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/luckyx182/Filament_sensor_simplified/archive/master.zip

## Configuration

Configuration consists of these parameters:
1. **Board mode** - Physical/BOARD or GPIO/BCM mode, **Physical/BOARD mode** - referring to the pins by the number, **GPIO/BCM mode** - referring to the pins
by the "Broadcom SOC channel", if this is selected by 3rd party, this option will be disabled with note on GUI
2. **pin number** - pin number based on selected mode
3. **power input to sensor** - input is connected to **ground or 3.3 V**
4. **switch type** - switch should be **triggered when opened** (input of the sensor doesn't transfer to its output) or **triggered when closed** (input of the sensor is transferred to its output)
5. **runout action** - choose whether you want to **send G-code** to printer or use **Octoprint pause** on filament runout
5. **g-code** to send to printer on filament runout / before OctoPrint pause - default is M600 X0 Y0

Default pin is 0 (not configured) and ground (as it is safer, read below).

After configuring it is best to restart Octoprint and dry-run to check if the filament change works correctly to avoid any problems.

**WARNING! Never connect the switch input to 5V as it could fry the GPIO section of your Raspberry!**

#### Advice

You might experience the same problem as I experienced - the sensor was randomly triggered. Turns out that if running sensor wires along motor wires, it was enough to interfere with sensor reading.

To solve this connect a shielded wire to your sensor and ground the shielding, ideally on both ends.

If you are unsure about your sensor being triggered, check [OctoPrint logs](https://community.octoprint.org/t/where-can-i-find-octoprints-and-octopis-log-files/299)

## Screenshots

Plugin settings:
![plugin_settings](screenshots/settings.png "Plugin settings")

Navbar icons:
![plugin_settings](screenshots/navbar-icon1.png "Plugin settings")
![plugin_settings](screenshots/navbar-icon2.png "Plugin settings")

No configuration pop-up:
![no_config_pop-up](screenshots/no_conf_popup.png "No configuration pop-up")

No filament when starting print pop-up:
![start_no_filament_popup](screenshots/no_filament.png "Start with no filament pop-up")

Filament runout pop-up:
![no_filament_popup](screenshots/filament_runout.png "No filament pop-up")

Waiting for user input pop-up:
![user_input_popup](screenshots/waiting_for_user_input.png "User input required pop-up")

## Maintainers wanted

As I don't have much time for this plugin anymore any help on maintaining the plugin will be greatly appreciated. I will only do basic maintenance.
