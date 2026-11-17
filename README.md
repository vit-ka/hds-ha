# hds-ha

A small Home Assistant custom integration (`hds`) for the **Half Decent Scale** from Decent
Espresso. It reads the scale's battery state over WiFi and checks whether newer firmware has been
published. It does nothing else: no weight, no tare, no control.

| Entity | Notes |
|---|---|
| `sensor.half_decent_scale_battery` | battery level, %; attribute `last_seen` is when the scale last answered |
| `sensor.half_decent_scale_battery_voltage` | battery voltage, V |
| `binary_sensor.half_decent_scale_charging` | on while the scale reports it is charging |
| `update.half_decent_scale_firmware` | installed version against the latest stable release; links the release notes |

Design: [ADR 0001](docs/adr/0001-last-answer-kept-while-the-scale-sleeps.md).

## How it works

- Every 5 minutes it makes one plain HTTP request to the scale to see whether it is awake.
- When the scale has just woken, it opens the WebSocket (`ws://<scale>/snapshot`), sends `status`,
  reads one answer and disconnects. This needs WiFi enabled on the scale (firmware 3.0.0 or later).
- **It asks for `status` once per wake, not on every poll.** The firmware restarts its 15-minute
  auto-off countdown whenever a WebSocket client is connected, so asking every 5 minutes would keep
  the scale awake until the battery ran out. It asks again every 30 minutes if the scale is still
  awake, and on every poll while the scale is charging, when it stays awake regardless.
- **The scale switches itself off after 15 idle minutes**, so most polls get no answer. That is
  normal: the entities keep the last values, and `last_seen` says how old they are. The values
  also survive a Home Assistant restart.
- Every 6 hours it reads the latest stable version from the firmware's release catalog on GitHub
  (`decentespresso/openscale`), the same catalog the scale's own `WiFi Update` menu uses.
- The update entity **reports only**. Install firmware from the scale: `Setup` → `Connections` →
  `WiFi Update`, with the scale on USB power.

The keep-awake behaviour was read from the 3.1.16 firmware source, not measured on a scale. To
check it on yours: use the scale on battery, leave it, and confirm it is off 15 to 20 minutes later.

## Install (git checkout on the HA box)

Run these in the HA SSH app.

```sh
mkdir -p /config/repos /config/custom_components
git clone https://github.com/vit-ka/hds-ha.git /config/repos/hds-ha
ln -s ../repos/hds-ha/custom_components/hds /config/custom_components/hds
```

Restart Home Assistant. Turn the scale on, then Settings → Devices & services → Add integration →
**Half Decent Scale**, and enter the scale's address: `hds.local` unless you renamed it, or its IP
address. The scale has to answer once, so a wrong address is caught here. A scale on firmware
3.1.15 or later is recognised by its own id, so it can be re-added at a new address.

Update: `git -C /config/repos/hds-ha pull`, then restart Home Assistant.

## Security note

The scale's WebSocket is unauthenticated: anything that can reach it on the network can tare it,
change its settings or switch it off. This integration only ever sends `status`.

## Development

```sh
python -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest
```
