# CozyLife Smart Plug - Home Assistant Integration

A Home Assistant custom integration for controlling and monitoring CozyLife Smart Plug devices over the local network.

## Features

### Controls Entities
- **Switch**: Control the power state of the smart plug (On/Off)
- **Overcurrent Protection**: Enable/disable overcurrent protection
- **Power On State**: Configure the plug's behavior after power restoration
  - All Off: All outlets remain off
  - All On: All outlets turn on
  - Remember the last state: Restore previous state

### Sensors Entities
- **Current**: Real-time current consumption (A)
- **Power**: Real-time power consumption (W)
- **Voltage**: Current voltage (V)
- **Energy**: Cumulative energy consumption since device was configured to the Homekit (kWh)
- **Energy Today**: Daily energy consumption (kWh) - calculated from Energy sensor statistics
- **Energy this Month**: Monthly energy consumption (kWh) - calculated from Energy sensor statistics

> ⚠️**Do not rename the entity ID of the Energy sensor**. The **Energy Today** and **Energy this Month** sensors depend on the statistics history of the Energy sensor. Modifying its entity ID will break the dependent sensors.

## Installation

### HACS Installation (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=PyanSofyan&repository=ha-cozylife-smartplug&category=integration)

Or manually:

1. Open Home Assistant and navigate to **HACS**
2. Click the three-dot menu
3. Select **Custom repositories**
4. Add ``https://github.com/PyanSofyan/ha-cozylife-smartplug`` as Type **Integration**
5. Click **CozyLife Smart Plug**, getting into the detail page then **DOWNLOAD**
6. Restart Home Assistant

### Manual Installation

1. Download the integration from [GitHub](https://github.com/PyanSofyan/ha-cozylife-smartplug)
2. Extract the contents
3. Copy the `cozylife_smartplug` folder from `custom_components` to your Home Assistant `/config/custom_components/` directory
4. Restart Home Assistant

## Configuration

[![Open your Home Assistant instance and start setting up a new Cozylife Smart Plug integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cozylife_smartplug)

Or manually:

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **CozyLife Smart Plug**
4. Follow the configuration flow:
   - Enter the IP address your CozyLife Smart Plug
   - Configure Device Name as needed
5. Click **Submit**

## Troubleshooting

### Device not responding
- Verify the CozyLife Smart Plug is powered on and connected to your network
- Check that the device IP address is correct
- Assign static IP addresses to prevent IP changes
- Ensure no more than 3 simultaneous connections are active. The device firmware is limited to a maximum of 3 concurrent connections.
- Restart or unplug the device to reset all connections
- Use ``telnet ip_address 5555`` to verify the TCP connection is accessible
- Check Home Assistant logs for error messages

### Energy sensors not working
- Verify that the Energy sensor entity ID has not been modified
- If modified, perform **Recreate entity IDs** and **Reload** the integration
- Initial values for **Energy Today** and **Energy this Month** will be 0.00 kWh even Energy sensor has a value. This is normal, these entities use historical statistics, while the main Energy sensor displays real-time data directly from the device.
