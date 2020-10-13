$(function () {
    function filamentsensorsimplifiedViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];
        self.testSensorResult = ko.observable(null);
        self.gpio_mode_disabled = ko.observable(false);
        self.printing = ko.observable(false);
        self.gpio_mode_disabled_by_3rd = ko.computed(function() {
            return this.gpio_mode_disabled() && !this.printing();
        }, this);

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "filamentsensorsimplified") {
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
                        "power": $("#powerInput").val(),
                        "mode": $("#gpioMode").val(),
                        "triggered": $("#triggeredInput").val()
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
                            self.testSensorResult("That is power, ground or out of range pin, choose other pin");
                        }
                    },
                    error: function () {
                        $("#sensor-test-result-text").css("color", "red");
                        self.testSensorResult("There was an error :(");
                    },
                    success: function (result) {
                        if (result.triggered === true) {
                            $("#sensor-test-result-text").css("color", "green");
                            self.testSensorResult("Sensor detected filament!");
                        } else {
                            $("#sensor-test-result-text").css("color", "red");
                            self.testSensorResult("Sensor triggered!")
                        }
                    }
                }
            );
        }

        getDisabled = function (item) {
            $.ajax({
                type: "GET",
                dataType: "json",
                url: "plugin/filamentsensorsimplified/disable",
                success: function (result) {
                    console.log("success");
                    console.log(result.gpio_mode_disabled);
                    console.log(result.printing);
                    self.gpio_mode_disabled(result.gpio_mode_disabled)
                    self.printing(result.printing)
                }
            });
        };

        self.onSettingsShown = function () {
            self.testSensorResult("");
            getDisabled();
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
