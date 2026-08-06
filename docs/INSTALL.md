# Installation and upgrade guide

[Română](INSTALL.ro.md)

## 1. Prepare phpIPAM

Enable the phpIPAM API, create the read-only and write applications, create the
custom fields, and grant the API user access to the required sections. Follow
[`phpipam/SETUP.md`](../phpipam/SETUP.md).

## 2. Prepare the jump server

```bash
sudo apt-get update
sudo apt-get install openssh-client sshpass pass gnupg ca-certificates git
```

`sshpass`, `pass`, and `gnupg` are optional if only interactive SSH or key-based
authentication is used.

## 3. Install from Git

```bash
git clone https://github.com/stancufm/gr-ipam.git
cd gr-ipam
sudo sh install.sh \
  --base-url https://ipam.example.net \
  --username gr-api \
  --app-id gr-app \
  --migration-app-id gr-migrate \
  --enable-timer
```

Use `--ca-file ./organization-ca.pem` for a private CA. A complete prepared
configuration can instead be installed with `--config PATH`.

Installed paths:

| Path | Scope |
|---|---|
| `/usr/local/bin/gr` | global CLI |
| `/usr/local/libexec/gr/` | global operational helpers |
| `/usr/local/share/doc/gr/` | installed documentation |
| `/etc/gr/config.json` | global non-secret configuration |
| `/etc/gr/phpipam-ca.pem` | optional private CA |
| `/var/lib/gr/ieee-vendors/` | shared IEEE database |
| `/etc/systemd/system/gr-vendor-update.*` | optional weekly update |

## 4. Initialize users

Each Linux user stores API credentials, GPG keys, vault entries, state and
reports in their own home directory:

```bash
gr init --configure-auth
gr doctor --api
```

For an encrypted password vault, create a GPG key with an encryption-capable
subkey and then run:

```bash
gr vault init GPG_ID
gr vault set PROFILE
gr vault test PROFILE
```

## Upgrades

```bash
cd gr-ipam
git pull --ff-only
sudo sh install.sh --config /etc/gr/config.json --enable-timer
gr doctor --api
```

The installer includes English and Romanian documentation, and does not modify user credentials, password stores, GPG keys or
SSH keys. Back up `/etc/gr/config.json` before major-version upgrades.

## Test installation

The installer supports a non-root isolated prefix:

```bash
sh install.sh --destdir /tmp/gr-root \
  --base-url https://ipam.example.net --username api-test
```
