# TFA KlimaLogg Pro for Home Assistant

This repository is a fork of [z8i/ha_custom_klimaloggpro](https://github.com/z8i/ha_custom_klimaloggpro) by Martin (z8i). It keeps that custom component and updates it for Home Assistant 2026.9.

The USB driver is the matching fork of [kloggpro](https://github.com/alexisvannier/kloggpro) 0.1.0, itself based on [weewx-klimalogg](https://github.com/matthewwall/weewx-klimalogg) by Matthew Wall. The station must be a TFA KlimaLogg Pro with its USB transceiver plugged into the computer that runs Home Assistant.

## Sensors

During setup, choose temperature and humidity for the indoor channel and for channels 1 to 8. The integration then creates:

- one temperature sensor and one humidity sensor for each selected channel
- one signal-strength sensor for the USB link
- one battery sensor for each enabled channel

Minimum and maximum values stay available as attributes on the temperature and humidity sensors.

## Installation

Use HACS and add this repository as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories) of category Integration.

URL: `https://github.com/alexisvannier/ha_custom_klimaloggpro`

1. Add the repository to HACS
2. Install the custom integration "TFA KlimaLogg pro BETA"
3. Restart Home Assistant
4. Go to Settings → Devices & services
5. Add the "Klimalogg" integration. The first USB connection can take a while. Refresh the page if it does not appear
6. Select the sensors connected to the base station
7. Hold the USB button on the station for about 3 seconds, until "USB" stays on the display
8. Add the sensors to a dashboard

On Home Assistant OS, the USB device is available without extra permission rules. On a manual install, the process user needs access to the transceiver. See below.

## Restart USB pairing

If the dongle fails to connect, for example after changing the station batteries:

1. Settings → Devices & services → KlimaLogg → Configure
2. The page shows whether the USB dongle is detected, paired, and when it last received data
3. Hold the USB button on the station until "USB" stays on the display
4. Choose **Check and restart USB pairing**

The same driver is reopened, so existing sensors stay in place. Pairing can take a minute while the radio thread stops.

## Station history

The console keeps temperature and humidity in its own memory. On the KlimaLogg Pro device page, two configuration buttons use that memory:

- **Reread history** reads records that are missing from Home Assistant, by default the last 7 days or everything newer than the latest stored hour. Hold the station USB button until "USB" stays on the display. Readings are stored as hourly minimum, mean and maximum statistics. The current hour still comes from the live sensors. A progress notification reports the result.
- **Clear history** deletes Home Assistant history for this station. The console memory is left as it is, so it can be read again.

Signal strength and battery status are not stored in the station history.

## USB device access

The transceiver identifies as USB vendor `6666`, product `5555`. On a manual Home Assistant installation, grant access to that device:

- add the Home Assistant user to the `plugdev` group: `sudo adduser <username> plugdev`
- add this rule to `/etc/udev/rules.d/50-usb-perms.rules`:

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="6666", ATTRS{idProduct}=="5555", GROUP="plugdev", MODE="0660"
```

Check that the device is present and writable by `plugdev`:

```bash
lsusb
# Bus 001 Device 004: ID 6666:5555 Prototype product Vendor ID
ls -l /dev/bus/usb/001/004
# crw-rw---- 1 root plugdev 189, 3 Dec 21 21:52 /dev/bus/usb/001/004
```

The bus and device numbers change. An error such as `The device has no langid` usually means the process cannot read the USB string descriptors.

## Tested with

- Home Assistant Operating System on a Raspberry Pi 4 Model B
- Home Assistant 2026.9
- A manual install on Raspberry Pi OS, with the udev rule above

Issues: https://github.com/alexisvannier/ha_custom_klimaloggpro/issues
