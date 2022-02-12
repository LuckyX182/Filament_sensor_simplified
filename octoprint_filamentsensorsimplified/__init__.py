# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import re
from octoprint.events import Events
from time import sleep
import RPi.GPIO as GPIO
import flask


class Filament_sensor_simplifiedPlugin(octoprint.plugin.StartupPlugin,
                                       octoprint.plugin.EventHandlerPlugin,
                                       octoprint.plugin.TemplatePlugin,
                                       octoprint.plugin.SettingsPlugin,
                                       octoprint.plugin.SimpleApiPlugin,
                                       octoprint.plugin.BlueprintPlugin,
                                       octoprint.plugin.AssetPlugin):
    # bounce time for sensing
    bounce_time = 250

    # default gcode
    default_gcode = 'M600 X0 Y0'

    # gpio mode disabled
    gpio_mode_disabled = False

    # printing flag
    printing = False

    gpio_initialized = False

    def initialize(self):
        GPIO.setwarnings(True)
        # flag defining that the filament change command has been sent to printer, this does not however mean that
        # filament change sequence has been started
        self.changing_filament_initiated = False
        # flag defining that the filament change sequence has been started and the M600 command has been se to printer
        self.changing_filament_command_sent = False
        # flag defining that the filament change sequence has been started and the printer is waiting for user
        # to put in new filament
        self.paused_for_user = False
        # flag to prevent double detection
        self.changing_filament_started = False

    @property
    def setting_gpio_mode(self):
        return int(self._settings.get(["gpio_mode"]))

    @property
    def setting_pin(self):
        return int(self._settings.get(["pin"]))

    @property
    def setting_power(self):
        return int(self._settings.get(["power"]))

    @property
    def setting_gcode(self):
        return self._settings.get(["g_code"])

    @property
    def setting_triggered(self):
        return int(self._settings.get(["triggered"]))

    @property
    def setting_cmd_action(self):
        return int(self._settings.get(["cmd_action"]))

    # AssetPlugin hook
    def get_assets(self):
        return dict(js=["js/filamentsensorsimplified.js"], css=["css/filamentsensorsimplified.css"])

    # Template hooks
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    # Settings hook
    def get_settings_defaults(self):
        return dict(
            gpio_mode=10,
            pin=0,  # Default is 0
            power=0,
            g_code=self.default_gcode,
            triggered=0,
            cmd_action=0
        )

    # simpleApiPlugin
    def get_api_commands(self):
        return dict(testSensor=["pin", "power"])

    @octoprint.plugin.BlueprintPlugin.route("/disable", methods=["GET"])
    def get_disable(self):
        self._logger.debug("getting gpio disabled by other plugins info")
        gpio_mode_disabled = self.gpio_mode_disabled
        return flask.jsonify(gpio_mode_disabled=gpio_mode_disabled, printing=self.printing)

    # test pin value, power pin or if its used by someone else
    def on_api_command(self, command, data):
        try:
            selected_power = int(data.get("power"))
            selected_pin = int(data.get("pin"))
            mode = int(data.get("mode"))
            triggered_mode = int(data.get("triggered"))

            if selected_pin is 0:
                return "", 556

            self.init_gpio(mode, selected_pin, selected_power, triggered_mode, True)
            triggered_int = self.is_filament_present(selected_pin, selected_power, triggered_mode)
            self.init_gpio(self.setting_gpio_mode, self.setting_pin, self.setting_power, self.setting_triggered, True)
            return flask.jsonify(triggered=triggered_int)
        except ValueError as e:
            self._logger.error(str(e))
            # ValueError occurs when reading from power, ground or out of range pins
            return "", 556

    def is_filament_present(self, pin, power, triggered_mode):
        if self.read_sensor_multiple(pin, power, triggered_mode):
            self._logger.info("Filament detected")
            return 0
        else:
            self._logger.info("Filament not detected")
            return 1

    def show_printer_runout_popup(self):
        self._plugin_manager.send_plugin_message(self._identifier,
                                                 dict(type="error", autoClose=False, msg="Printer ran out of filament!"))

    def send_out_of_filament(self):
        self.show_printer_runout_popup()
        if self.setting_cmd_action is 0:
            self._logger.info("Sending out of filament GCODE: %s" % (self.setting_gcode))
            self._printer.commands(self.setting_gcode)
            self.changing_filament_initiated = True
        elif self.setting_cmd_action is 1:
            self._logger.info("Pausing print using OctoPrint native pause")
            self._printer.commands('G1 X0 Y0')
            self._printer.pause_print()

    def sensor_callback(self, _):
        self._logger.info("Sensor callback called")
        filamentPresentInt = self.is_filament_present(self.setting_pin, self.setting_power, self.setting_triggered)
        if filamentPresentInt is 1:
            self._logger.info("Sensor was triggered")
            if not self.changing_filament_initiated and self.printing:
                self.send_out_of_filament()
            # change navbar icon to filament runout
            self._plugin_manager.send_plugin_message(self._identifier, dict(type="filamentStatus", noFilament=True,
                                                                            msg="Printer ran out of filament!"))
        elif filamentPresentInt is 0:
            self._logger.info("Sensor was not triggered")
            # change navbar icon to filament present
            self._plugin_manager.send_plugin_message(self._identifier, dict(type="filamentStatus", noFilament=False,
                                                                            msg="Filament inserted!"))

    def init_gpio(self, gpio_mode, pin, power, trigger_mode, test):
        self._logger.info("Initializing GPIO.")
        preset_gpio_mode = GPIO.getmode()
        if preset_gpio_mode is not None:
            self.gpio_mode_disabled = True
            gpio_mode = preset_gpio_mode
            self._settings.set(["gpio_mode"], preset_gpio_mode)
        else:
            self._logger.info("Preset mode is %s" % preset_gpio_mode)

        # Fix old -1 settings to 0
        if pin is -1:
            self._logger.debug("Fixing old settings from -1 to 0")
            self._settings.set(["pin"], 0)

        if self.plugin_enabled(pin):
            self._logger.info("Enabling filament sensor.")
            self._logger.info("Mode is %s" % gpio_mode)
            # BOARD
            if gpio_mode is 10:
                # if mode set by 3rd party don't set it again
                if not self.gpio_mode_disabled:
                    self._logger.info("Setting Board mode")
                    GPIO.cleanup()
                    GPIO.setmode(GPIO.BOARD)
                # first check pins not in use already
                usage = GPIO.gpio_function(pin)
                self._logger.debug("usage on pin %s is %s" % (pin, usage))
                # 1 = input
                if usage is not 1:
                    # 555 is not http specific so I chose it
                    return "", 555
            # BCM
            elif gpio_mode is 11:
                # BCM range 1-27
                if pin > 27:
                    return "", 556
                # if mode set by 3rd party don't set it again
                if not self.gpio_mode_disabled:
                    self._logger.debug("Setting BCM mode")
                    GPIO.cleanup()
                    GPIO.setmode(GPIO.BCM)
            if not test:
                try:
                    # 0 = sensor is grounded, react to rising edge pulled up by pull up resistor
                    if power is 0:
                        self.pull_resistor(pin, power)
                        # triggered when open
                        if trigger_mode is 0:
                            self._logger.debug("Reacting to rising edge")
                            GPIO.add_event_detect(
                                pin, GPIO.RISING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time)
                        # triggered when closed
                        else:
                            self._logger.debug("Reacting to falling edge")
                            GPIO.add_event_detect(
                                pin, GPIO.FALLING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time)

                    # 1 = sensor is powered, react to falling edge pulled down by pull down resistor
                    else:
                        self.pull_resistor(pin, power)
                        # triggered when open
                        if trigger_mode is 0:
                            self._logger.debug("Reacting to falling edge")
                            GPIO.add_event_detect(
                                pin, GPIO.FALLING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time)
                        # triggered when closed
                        else:
                            self._logger.debug("Reacting to rising edge")
                            GPIO.add_event_detect(
                                pin, GPIO.RISING,
                                callback=self.sensor_callback,
                                bouncetime=self.bounce_time)
                except RuntimeError as e:
                    self._logger.warn(str(e))
        else:
            self._logger.info("Sensor disabled")

    # pulls resistor up or down based on the parameters
    def pull_resistor(self, pin, power):
        if power is 0:
            self._logger.debug("Pulling up resistor")
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        elif power is 1:
            self._logger.debug("Pulling down resistor")
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        self._logger.debug("Done")

    def on_after_startup(self):
        self._logger.info("Filament Sensor Simplified started")
        self.init_gpio(self.setting_gpio_mode, self.setting_pin, self.setting_power, self.setting_triggered, False)
        self.gpio_initialized = True

    def on_settings_save(self, data):
        # Retrieve any settings not changed in order to validate that the combination of new and old settings end up in a bad combination
        self._logger.info("Saving settings for Filament Sensor Simplified")
        pin_to_save = self._settings.get_int(["pin"])
        gpio_mode_to_save = self._settings.get_int(["gpio_mode"])
        power_to_save = self._settings.get_int(["power"])
        trigger_mode_to_save = self._settings.get_int(["triggered"])

        if "pin" in data:
            pin_to_save = int(data.get("pin"))

        if "gpio_mode" in data:
            gpio_mode_to_save = int(data.get("gpio_mode"))

        if "power" in data:
            power_to_save = int(data.get("power"))

        if "trigger" in data:
            trigger_mode_to_save = int(data.get("triggered"))

        if pin_to_save is not None:
            # check if pin is not power/ground pin or out of range but allow the disabled value (0)
            if pin_to_save is not 0:
                try:
                    # BOARD
                    if gpio_mode_to_save is 10:
                        # before saving check if pin not used by others
                        usage = GPIO.gpio_function(pin_to_save)
                        self._logger.debug("usage on pin %s is %s" % (pin_to_save, usage))
                        if usage is not 1:
                            self._logger.info(
                                "You are trying to save pin %s which is already used by others" % (pin_to_save))
                            self._plugin_manager.send_plugin_message(self._identifier,
                                                                     dict(type="error", autoClose=True,
                                                                          msg="Filament sensor settings not saved, you are trying to use a pin which is already used by others"))
                            return
                    # BCM
                    elif gpio_mode_to_save is 11:
                        if pin_to_save > 27:
                            self._logger.info(
                                "You are trying to save pin %s which is out of range" % (pin_to_save))
                            self._plugin_manager.send_plugin_message(self._identifier,
                                                                     dict(type="error", autoClose=True,
                                                                          msg="Filament sensor settings not saved, you are trying to use a pin which is out of range"))
                            return

                except ValueError:
                    self._logger.info(
                        "You are trying to save pin %s which is ground/power pin or out of range" % (pin_to_save))
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True,
                                                                                    msg="Filament sensor settings not saved, you are trying to use a pin which is ground/power pin or out of range"))
                    return
                self.init_gpio(gpio_mode_to_save, pin_to_save, power_to_save, trigger_mode_to_save, False)
                self.init_icon(pin_to_save, power_to_save, trigger_mode_to_save)
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

    def sending_gcode(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
        if self.changing_filament_initiated:
            if self.changing_filament_command_sent and self.changing_filament_started:
                # M113 - host keepalive message, ignore this message
                if not re.search("^M113", cmd):
                    self._logger.debug("filament change sequence ended")
                    self.changing_filament_initiated = False
                    self.changing_filament_command_sent = False
                    self.changing_filament_started = False
                    if not self.read_sensor_multiple(self.setting_pin, self.setting_power, self.setting_triggered):
                        self._logger.debug("reading sensor after change")
                        self.send_out_of_filament()
            if cmd == self.setting_gcode:
                self._logger.debug("about to send out of filament g-code")
                self.changing_filament_command_sent = True

        # deliberate change
        if re.search("^M600", cmd):
            self._logger.info("deliberate M600 was initiated")
            self.changing_filament_initiated = True
            self.changing_filament_command_sent = True

    def gcode_response_received(self, comm, line, *args, **kwargs):
        if self.changing_filament_command_sent:
            if re.search("busy: paused for user", line):
                self._logger.debug("received busy paused for user")
                if not self.paused_for_user:
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False,
                                                                                    msg="Filament change: printer is waiting for user input."))
                    self.paused_for_user = True
                    self.changing_filament_started = True
            elif re.search("echo:busy: processing", line):
                self._logger.debug("received busy processing")
                if self.paused_for_user:
                    self.paused_for_user = False
        return line

    def init_icon(self, pin, power, triggered):
        if not self.gpio_initialized:
            return
        self._logger.info("Setting icon status")
        iconPresent = self.is_filament_present(pin, power, triggered)
        self._plugin_manager.send_plugin_message(self._identifier,
                                                 dict(type="filamentStatus", noFilament=iconPresent,
                                                      msg="Initial filament read"))

    def read_sensor_multiple(self, pin, power, trigger_mode):
        self._logger.info("Reading sensor values")
        oldTrigger = self.read_sensor(pin, power, trigger_mode)
        readFinished = False
        newTrigger = False

        # take a reading of 10 consecutive reads to prevent false positives
        while not readFinished:
            for x in range(0, 10):
                sleep(0.2)
                newTrigger = self.read_sensor(pin, power, trigger_mode)
                if oldTrigger != newTrigger:
                    self._logger.info("Repeating sensor read due to false positives")
                    break
                oldTrigger = newTrigger
            readFinished = True

        return newTrigger

    # plugin disabled if pin set to 0
    def plugin_enabled(self, pin):
        return pin != 0

    # read sensor input value
    def read_sensor(self, pin, power, trigger_mode):
        self._logger.debug("reading pin %s " % pin)
        self.pull_resistor(pin, power)
        pin_value = GPIO.input(pin)
        return (pin_value + power + trigger_mode) % 2 is 0

    def on_event(self, event, payload):
        # if user has logged in show appropriate popup
        if event is Events.CLIENT_OPENED:
            # if plugin enabled init icon on client open
            if self.plugin_enabled(self.setting_pin):
                self.init_icon(self.setting_pin, self.setting_power, self.setting_triggered)
            if self.changing_filament_initiated and not self.changing_filament_command_sent:
                self.show_printer_runout_popup()
            elif self.changing_filament_command_sent and not self.paused_for_user:
                self.show_printer_runout_popup()
            # printer is waiting for user to put in new filament
            elif self.changing_filament_command_sent and self.paused_for_user:
                self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False,
                                                                                msg="Printer ran out of filament! It's waiting for user input"))
            # if the plugin hasn't been initialized
            if not self.plugin_enabled(self.setting_pin):
                self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True,
                                                                                msg="Don't forget to configure this plugin."))

        elif event in (Events.PRINT_STARTED, Events.PRINT_RESUMED):
            self.changing_filament_initiated = False
            self.changing_filament_command_sent = False
            self.paused_for_user = False
            self.printing = True

            # print started with no filament present
            if event is Events.PRINT_STARTED and self.plugin_enabled(self.setting_pin):
                self._logger.info("Starting print.")
                if not self.read_sensor_multiple(self.setting_pin, self.setting_power, self.setting_triggered):
                    self._logger.info("Printing aborted: no filament detected!")
                    self._printer.cancel_print()
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True,
                                                                                    msg="No filament detected! Print cancelled."))
            # print resumed with no filament present
            elif event is Events.PRINT_RESUMED and self.plugin_enabled(self.setting_pin):
                self._logger.info("Resuming print.")
                if not self.read_sensor_multiple(self.setting_pin, self.setting_power, self.setting_triggered):
                    self._logger.info("Resuming print aborted: no filament detected!")
                    self.send_out_of_filament()
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True,
                                                                                    msg="Resuming print aborted: no filament detected!"))

        elif event in (Events.PRINT_DONE,
                Events.PRINT_FAILED,
                Events.PRINT_CANCELLED,
                Events.ERROR):
            self.changing_filament_initiated = False
            self.changing_filament_command_sent = False
            self.paused_for_user = False
            self.printing = False

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return dict(
            filamentsensorsimplified=dict(
                displayName="Filament sensor simplified",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="luckyx182",
                repo="Filament_sensor_simplified",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/luckyx182/Filament_sensor_simplified/archive/{target_version}.zip"
            )
        )


# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
# __plugin_pythoncompat__ = ">=2.7,<3" # only python 2
# __plugin_pythoncompat__ = ">=3,<4" # only python 3
__plugin_pythoncompat__ = ">=2.7,<4"  # python 2 and 3

__plugin_name__ = "Filament Sensor Simplified"
__plugin_version__ = "0.3.0"


def __plugin_check__():
    try:
        import RPi.GPIO as GPIO
        if GPIO.VERSION < "0.6":  # Need at least 0.6 for edge detection
            return False
    except ImportError:
        return False
    return True


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Filament_sensor_simplifiedPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.received": __plugin_implementation__.gcode_response_received,
        "octoprint.comm.protocol.gcode.sending": __plugin_implementation__.sending_gcode
    }
