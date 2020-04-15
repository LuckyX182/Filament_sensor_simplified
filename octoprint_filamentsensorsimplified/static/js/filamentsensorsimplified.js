$(function() {
    function filamentsensorsimplifiedViewModel(parameters) {
        var self = this;

		self.settingsViewModel = parameters[0];

		self.autoClose = ko.observable();
		self.msgType = ko.observable();
		self.msgTypes = ko.observableArray([{
						name : 'Notice',
						value : 'notice'
					}, {
						name : 'Error',
						value : 'error'
					}, {
						name : 'Info',
						value : 'info'
					}, {
						name : 'Success',
						value : 'success'
					}, {
						name : 'Disabled',
						value : 'disabled'
					}
				]);

		self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "filamentsensorsimplified") {
				console.log('Ignoring '+plugin);
                return;
            }

			if(data.type == "popup") {
				// console.log(data.msg);
				if(self.settingsViewModel.settings.plugins.filamentsensorsimplified.msgType() != "disabled"){
					new PNotify({
						title: 'Filament sensor simplified message',
						text: data.msg,
						type: self.settingsViewModel.settings.plugins.filamentsensorsimplified.msgType(),
						hide: self.settingsViewModel.settings.plugins.filamentsensorsimplified.autoClose()
						});
				}
			}
		}

		self.onBeforeBinding = function() {
            self.msgType(self.settingsViewModel.settings.plugins.filamentsensorsimplified.msgType());
            self.autoClose(self.settingsViewModel.settings.plugins.filamentsensorsimplified.autoClose());
        }

		self.onEventSettingsUpdated = function (payload) {
            self.msgType = self.settingsViewModel.settings.plugins.filamentsensorsimplified.msgType();
            self.autoClose = self.settingsViewModel.settings.plugins.filamentsensorsimplified.autoClose();
        }

		self.testPopUp = function(data) {
			self.onDataUpdaterPluginMessage("filamentsensorsimplified", {'msg':'Filament Sensor Simplified pop up message example.','type':'popup'});
		}

    }

    // This is how our plugin registers itself with the application, by adding some configuration
    // information to the global variable OCTOPRINT_VIEWMODELS
    ADDITIONAL_VIEWMODELS.push([
        // This is the constructor to call for instantiating the plugin
        filamentsensorsimplifiedViewModel,

        // This is a list of dependencies to inject into the plugin, the order which you request
        // here is the order in which the dependencies will be injected into your view model upon
        // instantiation via the parameters argument
        ["settingsViewModel"],

        // Finally, this is the list of selectors for all elements we want this view model to be bound to.
        ["#settings_plugin_filamentsensorsimplified_form"]
    ]);
});
