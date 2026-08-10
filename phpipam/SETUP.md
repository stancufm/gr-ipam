# phpIPAM preparation

[Română](SETUP.ro.md)

Enable the API in phpIPAM and create two API applications:

1. a permanent read-only application (default ID `gr-app`);
2. a write-enabled application (default ID `gr-migrate`) used only by commands
   that are explicitly applied.

Create a local API user, grant it access to the required sections/subnets and
verify that its authentication backend works through the API. Start with the
least privileges needed; write access is required only for metadata updates.

Under **Administration → Custom fields → IP addresses**, create:

| Field | Type | Suggested size | Purpose |
|---|---:|---:|---|
| `ssh_enabled` | tinyint / boolean | 1 | Enable SSH for this address |
| `ssh_user` | varchar | 64 | Login user; blank means current jump-server user |
| `ssh_port` | integer | — | Port; blank means 22 |
| `ssh_profile` | varchar | 64 | Per-user vault profile name |
| `ssh_jump` | varchar | 255 | Optional ProxyJump target |
| `ssh_client` | varchar | 16 | `normal` or `legacy` |
| `device_driver` | varchar | 64 | Device CLI behavior, independent from credentials |
| `device_vendor` | varchar | 64 | Normalized vendor inferred from MAC OUI |

phpIPAM returns these through the API as `custom_ssh_enabled`,
`custom_ssh_user`, and so on. No schema fork or source-code modification is
required: these are standard phpIPAM custom fields and survive normal upgrades.

For a new installation, the package provides an idempotent helper that performs
the same standard column creation from the phpIPAM application server. Back up
the database, then run it locally with the path to `config.php` if different:

```bash
sudo /usr/local/share/gr/phpipam/ensure-custom-fields.php \
  /var/www/html/phpipam/config.php
```

It creates only missing fields, validates the SQL family of existing fields,
uses a database advisory lock, and aborts on incompatible definitions. It does
not store or print database credentials. Afterwards, `gr doctor --api` on the
jump server validates that all eight fields are visible through the API.

Recommended first validation:

```bash
gr auth test
gr find known-device
gr update 192.0.2.10 --ssh-enabled yes --ssh-user operator --ssh-port 22
```

The last command is a dry-run until `--apply` is added.
