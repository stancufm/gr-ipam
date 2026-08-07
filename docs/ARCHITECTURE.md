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

### Operational helpers

- `libexec/validate-ssh` validates `sw*` devices concurrently and writes a JSON
  audit report.
- `libexec/collect-version` runs `show version`, preserves raw output and emits
  parsed JSON inventory.

Both helpers load the installed `gr` module so API, metadata, profiles, vault
and legacy-client behavior remain consistent.

`libexec/gr-update` is a root-only transaction helper reached through `gr self-update`. It verifies a signed release tag against a pinned public key, performs an isolated install, backs up system files and rolls back a failed live installation.

### Configuration layers

`/etc/gr/config.json` contains shared, non-secret settings. An optional
`~/.config/gr/config.json` overlays only user-specific keys; `ssh_profiles` is
merged by profile name. `--config PATH` deliberately selects one file without
layering.

### Credential boundaries

- phpIPAM password: `~/.config/gr/credentials`, mode `0600`;
- SSH passwords: `~/.password-store/gr/`, encrypted by the user's GPG key;
- SSH keys and known hosts: owned and managed by the Linux user;
- reports: `~/.local/state/gr/`, directory mode `0700`, files mode `0600`.

No credential is stored in phpIPAM. phpIPAM contains only the profile name that
selects a secret in the current user's vault.

### phpIPAM integration

The tool uses the official HTTPS API and standard custom IP-address fields. A
read-only application serves lookup and inventory. A second application is
selected for explicit write operations. This avoids phpIPAM source changes and
survives normal application upgrades.

### SSH selection

For each address, `gr` resolves user, port, profile, jump host and client from
phpIPAM. Missing user defaults to the current Linux user; missing port defaults
to 22. CLI overrides affect only the current connection. `legacy` selects the
separate `ssh1` wrapper, keeping weak algorithms isolated per device.

### Shared vendor registry

IEEE MA-L, MA-M and MA-S registries are downloaded atomically into a root-owned,
world-readable cache. Lookup uses longest-prefix matching. The weekly systemd
timer updates the shared database once for all users.

## Data flows

### Search and SSH

1. Authenticate to phpIPAM using the current user's API credential.
2. Find all matching address records, including duplicates.
3. Resolve SSH metadata and defaults.
4. Select automatically if exactly one target exists; otherwise prompt.
5. Obtain the selected profile's secret from the current user's GPG vault.
6. If enabled, relay the PTY through a lossless stdin/stdout/stderr recorder.
7. Execute OpenSSH or the isolated legacy wrapper against the IP address.

### Updates

1. Fetch the exact address record.
2. Build and display the proposed field changes.
3. Stop unless `--apply` is supplied.
4. Use the write application, submit the update, and GET-verify the result.
5. Save a private audit report where applicable.
