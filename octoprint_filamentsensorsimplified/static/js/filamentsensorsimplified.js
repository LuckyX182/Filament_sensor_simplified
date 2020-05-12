$(function () {
    function filamentsensorsimplifiedViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];
        self.testSensorResult = ko.observable(null);

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "filamentsensorsimplified") {
                console.log('Ignoring ' + plugin);
                return;
            }

            new PNotify({
                title: 'Filament sensor simplified',
                text: data.msg,
                type: data.type,
                hide: data.autoClose
            });

        }

        self.testSensor = function () {
            $.ajax({
                    url: "/api/plugin/filamentsensorsimplified",
                    type: "post",
                    dataType: "json",
                    contentType: "application/json",
                    headers: {"X-Api-Key": UI_API_KEY},
                    data: JSON.stringify({
                        "command": "testSensor",
                        "pin": $("#pinInput").val(),
                        "power": $("#powerInput").val()
                    }),
                    statusCode: {
                        500: function () {
                            $("#sensor-test-result-text").css("color", "red");
                            self.testSensorResult("OctoPrint experienced issue. Check octoprint.log for further info");
                        },
                        555: function () {
                            $("#sensor-test-result-text").css("color", "red");
                            self.testSensorResult("This pin is currently used by others, choose other pin");
                        },
                        556: function () {
                            $("#sensor-test-result-text").css("color", "red");
                            self.testSensorResult("That is power or ground pin, choose other pin");
                        }
                    },
                    error: function () {
                        $("#sensor-test-result-text").css("color", "red");
                        self.testSensorResult("There was an error :(");
                    },
                    success: function (result) {
                        if (result.triggered === true) {
                            $("#sensor-test-result-text").css("color", "green");
                            self.testSensorResult("OK! Sensor detected filament.");
                        } else {
                            $("#sensor-test-result-text").css("color", "red");
                            self.testSensorResult("Fail! Sensor open (triggered).")
                        }
                    }
                }
            );
        }

        self.onSettingsShown = function () {
            self.testSensorResult("");
        }
    }

    // This is how our plugin registers itself with the application, by adding some configuration
    // information to the global variable OCTOPRINT_VIEWMODELS
    ADDITIONAL_VIEWMODELS.push({
        construct: filamentsensorsimplifiedViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_filamentsensorsimplified"]
    })
})
