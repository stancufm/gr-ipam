# Architecture

[Română](ARCHITECTURE.ro.md)

## Overview

```text
Linux user
   |
   v
/usr/local/bin/gr --------------------+---------------------+
   |                                  |                     |
   v                                  v                     v
phpIPAM HTTPS API              per-user GPG/pass      global IEEE DB
inventory + SSH metadata       encrypted secrets      /var/lib/gr
   |                                  |                     |
   +-------------------+--------------+                     |
                       v                                    |
                 OpenSSH / ssh1 <---------------------------+
                       |
                       v
                 managed devices
```

## Components

### Main CLI

`bin/gr` is dependency-free Python and provides search, SSH connection,
phpIPAM metadata updates, vendor lookup/synchronization, configuration checks,
documentation and vault management.

The native interactive-device executor also lives in `bin/gr`. It owns the
PTY, second-stage login state machine, prompt-gated command queue, contextual
help cancellation, bounded deadlines and output redaction. `gr device probe`,
version collection and configuration collection reuse this executor instead of
nesting external `expect`, Paramiko or Netmiko sessions.

### Operational helpers

- `libexec/validate-ssh` validates `sw*` devices concurrently and writes a JSON
  audit report.
- `libexec/collect-version` runs `show version`, preserves raw output and emits
  parsed JSON inventory.
- `libexec/collect-config` runs the driver's configuration commands and commits
  changed normalized configurations to the global private Git archive.
- `libexec/config-collection-pools` resolves declarative phpIPAM-backed pools,
  serializes scheduled runs, and delegates each eligible set to
  `collect-config`.
- `libexec/snmp-manager` resolves model/OS templates, inventories and tests;
- `libexec/snmp-handlers` contains reviewed interactive session and normalized
  verification behavior, separate from declarative SNMP templates
  SNMP, gates transactional writes, and reconciles phpIPAM with LibreNMS.

The helpers load the installed `gr` module so API, metadata, credential
profiles, device drivers, vault and legacy-client behavior remain consistent.

The device-driver registry currently includes generic, Cisco IOS, adaptive
Cisco Small Business, Dell SmartFabric OS10, HPE ArubaOS-Switch/ProVision and
HPE Comware 7 behaviors. Credential profiles are never used to infer the
device driver.
Driver autodetection is report-driven: the newest successful inventory evidence
is preferred, unambiguous vendor metadata is a secondary source, and unknown
devices resolve to `generic`. Applied changes use the dedicated write API and
GET verification.

`libexec/gr-update` is a root-only transaction helper reached through `gr self-update`. It verifies a signed release tag against a pinned public key, performs an isolated install, backs up system files and rolls back a failed live installation.

### Configuration layers

`/etc/gr/config.json` contains shared, non-secret settings. An optional
`~/.config/gr/config.json` overlays only user-specific keys; `ssh_profiles`,
`snmp_profiles` and `monitoring_profiles` are merged by profile name;
`config_collection` is shallow-merged so a user may override scheduler state
without duplicating shared pool definitions.
`--config PATH` deliberately selects one file without
layering.

### Credential boundaries

- phpIPAM password: `~/.config/gr/credentials`, mode `0600`;
- SSH passwords: `~/.password-store/gr/`, encrypted by the user's GPG key;
- SNMP AUTH/PRIV values and monitoring API tokens: named `pass` entries;
- SSH keys and persistent gr known hosts: owned and managed by the Linux user;
- reports: `~/.local/state/gr/`, directory mode `0700`, files mode `0600`.
- scheduled collector: locked system account `gr-collector`, dedicated
  `/etc/gr/collector.json`, private `/var/lib/gr-collector`, and separately
  provisioned least-privilege API/vault material;
- device configuration history: `/var/lib/gr/config-archive`, mode `2770`,
  owned by `gr-collector:gr-config` and readable only by authorized members.

No credential is stored in phpIPAM. phpIPAM contains only the profile name that
selects a secret in the current user's vault. The independent `device_driver`
field selects prompt handling, operational commands and output parsing.

### phpIPAM integration

The tool uses the official HTTPS API and standard custom IP-address fields. A
read-only application serves lookup and inventory. A second application is
selected for explicit write operations. This avoids phpIPAM source changes and
survives normal application upgrades.

SNMP address fields store desired enablement, template/profile association and
the external monitoring device identifier, never secrets. Native device OS is
joined by `deviceId` when permitted. LibreNMS is authoritative for current
presence, status and last poll; phpIPAM remains authoritative for inventory and
`lastSeen`.

### SNMP transaction boundary

The site-editable template catalog is data, while reviewed workflow handlers
are code. A template cannot enable writes by commands alone: it must opt into a
known handler. Plans are always available, but apply requires `--apply`. The
handler changes running state, performs structural and authenticated checks,
saves only after success, and otherwise executes rollback. Reports and tests
never create terminal audit transcripts containing newly configured secrets.

### SSH selection

For each address, `gr` resolves user, port, profile, jump host and client from
phpIPAM. Missing user defaults to the current Linux user; missing port defaults
to 22. CLI overrides affect only the current connection. `legacy` selects the
separate `ssh1` wrapper, keeping weak algorithms isolated per device.

### Shared vendor registry

IEEE MA-L, MA-M and MA-S registries are downloaded atomically into a root-owned,
world-readable cache. Lookup uses longest-prefix matching. The weekly systemd
timer updates the shared database once for all users.

### Global configuration archive

Drivers own both version and running-configuration commands. Authentication
uses the initiating operator's private vault for interactive runs and the
dedicated collector vault for scheduled runs. Normalized configurations are
written under a lock stored inside `.git` to
`/var/lib/gr/config-archive/devices/`. Git creates one collection commit only
when staged content differs from HEAD. A private, untracked
`.git/gr-collection-state.json` sidecar records each IP's last attempt, last
successful extraction and status even when content is unchanged. Browsing uses
`gr config devices/history/view`; GR configures no archive remote.

The system timer runs as `gr-collector`, is disabled by default, and is fenced
by the HA active marker. The independent `jumpserver-ha` project replicates the
archive and collector identity data; standby must never schedule collection
before promotion.

## Data flows

### Search and SSH

1. Authenticate to phpIPAM using the current user's API credential.
2. Find all matching address records, including duplicates.
3. Resolve SSH metadata and defaults.
4. Select automatically if exactly one target exists; otherwise prompt.
5. Obtain the selected profile's secret from the current user's GPG vault.
6. If enabled, relay the PTY through a lossless stdin/stdout/stderr recorder.
7. Execute OpenSSH or the isolated legacy wrapper against the IP address.
8. Interpret `sshpass` status 5 as a rejected Vault credential. Generic targets
   may be retried once through an operator-approved OpenSSH prompt; automated
   device drivers stop until their Vault profile is corrected.
9. For every other non-zero result, classify recorded stderr evidence and emit
   a secret-free `SSH_DIAGNOSTIC`. Normal clients accept only first-seen host
   keys into the private gr store, reject changed keys, and use bounded connect
   attempts plus keepalives.

### Updates

1. Fetch the exact address record.
2. Build and display the proposed field changes.
3. Stop unless `--apply` is supplied.
4. Use the write application, submit the update, and GET-verify the result.
5. Save a private audit report where applicable.
