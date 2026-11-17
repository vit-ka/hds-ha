# 0001. The last answer is kept while the scale sleeps

Date: 2026-11-17
Status: Accepted

## Context

The Half Decent Scale powers off after 15 idle minutes and is then off the network; in normal use
it is unreachable most of the day. Its WiFi interface is a WebSocket at `/snapshot` where a
`status` request returns battery percent, voltage, charging state and firmware version. It pushes
nothing when it wakes.

Firmware 3.1.16 restarts the auto-off countdown on every main-loop pass while a WebSocket client
is connected (`src/hds.ino`: `websocketHasClients()` beside charging and a live BLE client). A
`status` request every few minutes would therefore keep the scale awake indefinitely. Plain HTTP
requests are not counted. `GET /setup/wifi/status` (3.1.15 and later) answers over plain HTTP with
WiFi state and a `device_id`, but no battery data.

The purpose is a battery level that low-battery alerts can use, and a firmware update check.
Entities that went unavailable whenever the scale slept would be unavailable nearly always, and
would look like a dead device to anything watching for one.

## Decision

- Every 5 minutes one plain HTTP request to `/setup/wifi/status` tells whether the scale is awake.
  Any HTTP answer counts, so older firmware without that route still reads as awake. No answer is
  not an error: the coordinator never fails an update for it.
- A `status` request over the WebSocket, on a short-lived connection, is made only when the scale
  has just been found awake, or has never answered, or reported charging last time (it stays awake
  while charging regardless), or 30 minutes have passed since the last request (still awake that
  long after means something else is keeping it awake).
- The last status, the time it was received, and the last known release are kept in Home
  Assistant storage. Entities show those values, asleep or not, and across restarts. They are
  unavailable only until the scale has answered for the first time.
- The battery sensors carry `last_seen`, so a stale value can be told from a fresh one.
- The latest firmware version comes from the release catalog on GitHub every 6 hours,
  independently of the scale. A failed check keeps the version already known and is retried on
  the next poll. Until a version is known, the update entity reports the installed version as the
  latest, so it never claims an update it has not seen.
- The update entity cannot install. The scale's own updater verifies a signed manifest and its
  hardware compatibility; this integration does not duplicate or bypass that.
- The config entry's unique id is the scale's `device_id` where the firmware gives one, else the
  address entered.

## Consequences

- A battery alert works on the last reading, which can be days old if the scale is unused; a
  scale that has died looks the same as one that is asleep. `last_seen` is the only way to tell.
- Each wake costs the scale at most one restart of its countdown: it can stay on up to 5 minutes
  longer than it otherwise would, once.
- On battery the level is read once per wake, so it does not track a long session closely.
- A scale used for less than 5 minutes between polls can be missed entirely.
- The keep-awake rule comes from reading the firmware source, not from a measurement; a firmware
  change to what counts as activity would need this revisited.
- Re-adding a scale at a new address updates the existing entry when the firmware gives an id;
  otherwise it means removing and re-adding the entry.
- Adding weight or control later would need a long-lived connection, which this design avoids.
