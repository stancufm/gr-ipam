# gr-ipam

[Română](README.ro.md)

`gr-ipam` is a multi-user CLI for Debian jump servers that use phpIPAM as the
source of truth for network inventory and SSH connection metadata.

It can search addresses, connect through SSH, keep device passwords in a
per-user encrypted vault, maintain a shared IEEE OUI database, synchronize
normalized vendor information, validate switch access and collect device
version inventory.

## Main properties

- phpIPAM remains the source of truth; no fork or database schema patch is used.
- SSH metadata is stored in standard phpIPAM custom address fields.
- API and SSH passwords remain private to each jump-server user.
- Read and write API applications are separated.
- Every write operation is a dry-run unless `--apply` is explicitly supplied.
- `/etc/hosts` generation is disabled by default.
- Legacy SSH is opt-in per device and never weakens the normal SSH client.
- Complete SSH terminal auditing is configurable globally and per session.

## Requirements

- Debian 10 or newer with Python 3.7+
- phpIPAM available through HTTPS
- `openssh-client`
- optional: `sshpass`, `pass`, and `gnupg` for encrypted password automation
- optional: an `/usr/bin/ssh1` compatibility wrapper for legacy devices
- systemd for automatic IEEE registry updates

## Installation from Git

```bash
git clone https://github.com/stancufm/gr-ipam.git
cd gr-ipam
sudo sh install.sh \
  --base-url https://ipam.example.net \
  --username gr-api \
  --ca-file ./organization-ca.pem \
  --enable-timer
```

If phpIPAM uses a certificate signed by a public CA, omit `--ca-file`; the
installer uses Debian's system trust store.

Prepare phpIPAM using [the phpIPAM guide](phpipam/SETUP.md). Then initialize
each jump-server user independently:

```bash
gr init --configure-auth
gr doctor --api
```

## Typical usage

```bash
gr find core-switch
gr --ssh core-switch
gr --ssh --audit core-switch
gr update 192.0.2.10 --ssh-enabled yes --ssh-user operator --apply
gr vendor lookup e8:d3:22:00:00:01
sudo gr vendor update-db
gr vendor sync
gr ssh validate
gr ssh validate --run --ip 192.0.2.10
gr collect version --ip 192.0.2.10
gr self-update check
```

## Documentation

- [Installation and upgrades](docs/INSTALL.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security model](docs/SECURITY-MODEL.md)
- [SSH session auditing](docs/AUDIT.md)
- [Signed self-update](docs/UPDATE.md)
- [Complete command guide](docs/GR-PHPIPAM.md)
- [phpIPAM preparation](phpipam/SETUP.md)
- [Contributing](CONTRIBUTING.md)

## Project status

Version `1.2.0` has been tested through an isolated `DESTDIR` installation on
Debian. The package contains no credentials, private keys, inventory exports or
organization-specific addressing.

## License

This project is available under the [MIT License](LICENSE).
