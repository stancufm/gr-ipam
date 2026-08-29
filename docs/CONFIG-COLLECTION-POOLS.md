# Scheduled configuration collection pools

[Română](CONFIG-COLLECTION-POOLS.ro.md)

GR can collect device configurations into the global Git archive with
`gr collect config`. Named pools add safe periodic scheduling without putting
credentials, SSH commands, or a second device inventory in cron.

## Execution and safety model

phpIPAM remains authoritative for targets, hostnames, drivers and SSH metadata.
A pool contains selectors only. Every resolved target must have SSH enabled, a
profile, an explicit non-generic driver and a configuration command. One
rejected target fails the pool before any device connection is opened.

Scheduled runs use the dedicated, locked-down `gr-collector` system account.
They do not depend on an administrator login, `loginctl enable-linger`, or a
particular human home directory. Interactive GR commands continue to use the
calling operator's configuration and vault.

The scheduler:

- is disabled by installation and upgrade;
- uses one non-blocking lock, so manual and timer runs cannot overlap;
- clamps workers to 1-12 and validates every setting;
- retries failures on `retry_interval`, not every timer tick;
- checks the active HA marker and optional maintenance window;
- commits only changed normalized configurations.

On HA installations the collector needs traversal, but not listing or read
access, on `/etc/jumpserver-ha` so it can test the fixed, world-readable
`active` marker. The installer uses a user-specific ACL for that single
purpose; protected HA files keep their existing group-only permissions. This
works regardless of whether GR or `jumpserver-ha` is installed first.

The collector lock is stored inside the archive's `.git` directory, so it can
never appear as an untracked configuration artifact.

## Dedicated configuration and credentials

The service reads `/etc/gr/collector.json`; start from
`examples/collector.json`. It has a private state directory at
`/var/lib/gr-collector/config-collection`. Configure API authentication and
the encrypted SSH profiles specifically for `gr-collector`. Do not copy a
human user's complete home or private keys as a shortcut. Validate vault and
API access in a controlled service-account session before enabling scheduling.

An administrator can initialize it from a TTY without enabling a login shell:

```text
sudo -u gr-collector env HOME=/var/lib/gr-collector \
  gr --config /etc/gr/collector.json init --configure-auth
sudo -u gr-collector env HOME=/var/lib/gr-collector \
  gr --config /etc/gr/collector.json doctor --api
```

Pool files contain no plaintext secrets. GR does not store a GPG passphrase for
unattended scheduling. The deployment must provide an approved non-interactive
secret-unlock mechanism for this service identity, or leave the timer disabled
and run pools interactively.

Top-level `config_collection` settings are `state_dir`, `scheduler_enabled`,
`active_marker`, and `pools`. Each pool requires `interval` and at least one of
`ips`, `hostname_regex`, `vendor`, or `driver`. Selectors within a pool are
ANDed. Optional controls include `enabled`, `retry_interval`, `workers`,
`exclude_ips`, `exclude_hostnames`, and a Europe/Bucharest
`maintenance_window`. Intervals use `m`, `h`, or `d`, from 15 minutes through
365 days. Prefer non-overlapping pools; `gr collect config pools` reports any
overlap as attention.

## Commands

```text
gr collect config pools
gr collect config status
gr collect config --pool critical
gr collect config --due
```

`pools` and `status` are read-only. `--pool` starts one pool immediately;
`--due` honors scheduler, active marker, interval, retry, and maintenance
window. Direct commands such as `gr collect config --ip ADDRESS` are unchanged
and use the current operator.

Failed `RESULT` lines include a stable reason such as `ssh-key-exchange`,
`ssh-host-key`, `ssh-authentication`, or `connection-timeout`. Raw SSH stderr
and secret values are not copied into this scheduler summary.

After configuration and validation on the active HA peer:

```text
sudo systemctl daemon-reload
sudo systemctl start gr-config-collect@critical.service
sudo systemctl enable --now gr-config-collect.timer
systemctl status gr-config-collect.timer
journalctl -u gr-config-collect.service
```

The template unit provides explicit manual pool execution under the service
identity. Installation and upgrade preserve configuration and never enable the
timer. On demotion, the HA active marker fences `--due`; the timer should also
be disabled as defence in depth.

## Archive and HA

`/var/lib/gr/config-archive` is owned by `gr-collector:gr-config`, mode `2770`.
Operators granted membership in `gr-config` can read history and perform
explicit interactive collections but do not own the scheduled writer.
Configurations can contain secrets, so access must remain limited.
The installer registers only this exact shared repository as a system Git
`safe.directory`; it never enables a wildcard trust rule.

Per-device extraction metadata is stored privately in
`.git/gr-collection-state.json`. It contains hostname/IP, timestamps, status
and a stable failure classification, but no configuration text or credential.
`gr config devices` combines this state with Git history so `LAST EXTRACTED`
does not change meaning when an identical collection creates no commit.

The `jumpserver-ha` project is the sole authority for replication to standby.
It preserves numeric ownership, ACLs and extended attributes and keeps
collection disabled on standby until promotion. Do not configure a second Git
replication path or run the GR timer on both peers.

## Recovery

Inspect `gr collect config status` using the collector configuration and the
system journal. Repair phpIPAM metadata, vault availability, or device access,
then rerun only the affected pool. A failed pool becomes eligible after
`retry_interval`; a successful manual run updates the same state atomically.
