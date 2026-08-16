# Scheduled configuration collection pools

GR already has `gr collect config` and the global Git configuration archive.
This proposal adds declarative pools and a scheduler without placing credentials,
device lists, or SSH commands in cron.

## Proposed CLI

- `gr collect config --pool NAME`: collect one named pool.
- `gr collect config --due`: collect only pools whose due time has elapsed.
- `gr collect config pools`: resolve and list pool targets and next execution.
- `gr collect config status`: report last success, failure, and archive age.

phpIPAM remains the inventory source of truth. Pools never hold SSH usernames,
passwords, ports, or keys. Each resolved target needs explicit non-generic GR
driver metadata and enabled SSH.

## Timer lifecycle

The GR package installs `gr-config-collect.service` and
`gr-config-collect.timer` on both first install and upgrade, and always calls
`systemctl daemon-reload`. The timer stays disabled by default. It is enabled
explicitly only on the active HA peer. An upgrade must never start collection
without this explicit activation.

The service stores due state and reports outside the Git archive, uses a lock,
bounded workers, retry/backoff, and a maintenance-window check.

## HA

`/var/lib/gr/config-archive` is authoritative on the active node and must be in
the HA export allow-list with owner and mode preserved. The standby replicates
it but does not collect or write while in standby state.
