# Installation and upgrade guide

[Română](INSTALL.ro.md)

## 1. Prepare phpIPAM

Enable the phpIPAM API, create the read-only and write applications, create the
custom fields, and grant the API user access to the required sections. Follow
[`phpipam/SETUP.md`](../phpipam/SETUP.md).

On a new phpIPAM server, copy the packaged
`phpipam/ensure-custom-fields.php` helper to the application host and run it
there after a database backup. Schema creation cannot be performed through the
phpIPAM address API and database credentials are deliberately never copied to
the jump server. `gr doctor --api` is the mandatory post-install validation and
fails when any required field is absent.

The idempotent preparation creates and validates all required address fields
(`ssh_*`, `device_driver`, `device_vendor`, `os_version`),
`devices.device_os`, and the native `Server` device type. On the phpIPAM
application host, after a database backup, it can be integrated into install:

```console
sudo ./install.sh --config /etc/gr/config.json \
  --phpipam-config /var/www/html/phpipam/config.php
```

Run the installer on a jump server without `--phpipam-config`; `gr doctor
--api` then performs the remote address-field validation.

## 2. Prepare the jump server

```bash
sudo apt-get update
sudo apt-get install python3 openssh-client sshpass pass gnupg ca-certificates git bash-completion less systemd snmp
```

All dependencies are mandatory so every documented feature is available. The
separately packaged legacy client must also be installed as `/usr/bin/ssh1`.
The Python entry points retain Python 3.7 grammar compatibility and are also
validated on Python 3.13 without deprecated UTC or module-loader APIs.
The installer verifies the complete list before modifying the system. If Debian
packages are missing it aborts and prints the exact `apt-get` command. To let the
installer install missing packages explicitly, add `--install-dependencies`.

## 3. Install from Git

```bash
git clone https://github.com/stancufm/gr-ipam.git
cd gr-ipam
sudo sh install.sh \
  --base-url https://ipam.example.net \
  --username gr-api \
  --app-id gr-app \
  --migration-app-id gr-migrate \
  --install-dependencies \
  --enable-timer
```

Use `--ca-file ./organization-ca.pem` for a private CA. A complete prepared
configuration can instead be installed with `--config PATH`.

The official package includes and installs the project's public release key. To override the repository for a maintained fork:

```bash
sudo sh install.sh --config /etc/gr/config.json \
  --update-repository https://github.com/stancufm/gr-ipam.git
```

Installed paths:

| Path | Scope |
|---|---|
| `/usr/local/bin/gr` | global CLI |
| `/usr/local/libexec/gr/` | global operational helpers |
| `/usr/local/share/doc/gr/` | installed documentation |
| `/etc/gr/config.json` | global non-secret configuration |
| `/etc/gr/collector.json` | dedicated scheduled-collector configuration, mode `0640` |
| `/etc/gr/phpipam-ca.pem` | optional private CA |
| `/etc/gr/update.json` | root-owned HTTPS release repository |
| `/etc/gr/release-key.asc` | pinned public release-signing key |
| `/etc/bash_completion.d/gr` | global Bash completion, including dynamic audit candidates |
| `/var/lib/gr/ieee-vendors/` | shared IEEE database |
| `/etc/systemd/system/gr-vendor-update.*` | optional weekly update |
| `/etc/systemd/system/gr-config-collect.*` | disabled-by-default system collector units |
| `/var/lib/gr-collector/` | private home and scheduler state for `gr-collector` |

## 4. Initialize users

Each Linux user stores API credentials, GPG keys, vault entries, state and
reports in their own home directory:

```bash
gr init --configure-auth
gr doctor --api
```

`gr init` also creates the private persistent host-key store at
`~/.local/state/gr/known_hosts`.

Scheduled configuration collection is not activated by installation. Configure
and validate pools first; activation and HA guidance are in
`CONFIG-COLLECTION-POOLS.md`.

The installer creates the locked `gr-collector` system account and installs a
starter `/etc/gr/collector.json`. Provision only the API and encrypted SSH
credentials required by scheduled pools for this identity. A prepared service
configuration can be installed with `--collector-config PATH`. The service
must not reuse a human operator's home, private SSH keys, or interactive GPG
agent. The timer remains disabled until an administrator explicitly enables it.

The installer creates the global configuration archive and its authorization
group. Grant access explicitly, then start a new login session:

```bash
sudo usermod -aG gr-config OPERATOR
```

`/var/lib/gr/config-archive` is mode `2770`, owned by
`gr-collector:gr-config`. Device configurations may contain secrets; do not
grant this group broadly. In an HA deployment, replication is owned by the
separate `jumpserver-ha` mechanism; do not add a competing Git remote.

### Upgrading from gr 1.x to 2.x

Create the standard phpIPAM address custom field `device_driver`, install 2.x,
then migrate before removing legacy `session_driver` keys from user/global
credential profiles:

```bash
gr migrate-drivers
gr migrate-drivers --apply
gr doctor --api
```

Credential profiles retain only secrets/identity files. Device CLI behavior is
stored per address in phpIPAM.

For an encrypted password vault, create a GPG key with an encryption-capable
subkey and then run:

```bash
gr vault init GPG_ID
gr vault set PROFILE
gr vault test PROFILE
# Recovery only when an abandoned pinentry blocks the current user's agent:
gr vault reset-agent PROFILE
```

## Signed upgrades

After the release key is installed:

```bash
gr self-update check
gr self-update --dry-run
gr self-update
```

The updater verifies the signed tag, stages the package, creates a backup and rolls back on failure. See [Signed self-update](UPDATE.md).

## Manual upgrades

```bash
cd gr-ipam
git pull --ff-only
sudo sh install.sh --config /etc/gr/config.json --enable-timer
gr doctor --api
```

The installer includes English and Romanian documentation, and does not modify user credentials, password stores, GPG keys or
SSH keys. Back up `/etc/gr/config.json` before major-version upgrades.

`--destdir` installations deliberately skip host dependency checks because they
are package/test staging operations and do not activate system services.

Open a new Bash session after installation, or run
`source /etc/bash_completion.d/gr`. Set `GR_COMPLETION_CISCO_STYLE=1` before
completion is loaded to display ambiguous candidates on the first Tab.

## Test installation

The installer supports a non-root isolated prefix:

```bash
sh install.sh --destdir /tmp/gr-root \
  --base-url https://ipam.example.net --username api-test
```
