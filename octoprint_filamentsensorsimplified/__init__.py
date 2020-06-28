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
                                       octoprint.plugin.AssetPlugin):

    def initialize(self):
        GPIO.setwarnings(True)
        self.checkingM600 = False
        self.m600Enabled = True
        self.changing_filament_initiated = False
        self.changing_filament_started = False
        self.paused_for_user = False

    @property
    def pin(self):
        return int(self._settings.get(["pin"]))

    @property
    def switch(self):
        return int(self._settings.get(["switch"]))

    # AssetPlugin hook
    def get_assets(self):
        return dict(js=["js/filamentsensorsimplified.js"], css=["css/filamentsensorsimplified.css"])

    # Template hooks
    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    # Settings hook
    def get_settings_defaults(self):
        return dict(
            pin=-1,  # Default is -1
            switch=0
        )

    # simpleApiPlugin
    def get_api_commands(self):
        return dict(testSensor=["pin", "power"])

    def on_api_command(self, command, data):
        try:
            selected_power = int(data.get("power"))
            selected_pin = int(data.get("pin"))
            GPIO.setmode(GPIO.BCM)
            # first check pins not in use already
            usage = GPIO.gpio_function(selected_pin)
            self._logger.debug("usage on pin %s is %s" % (selected_pin, usage))
            # 1 = input
            if usage is not 1:
                # 555 is not http specific so I chose it
                return "", 555
            # before read don't let the pin float
            if selected_power is 0:
                GPIO.setup(selected_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(selected_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            pin_value = GPIO.input(selected_pin)
            # reset input to pull down after read
            GPIO.cleanup(selected_pin)
            triggered_bool = pin_value is selected_power
            return flask.jsonify(triggered=triggered_bool)
        except ValueError:
            # ValueError occurs when reading from power or ground pins
            return "", 556

    def on_after_startup(self):
        self._logger.info("Filament Sensor Simplified started")
        self._setup_sensor()

    def on_settings_save(self, data):
        if data.get("pin") is not None:
            pin_to_save = int(data.get("pin"))

            # check if pin is not power/ground pin or out of range but allow -1
            if pin_to_save is not -1:
                try:
                    # before saving check if pin not used by others
                    usage = GPIO.gpio_function(pin_to_save)
                    self._logger.debug("usage on pin %s is %s" % (pin_to_save, usage))
                    if usage is not 1:
                        self._logger.info("You are trying to save pin %s which is already used by others" % (pin_to_save))
                        self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True,
                                                                                        msg="Settings not saved, you are trying to save pin which is already used by others"))
                        return
                    GPIO.setup(pin_to_save, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    GPIO.input(pin_to_save)
                    GPIO.cleanup(pin_to_save)
                except ValueError:
                    self._logger.info("You are trying to save pin %s which is ground/power pin or out of range" % (pin_to_save))
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True, msg="Settings not saved, you are trying to save pin which is ground/power pin or out of range"))
                    return
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._setup_sensor()

    def _setup_sensor(self):
        if self.sensor_enabled():
            self._logger.info("Setting up sensor using BCM mode.")
            GPIO.setmode(GPIO.BCM)
            self._logger.info("Filament Sensor active on GPIO Pin [%s]" % self.pin)
            if self.switch is 0:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        else:
            self._logger.info("Pin not configured, won't work unless configured!")

    def checkM600Enabled(self):
        sleep(1)
        self.checkingM600 = True
        self._printer.commands("M603")

    def sending_gcode(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
        if self.changing_filament_initiated and self.m600Enabled:
            if self.changing_filament_started:
                if not re.search("^M113", cmd):
                    self.changing_filament_initiated = False
                    self.changing_filament_started = False
                    if self.no_filament():
                        self.send_out_of_filament()
            if cmd == "M600":
                self.changing_filament_started = True

    def gcode_response_received(self, comm, line, *args, **kwargs):
        if self.m600Enabled:

            if self.changing_filament_started:
                if re.search("busy: paused for user", line):
                    self._logger.debug("received busy paused for user")
                    if not self.paused_for_user:
                        self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False, msg="Filament change: printer is waiting for user input."))
                        self.paused_for_user = True
                elif re.search("echo:busy: processing", line):
                    self._logger.debug("received busy processing")
                    if self.paused_for_user:
                        self.paused_for_user = False

            if self.checkingM600:
                if re.search("^ok", line):
                    self._logger.debug("Printer supports M600")
                    self.m600Enabled = True
                    self.checkingM600 = False
                elif re.search("^echo:Unknown command: \"M603\"", line):
                    self._logger.debug("Printer doesn't support M600")
                    self.m600Enabled = False
                    self.checkingM600 = False
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True, msg="M600 gcode command is not enabled on this printer! This plugin won't work."))
                else:
                    self._logger.debug("M600 check unsuccessful, trying again")
                    self.checkM600Enabled()
        return line

    def sensor_enabled(self):
        return self.pin != -1

    def no_filament(self):
        return GPIO.input(self.pin) != self.switch

    def on_event(self, event, payload):
        if event is Events.CONNECTED:
            self.checkM600Enabled()
        elif event is Events.DISCONNECTED:
            self.m600Enabled = True

        if event is Events.CLIENT_OPENED:
            if self.changing_filament_initiated and not self.changing_filament_started:
                self.show_printer_runout_popup()
            if self.changing_filament_started and not self.paused_for_user:
                self.show_printer_runout_popup()
            if self.changing_filament_started and self.paused_for_user:
                self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False, msg="Printer ran out of filament! It's waiting for user input"))

        if not self.sensor_enabled():
            if event is Events.CLIENT_OPENED:
                self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True, msg="Don't forget to configure this plugin."))
            elif event is Events.PRINT_STARTED:
                self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True, msg="You may have forgotten to configure this plugin."))
        elif event is Events.PRINT_STARTED and self.no_filament():
            self._logger.info("Printing aborted: no filament detected!")
            self._printer.cancel_print()
            self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", autoClose=True, msg="No filament detected! Print cancelled."))
        if self.m600Enabled:
            # Enable sensor
            if event in (
                    Events.PRINT_STARTED,
                    Events.PRINT_RESUMED
            ):
                self._logger.info("%s: Enabling filament sensor." % (event))
                if self.sensor_enabled():
                    self.print_head_parking = False
                    self.print_head_parked = False
                    GPIO.remove_event_detect(self.pin)
                    if self.switch is 0:
                        GPIO.add_event_detect(
                            self.pin, GPIO.RISING,
                            callback=self.sensor_callback_high,
                            bouncetime=40000
                        )
                    else:
                        GPIO.add_event_detect(
                            self.pin, GPIO.FALLING,
                            callback=self.sensor_callback_low,
                            bouncetime=40000
                        )
            # Disable sensor
            elif event in (
                    Events.PRINT_DONE,
                    Events.PRINT_FAILED,
                    Events.PRINT_CANCELLED,
                    Events.ERROR
            ):
                self._logger.info("%s: Disabling filament sensor." % (event))
                GPIO.remove_event_detect(self.pin)
                self.changing_filament_initiated = False
                self.changing_filament_started = False
                self.paused_for_user = False

    def sensor_callback_high(self, _):
        self._logger.info("Sensor was triggered high")
        sleep(30)
        if GPIO.input(self.pin) != GPIO.HIGH:
            return self._logger.info("Sensor was false positive high")
        elif not self.changing_filament_initiated:
            self.send_out_of_filament()

    def sensor_callback_low(self, _):
        self._logger.info("Sensor was triggered low")
        sleep(30)
        if GPIO.input(self.pin) != GPIO.LOW:
            return self._logger.info("Sensor was false positive low")
        elif not self.changing_filament_initiated:
            self.send_out_of_filament()

    def send_out_of_filament(self):
        self.show_printer_runout_popup()
        self._logger.info("Sending out of filament GCODE")
        self._printer.commands("M600")
        self.changing_filament_initiated = True

    def show_printer_runout_popup(self):
        self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False, msg="Printer ran out of filament!"))

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
__plugin_version__ = "0.1.0"

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
