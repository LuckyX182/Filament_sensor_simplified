# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import re
from octoprint.events import Events
import RPi.GPIO as GPIO
from time import sleep


class Filament_sensor_simplifiedPlugin(octoprint.plugin.StartupPlugin,
									   octoprint.plugin.EventHandlerPlugin,
									   octoprint.plugin.TemplatePlugin,
									   octoprint.plugin.SettingsPlugin,
									   octoprint.plugin.AssetPlugin):

	def initialize(self):
		self._logger.info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
		if GPIO.VERSION < "0.6":  # Need at least 0.6 for edge detection
			raise Exception("RPi.GPIO must be greater than 0.6")
		GPIO.setwarnings(False)  # Disable GPIO warnings
		self.print_head_parking = False
		self.print_head_parked = False
		self.checkingM600 = False
		self.m600Enabled = True

	@property
	def pin(self):
		return int(self._settings.get(["pin"]))

	@property
	def switch(self):
		return int(self._settings.get(["switch"]))

	# AssetPlugin hook
	def get_assets(self):
		return dict(js=["js/filamentsensorsimplified.js"])

	# Template hooks
	def get_template_configs(self):
		return [dict(type="settings", custom_bindings=False)]

	# Settings hook
	def get_settings_defaults(self):
		return dict(
			pin=-1,  # Default is -1
			switch=1,  # Normally closed
			autoClose=True,
		)

	def on_after_startup(self):
		self._logger.info("Filament Sensor Simplified started")
		self._setup_sensor()

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self._setup_sensor()

	def _setup_sensor(self):
		if self.sensor_enabled():
			self._logger.info("Setting up sensor.")
			self._logger.info("Using Board Mode")
			GPIO.setmode(GPIO.BOARD)
			self._logger.info("Filament Sensor active on GPIO Pin [%s]" % self.pin)
			GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		else:
			self._logger.info("Pin not configured, won't work unless configured!")

	def checkM600Enabled(self):
		sleep(1)
		self.checkingM600 = True
		self._printer.commands("M603")

	def get_position_info(self):
		self._logger.debug("Sending M114 command")
		self._printer.commands("M114")

	def gcode_response_received(self, comm, line, *args, **kwargs):
		if self.m600Enabled:
			if re.search("^X:.* Y:.* Z:.* E:.*", line):
				self._logger.debug("Received coordinates, processing...")
				self.extract_xy_position(line)
			if re.search("^ok", line) and self.checkingM600:
				self._logger.debug("Printer supports M600")
				self.m600Enabled = True
				self.checkingM600 = False
			elif re.search("^echo:Unknown command: \"M603\"", line) and self.checkingM600:
				self._logger.debug("Printer doesn't support M600")
				self.m600Enabled = False
				self.checkingM600 = False
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", msg="M600 gcode command is not enabled on this printer! This plugin won't work."))
			elif self.checkingM600:
				self._logger.debug("M600 check unsuccessful, trying again")
				self.checkM600Enabled()
		return line

	def extract_xy_position(self, arg):
		initial_list = arg.split(" ")[:2]
		xy_coordinates = []
		for item in initial_list:
			xy_coordinates.append(item.split(":")[1])
		self._logger.debug("Parsed coordinates are: X%s Y%s", xy_coordinates[0], xy_coordinates[1])
		self.set_head_parked(xy_coordinates)

	def set_head_parked(self, xy_coordinates):
		if xy_coordinates[0] == "0.00" and xy_coordinates[1] == "0.00":
			self._logger.debug("Print head is parked")
			self.print_head_parked = True
		else:
			self._logger.debug("Print head is not parked")
			self.print_head_parked = False

	def sensor_enabled(self):
		return self.pin != -1

	def no_filament(self):
		return GPIO.input(self.pin) != self.switch

	def on_event(self, event, payload):
		self._logger.info("Received event: %s" %(event))
		if event is Events.CONNECTED:
			self.checkM600Enabled()
		elif event is Events.DISCONNECTED:
			self.m600Enabled = True

		if not self.sensor_enabled():
			if event is Events.USER_LOGGED_IN:
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", msg="Don' forget to configure this plugin."))
			elif event is Events.PRINT_STARTED:
				self._plugin_manager.send_plugin_message(self._identifier, dict(type="info", msg="You may have forgotten to configure this plugin."))
		elif event is Events.PRINT_STARTED and self.no_filament():
			self._logger.info("Printing aborted: no filament detected!")
			self._printer.cancel_print()
			self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", msg="No filament detected! Print cancelled."))
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
					GPIO.add_event_detect(
						self.pin, GPIO.BOTH,
						callback=self.sensor_callback,
						bouncetime=1
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

	def sensor_callback(self, _):
		self.get_position_info()
		sleep(1)

		if self.no_filament() and not self.print_head_parked:
			self._logger.info("Out of filament!")
			if self.print_head_parking:
				self._logger.info("Waiting for print head to park")
				return
			self._logger.info("Sending out of filament GCODE")
			self._printer.commands("M600 X0 Y0")
			self.print_head_parking = True
		elif self.print_head_parked:
			self.print_head_parking = False
			if not self.no_filament():
				self._logger.info("Filament detected!")

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
		# for details.
		return dict(
			Filament_Sensor_Simplified=dict(
				displayName="Filament_sensor_simplified Plugin",
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


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = Filament_sensor_simplifiedPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.received": __plugin_implementation__.gcode_response_received
	}
