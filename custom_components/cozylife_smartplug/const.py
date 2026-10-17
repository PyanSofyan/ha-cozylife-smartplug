"""Constants for the CozyLife Smart Plug integration."""

DOMAIN = "cozylife_smartplug"
MANUFACTURER = "CozyLife"
MODEL = "Smart Plug"

CONF_IP_ADDRESS   = "ip_address"
CONF_DEVICE_NAME  = "device_name"
CONF_DEVICE_TYPE  = "device_type"
CONF_AUTHORIZATION_CODE = "authorization_code"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_KEY = "device_key"
CONF_RELAY_HOST = "relay_host"
CONF_RELAY_PORT = "relay_port"
CONF_WSS_DOMAIN = "wss_domain"
CONF_DEVICE_MODEL = "device_model"
CONF_ENTITY_ID = "entity_identity"

AUTH_CODE_URL = "https://api-cn.doiting.com/api/app/auth_code2token"
DEVICE_LIST_URL = "https://api-us.doiting.com/api/v2/app/device_with_group/list"
CLOUD_USER_AGENT = "CozyLife/1.20.24 okhttp/4.9.0"
CLOUD_TIMEOUT = 12
CLOUD_REFRESH_INTERVAL = 60
DISCOVERY_INTERVAL = 300
LOCAL_FAILURE_THRESHOLD = 3
LOCAL_RETRY_INTERVAL = 60

DEVICE_TYPE_SMART_PLUG   = "smart_plug"
DEVICE_TYPE_SMART_SWITCH = "smart_switch"

UPDATE_INTERVAL = 10

CMD_QUERY = 2
CMD_SET = 3

SWITCH_ID = 1
ON_STATE_ID = 18
CURRENT_ID = 27
POWER_ID = 28
VOLTAGE_ID = 29
OVERCURRENT_PROTECT_ID = 32
ENERGY_ID = 26

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
