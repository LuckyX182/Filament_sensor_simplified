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

	# pin number used as plugin disabled
	pin_num_disabled = 0

	# default gcode
	default_gcode = 'M600 X0 Y0'

	# gpio mode disabled
	gpio_mode_disabled = False

	# printing flag
	printing = False

	# detection active
	detectionOn = False

	def initialize(self):
		GPIO.setwarnings(True)
		# flag telling that we are expecting M603 response
		self.checking_M600 = False
		# flag defining if printer supports M600
		self.M600_supported = True
		# flag defining that the filament change command has been sent to printer, this does not however mean that
		# filament change sequence has been started
		self.changing_filament_initiated = False
		# flag defining that the filament change sequence has been started and the M600 command has been se to printer
		self.changing_filament_command_sent = False
		# flag defining that the filament change sequence has been started and the printer is waiting for user
		# to put in new filament
		self.paused_for_user = False
		# flag for determining if the gcode starts with M600
		self.M600_gcode = True
		# flag to prevent double detection
		self.changing_filament_started = False

	@property
	def gpio_mode(self):
		return int(self._settings.get(["gpio_mode"]))

	@property
	def pin(self):
		return int(self._settings.get(["pin"]))

	@property
	def power(self):
		return int(self._settings.get(["power"]))

	@property
	def g_code(self):
		return self._settings.get(["g_code"])

	@property
	def triggered(self):
		return int(self._settings.get(["triggered"]))

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
			pin=self.pin_num_disabled,  # Default is -1
			power=0,
			g_code=self.default_gcode,
			triggered=0
		)

	# simpleApiPlugin
	def get_api_commands(self):
		return dict(testSensor=["pin", "power"])

	@octoprint.plugin.BlueprintPlugin.route("/disable", methods=["GET"])
	def get_disable(self):
		self._logger.debug("getting disabled info")
		if self.printing:
			self._logger.debug("printing")
			gpio_mode_disabled = True
		else:
			self._logger.debug("not printing")
			gpio_mode_disabled = self.gpio_mode_disabled

		return flask.jsonify(gpio_mode_disabled=gpio_mode_disabled, printing=self.printing)

	# test pin value, power pin or if its used by someone else
	def on_api_command(self, command, data):
		try:
			selected_power = int(data.get("power"))
			selected_pin = int(data.get("pin"))
			mode = int(data.get("mode"))
			triggered = int(data.get("triggered"))

			# BOARD
			if mode is 10:
				# if mode set by 3rd party don't set it again
				if not self.gpio_mode_disabled:
					GPIO.cleanup()
					GPIO.setmode(GPIO.BOARD)
				# first check pins not in use already
				usage = GPIO.gpio_function(selected_pin)
				self._logger.debug("usage on pin %s is %s" % (selected_pin, usage))
				# 1 = input
				if usage is not 1:
					# 555 is not http specific so I chose it
					return "", 555
			# BCM
			elif mode is 11:
				# BCM range 1-27
				if selected_pin > 27:
					return "", 556
				# if mode set by 3rd party don't set it again
				if not self.gpio_mode_disabled:
					GPIO.cleanup()
					GPIO.setmode(GPIO.BCM)

			# before read don't let the pin float
			self._logger.debug("selected power is %s" % selected_power)
			if selected_power is 0:
				GPIO.setup(selected_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
			else:
				GPIO.setup(selected_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

			pin_value = GPIO.input(selected_pin)
			self._logger.debug("pin value is %s" % pin_value)

			# reset input to pull down after read
			GPIO.setup(selected_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

			triggered_bool = (pin_value + selected_power + triggered) % 2 is 0
			self._logger.debug("triggered value %s" % triggered_bool)
			return flask.jsonify(triggered=triggered_bool)
		except ValueError as e:
			self._logger.error(str(e))
			# ValueError occurs when reading from power, ground or out of range pins
			return "", 556

	def on_after_startup(self):
		self._logger.info("Filament Sensor Simplified started")
		gpio_mode = GPIO.getmode()

		# Fix old -1 settings to 0
		if self.pin is -1:
			self._logger.info("Fixing old settings from -1 to 0")
			self._settings.set(["pin"], 0)
			self.pin = 0
		if gpio_mode is not None:
			self._settings.set(["gpio_mode"], gpio_mode)
			self.gpio_mode_disabled = True
		else:
			if self.gpio_mode is 10:
				GPIO.setmode(GPIO.BOARD)
			elif self.gpio_mode is 11:
				GPIO.setmode(GPIO.BCM)
			self.gpio_mode_disabled = False
		self._logger.info("Mode is %s" % (gpio_mode))

	def on_settings_save(self, data):
		# Retrieve any settings not changed in order to validate that the combination of new and old settings end up in a bad combination
		pin_to_save = self._settings.get_int(["pin"])
		mode_to_save = self._settings.get_int(["gpio_mode"])

		if "pin" in data:
			pin_to_save = int(data.get("pin"))

		if "gpio_mode" in data:
			mode_to_save = int(data.get("gpio_mode"))

		if pin_to_save is not None:
			# check if pin is not power/ground pin or out of range but allow the disabled value (0)
			if pin_to_save is not self.pin_num_disabled:
				try:
					# BOARD
					if mode_to_save is 10:
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
					elif mode_to_save is 11:
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

		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

	def checkM600Enabled(self):
		sleep(1)
		self.checking_M600 = True
		self._printer.commands("M603")

	# this method is called before the gcode is sent to printer
	def sending_gcode(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
		if self.changing_filament_initiated and self.M600_supported:
			if self.changing_filament_command_sent and self.changing_filament_started:
				# M113 - host keepalive message, ignore this message
				if not re.search("^M113", cmd):
					self.changing_filament_initiated = False
					self.changing_filament_command_sent = False
					self.changing_filament_started = False
					if self.no_filament():
						self.send_out_of_filament()
			if cmd == self.g_code:
				self.changing_filament_command_sent = True

		# deliberate change
		if self.M600_supported and re.search("^M600", cmd):
			self.changing_filament_initiated = True
			self.changing_filament_command_sent = True

	# this method is called on gcode response
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

		# waiting for M603 command response
		if self.checking_M600:
			if re.search("^ok", line):
				self._logger.debug("Printer supports M600")
				self.M600_supported = True
				self.checking_M600 = False
			elif re.search("^echo:Unknown command: \"M603\"", line):
				self._logger.debug("Printer doesn't support M600")
				self.M600_supported = False
				self.checking_M600 = False
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True,
																				msg="M600 gcode command is not enabled on this printer! This plugin won't work."))
			else:
				self._logger.debug("M600 check unsuccessful, trying again")
				self.checkM600Enabled()
		return line

	# plugin disabled if pin set to -1
	def sensor_enabled(self):
		return self.pin != self.pin_num_disabled

	# read sensor input value
	def no_filament(self):
		return (GPIO.input(self.pin) + self.power + self.triggered) % 2 is not 0

	# method invoked on event
	def on_event(self, event, payload):
		# octoprint connects to 3D printer
		if event is Events.CONNECTED:
			# if the command starts with M600, check if printer supports M600
			if re.search("^M600", self.g_code):
				self.M600_gcode = True
				self.checkM600Enabled()

		# octoprint disconnects from 3D printer, reset M600 enabled variable
		elif event is Events.DISCONNECTED:
			self.M600_supported = True

		# if user has logged in show appropriate popup
		elif event is Events.CLIENT_OPENED:
			if self.changing_filament_initiated and not self.changing_filament_command_sent:
				self.show_printer_runout_popup()
			elif self.changing_filament_command_sent and not self.paused_for_user:
				self.show_printer_runout_popup()
			# printer is waiting for user to put in new filament
			elif self.changing_filament_command_sent and self.paused_for_user:
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=False,
																				msg="Printer ran out of filament! It's waiting for user input"))
			# if the plugin hasn't been initialized
			if not self.sensor_enabled():
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", autoClose=True,
																				msg="Don't forget to configure this plugin."))

		if not (self.M600_gcode and not self.M600_supported):
			# Enable sensor
			if event in (
					Events.PRINT_STARTED,
					Events.PRINT_RESUMED
			):
				self._logger.info("%s: Enabling filament sensor." % (event))
				if self.sensor_enabled():
					if self.gpio_mode is 10:
						GPIO.setmode(GPIO.BOARD)
					elif self.gpio_mode is 11:
						GPIO.setmode(GPIO.BCM)

					# 0 = sensor is grounded, react to rising edge pulled up by pull up resistor
					if self.power is 0:
						GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
						# triggered when open
						if self.triggered is 0:
							self.turnOffDetection(event)
							self.detectionOn = True
							GPIO.add_event_detect(
								self.pin, GPIO.RISING,
								callback=self.sensor_callback,
								bouncetime=self.bounce_time)
						# triggered when closed
						else:
							self.turnOffDetection(event)
							self.detectionOn = True
							GPIO.add_event_detect(
								self.pin, GPIO.FALLING,
								callback=self.sensor_callback,
								bouncetime=self.bounce_time)

					# 1 = sensor is powered, react to falling edge pulled down by pull down resistor
					else:
						GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
						# triggered when open
						if self.triggered is 0:
							self.turnOffDetection(event)
							self.detectionOn = True
							GPIO.add_event_detect(
								self.pin, GPIO.RISING,
								callback=self.sensor_callback,
								bouncetime=self.bounce_time)
						# triggered when closed
						else:
							self.turnOffDetection(event)
							self.detectionOn = True
							GPIO.add_event_detect(
								self.pin, GPIO.FALLING,
								callback=self.sensor_callback,
								bouncetime=self.bounce_time)

					# print started with no filament present
					if self.no_filament() and event is Events.PRINT_STARTED:
						self._logger.info("Printing aborted: no filament detected!")
						self._printer.cancel_print()
						self._plugin_manager.send_plugin_message(self._identifier,
																 dict(type="error", autoClose=True,
																	  msg="No filament detected! Print cancelled."))
					elif self.no_filament() and event is Events.PRINT_RESUMED:
						self._logger.info("Resuming print aborted: no filament detected!")
						self._printer.pause_print()
						self._plugin_manager.send_plugin_message(self._identifier,
																 dict(type="error", autoClose=True,
																	  msg="Resuming print aborted: no filament detected!"))
					# print started
					else:
						self.printing = True

				# print started without plugin configuration
				else:
					self._plugin_manager.send_plugin_message(self._identifier,
															 dict(type="info", autoClose=True,
																  msg="You may have forgotten to configure this plugin."))

			# Disable sensor
			elif event in (
					Events.PRINT_DONE,
					Events.PRINT_FAILED,
					Events.PRINT_CANCELLED,
					Events.ERROR
			):
				self.turnOffDetection(event)
				self.changing_filament_initiated = False
				self.changing_filament_command_sent = False
				self.paused_for_user = False
				self.printing = False

	# turn off detection if on
	def turnOffDetection(self,event):
		if self.detectionOn:
			self._logger.info("%s: Disabling filament sensor." % (event))
			self.detectionOn = False
			GPIO.remove_event_detect(self.pin)

	def sensor_callback(self, _):
		trigger = True
		for x in range(0, 5):
			sleep(0.05)
			if not self.no_filament():
				trigger = False

		if trigger:
			self._logger.info("Sensor was triggered")
			if not self.changing_filament_initiated:
				self.send_out_of_filament()

	def send_out_of_filament(self):
		self.show_printer_runout_popup()
		self._logger.info("Sending out of filament GCODE: %s" % (self.g_code))
		self._printer.commands(self.g_code)
		self.changing_filament_initiated = True

	def show_printer_runout_popup(self):
		self._plugin_manager.send_plugin_message(self._identifier,
												 dict(type="info", autoClose=False, msg="Printer ran out of filament!"))

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
