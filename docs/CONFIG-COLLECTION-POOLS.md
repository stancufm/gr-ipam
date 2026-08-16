# Scheduled configuration collection pools

GR can collect device configurations into the global Git archive with
`gr collect config`. Named pools add safe periodic scheduling without putting
credentials, SSH commands, or a second device inventory in cron.

## Model and safety

phpIPAM remains the target, hostname, driver and SSH metadata source of truth.
A pool contains selectors only. Every resolved target must have SSH enabled, a
profile, an explicit non-generic driver and a configuration command. A rejected
target makes the pool fail before any connection is opened; targets are never
silently omitted.

The scheduler:

- is disabled by default and is never enabled by installation or upgrade;
- uses one non-blocking lock, so manual and timer runs cannot overlap;
- clamps workers to 1-12 and validates every configuration key;
- writes only safe summary state, atomically, with mode `0600` below a `0700`
  directory;
- retries failed pools on `retry_interval`, not every timer tick;
- checks an optional active-node marker and maintenance window for `--due`;
- delegates collection and Git archive commits to the existing collector.

Pool files contain no secrets. Device passwords continue to come from the
existing encrypted SSH profiles. An unattended run must be able to decrypt
those profiles without a graphical prompt. Validate this in the same user
session with `gr vault test PROFILE` before enabling the timer; GR does not
weaken the vault or store a passphrase for scheduling.

## Configuration

Add `config_collection` to the normal system or user GR JSON configuration.
See `examples/config-collection-pools.json` for a complete example.

Top-level settings:

- `state_dir`: per-user runtime state; default
  `~/.local/state/gr/config-collection`;
- `scheduler_enabled`: must be `true` before `--due` performs work;
- `active_marker`: optional path which must exist on the active HA node;
- `pools`: named pool objects.

Each pool requires `interval` and at least one selector: `ips`,
`hostname_regex`, `vendor`, or `driver`. Selectors in the same pool are ANDed.
Supported controls are `enabled`, `retry_interval`, `workers`, `exclude_ips`,
`exclude_hostnames`, and an optional local Europe/Bucharest
`maintenance_window` with `days`, `start`, and `end`. Intervals use `m`, `h`,
or `d` and must be between 15 minutes and 365 days.

Use non-overlapping pools. `gr collect config pools` reports overlaps as
attention because simultaneous schedules would collect the same device twice.

## Commands

```text
gr collect config pools
gr collect config status
gr collect config --pool critical
gr collect config --due
```

`pools` resolves phpIPAM targets and validates eligibility without contacting
devices. `status` reads local state only. `--pool` starts one pool immediately;
`--due` honors scheduler, active-marker, interval, retry, and maintenance-window
controls. Existing direct commands such as `gr collect config --ip ADDRESS`
remain unchanged.

## User systemd timer

The package installs `gr-config-collect.service` and `.timer` in
`/etc/systemd/user`. They deliberately run as the operator, so GR can use that
user's API configuration and encrypted vault without a hard-coded service
account. After configuring and validating pools on the active node:

```text
systemctl --user daemon-reload
systemctl --user enable --now gr-config-collect.timer
systemctl --user status gr-config-collect.timer
journalctl --user -u gr-config-collect.service
```

For operation without an interactive login, the administrator may enable
systemd user lingering explicitly for the chosen account. Do this only on the
active HA peer. On demotion, disable the timer or remove the configured active
marker. Upgrades preserve the disabled/enabled state and never activate it.

The authoritative `/var/lib/gr/config-archive` must be replicated to the
standby with owner, group and mode preserved. The standby may read it but must
not schedule collection until promotion has been validated.

## Recovery

If a run fails, inspect `gr collect config status` and the user journal. Fix
phpIPAM metadata, vault availability, or device access, then run the affected
pool manually. Removing `state.json` is unnecessary: a failure becomes
eligible again after `retry_interval`; a successful manual run updates the same
state atomically.
