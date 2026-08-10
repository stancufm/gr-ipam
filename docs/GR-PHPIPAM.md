# `gr` — phpIPAM and SSH integration

[Română](GR-PHPIPAM.ro.md)

## Configuration and authentication

Shared configuration is `/etc/gr/config.json`; `~/.config/gr/config.json` overlays user values. Required keys identify the phpIPAM HTTPS endpoint, read application, API user, pinned CA and private credential file. Initialize and test with:

```bash
gr init --configure-auth
gr doctor --api
```

phpIPAM standard custom address fields are `ssh_enabled`, `ssh_user`, `ssh_port`,
`ssh_profile`, `ssh_jump`, `ssh_client`, `device_driver` and `device_vendor`.
Passwords are never stored in phpIPAM. `ssh_profile` selects credentials only;
`device_driver` independently selects device CLI behavior.

## Search and SSH

```bash
gr find <text-or-ip>
gr find <text-or-ip> --details
gr <ip>
gr subnet <cidr>
gr --ssh <target>
gr --ssh --user operator --port 2222 --profile network-admin --driver cisco-ios <target>
```

One match connects automatically; multiple matches open an interactive selector. CLI overrides last only for that connection. `--no-vault` uses the OpenSSH prompt. A `legacy` client is isolated per device.

The compact result table shows phpIPAM `lastSeen` immediately after `STATUS`.

### Cisco Small Business second-stage login

Some Cisco Small Business switches establish SSH and then display their own
`User Name:` and `Password:` prompts. Select this behavior independently in
phpIPAM:

```json
"shared-network": {"password_secret": "gr/shared-network"}
```

Set `ssh_profile` to the required credential profile and set
`device_driver=cisco-small-business`. `gr --ssh` answers the second-stage
prompts and then hands the live CLI to the operator. `gr collect version` uses
the same driver, attempts to disable paging with `terminal datadump`, runs
`show version` for firmware, runs `show system` for model/system data, and exits. Each command
is sent only after the CLI prompt returns. On Sx220 models, `terminal datadump`
may be unsupported, `show version` already contains the model, and two `exit`
commands are required because the first only leaves privileged mode. The injected
password is never written to collect reports.

Collection success is determined when every data command has returned to the
CLI prompt. Cleanup commands are tracked separately, so a device that closes
the connection after the first `exit` is not reported as a false failure.

Dell SmartFabric OS10 devices use `device_driver=dell-os10`. The driver runs
`show version` and parses the OS version and `System Type` independently from
the selected SSH credential profile.

`--details` keeps the compact summary and then prints every field returned by
phpIPAM for each matching address. Fields are sorted, multiline values are
indented and nested JSON values remain readable. The detailed view is read-only
and can also be combined with `--ssh`.

## Complete SSH auditing

Set `ssh_audit_enabled` globally or use `--audit`/`--no-audit` per connection. `ssh_audit_dir` defaults to `~/.local/state/gr/audit`. Each `.ses` recording preserves timestamped stdin, stdout and stderr bytes, including credentials typed while echo is disabled.

```bash
gr --ssh --audit <target>
gr audit show
gr audit show <hostname-or-ip>
gr audit show <hostname-or-ip> latest
gr audit show <hostname-or-ip> latest --no-more
```

Normal replay shows stdout/stderr through an automatic pager and omits stdin to
avoid duplicated terminal echo. `--include-stdin` restores the forensic view,
`--stream` isolates one channel and `--no-more` disables paging. Recordings use
private `0700` directories and `0600` files but remain highly sensitive. See
[SSH session auditing](AUDIT.md).

## Bash completion

The global installer provides command, option and dynamic audit completion for
Bash. Open a new shell or run `source /etc/bash_completion.d/gr`. Set
`GR_COMPLETION_CISCO_STYLE=1` before loading completion to display ambiguous
choices on the first Tab. `gr completion bash` prints the installed script.

## Authentication vault

```bash
gr auth configure
gr auth test
gr vault init <GPG-ID>
gr vault set <profile>
gr vault test <profile>
gr vault list
```

The API credential requires mode `0600`. SSH passwords are encrypted through pass/GPG and supplied to sshpass over an anonymous descriptor.

## Inventory updates

`gr sync` previews generated SSH configuration and optionally `/etc/hosts`; writing requires `--apply`. `gr update IP` previews standard and custom-field changes, then uses the separate write application and GET-verifies applied values. `gr migrate-ssh` imports legacy `[port][user]` metadata and is also dry-run by default.

## Application updates

`gr self-update check` compares the installed version with signed semantic release tags. `gr self-update` verifies, stages, backs up and installs the newest release through a privileged helper. Use `--dry-run` for full verification without installation or `--version vX.Y.Z` to select a release. See [Self-update](UPDATE.md).

## Vendor and operational commands

```bash
sudo gr vendor update-db
gr vendor lookup <mac>
gr vendor sync [--apply]
gr ssh validate [--run] [--ip IP]
gr collect version --ip IP
```

The shared IEEE database is replaced atomically. Synchronization, validation and collection reports are private and must not be committed.

### Collect device version inventory

```bash
gr collect version --all [--vendor VENDOR] [--workers N]
gr collect version --ip IP [--ip IP ...] [--vendor VENDOR] [--workers N]
```

The command reads the phpIPAM address inventory, selects records whose
`device_vendor` matches the requested vendor, requires enabled SSH metadata and
an SSH vault profile, then runs `show version` through the normal or isolated
legacy client selected for each device. It does not modify phpIPAM or device
configuration.

The device driver comes from phpIPAM `device_driver`, not from the credential
profile. An explicit `--driver` overrides it for one interactive connection.
When `device_driver` is blank, Cisco vendor records fall back to `cisco-ios` and
other vendors to `generic`.

Options:

- `--all` selects every eligible address matching `--vendor`;
- `--ip IP` restricts collection to one address and can be repeated; the vendor,
  SSH-enabled and profile requirements still apply;
- `--vendor VENDOR` matches the phpIPAM `device_vendor` value
  case-insensitively; the default is `cisco`;
- `--workers N` controls parallel SSH sessions; the default is `4` and the
  effective value is constrained to `1..12`.

Each run creates a private timestamped directory under
`~/.local/state/gr/device-version/`. It contains one raw `show version` text
file per device, a persistent per-user host-key store and
`<vendor>-show-version-report.json` with parsed model, firmware, OS family,
uptime, serial, system image, ROM, stderr and result status. The parser is
primarily designed for Cisco output; a different vendor is useful only when
its devices support `show version` and compatible output.

### Driver migration from gr 1.x

Version 2 removes runtime use of `session_driver` from credential profiles.
Preview and apply migration before deleting the legacy configuration keys:

```bash
gr migrate-drivers
gr migrate-drivers --apply
```

The migration copies legacy associations into phpIPAM `device_driver`, writes a
private report and GET-verifies every applied value. `--limit` supports a pilot;
`--overwrite` requires `--apply`.

`gr` keeps host keys in `~/.local/state/gr/known_hosts`. New keys are accepted
and reported as `added`; changed keys fail as `changed` and are never replaced
automatically.

Exit status is `0` when every selected device succeeds, `1` when no eligible
device matches and `2` when at least one connection fails or times out.

Browse complete collection runs without remembering report paths:

```bash
gr collect reports
gr collect reports latest
gr collect reports <report-timestamp>
gr collect reports <report-timestamp> --raw
gr collect reports <report-timestamp> --no-more
```

The first command lists one row per collection run with its timestamp, device
count and `success`/`failed`/`timeout` totals. Selecting `latest` or a report ID
shows a device table by default. Its columns are derived from every available
result attribute except `stderr`, `raw_report`, `system_image`, `rom` and `uptime`.
`--raw` displays the original JSON file without transformation. Both formats
use the automatic pager; `--no-more` writes directly. Bash completion proposes
`latest`, every available report ID and the display options. Reports are
discovered under `device_version_dir`, whose default is
`~/.local/state/gr/device-version` and which can be overridden globally or per
user.

## Diagnostics and documentation

`gr doctor --api` checks configuration, permissions, executables, IEEE data and API access. `gr docs --language en` shows this guide; `gr docs --language ro` shows Romanian documentation. Inventory writes remain dry-run until `--apply`.

### Configuration inventory

```bash
gr config show
```

The configuration inventory lists every option supported by the installed
version. For each option it compares the documented default, the global value
from `/etc/gr/config.json`, the active user's override from
`~/.config/gr/config.json`, the normalized effective value and its source.
Required options without a built-in default are marked `<required>`. The
command is read-only and never reads the separate API credential or SSH vault.
