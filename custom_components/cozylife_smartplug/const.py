"""Constants for the CozyLife Smart Plug integration."""

DOMAIN = "cozylife_smartplug"
MANUFACTURER = "CozyLife"
MODEL = "Smart Plug"

CONF_IP_ADDRESS  = "ip_address"
CONF_DEVICE_NAME = "device_name"

UPDATE_INTERVAL = 10

CMD_QUERY = 2
CMD_SET = 3

SWITCH_ID = 1
ON_STATE_ID = 18
CURRENT_ID = 27
POWER_ID = 28
VOLTAGE_ID = 29
OVERCURRENT_PROTECT_ID = 32
ENERGY_ID = 42

SWITCH_NAME = "Switch"
ON_STATE_NAME = "Power On State"
DAILY_ENERGY_NAME = "Daily Energy"
CURRENT_NAME = "Current"
POWER_NAME = "Power"
VOLTAGE_NAME = "Voltage"
OVERCURRENT_PROTECT_NAME = "Overcurrent Protection"
ENERGY_NAME = "Energy"
ENERGY_TODAY = "Energy Today"
ENERGY_MONTH = "Energy this Month"

MODE_ON_STATE = "on_state"
ON_STATE_OPTIONS = {
    "All Off": 0,
    "All On": 1,
    "Remember the last state": 2
}