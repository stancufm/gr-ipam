# `gr` — phpIPAM and SSH integration

[Română](GR-PHPIPAM.ro.md)

## Configuration and authentication

Shared configuration is `/etc/gr/config.json`; `~/.config/gr/config.json` overlays user values. Required keys identify the phpIPAM HTTPS endpoint, read application, API user, pinned CA and private credential file. Initialize and test with:

```bash
gr init --configure-auth
gr doctor --api
```

phpIPAM standard custom address fields are `ssh_enabled`, `ssh_user`, `ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client` and `device_vendor`. Passwords are never stored in phpIPAM.

## Search and SSH

```bash
gr find <text-or-ip>
gr <ip>
gr subnet <cidr>
gr --ssh <target>
gr --ssh --user operator --port 2222 --profile network-admin <target>
```

One match connects automatically; multiple matches open an interactive selector. CLI overrides last only for that connection. `--no-vault` uses the OpenSSH prompt. A `legacy` client is isolated per device.

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

## Diagnostics and documentation

`gr doctor --api` checks configuration, permissions, executables, IEEE data and API access. `gr docs --language en` shows this guide; `gr docs --language ro` shows Romanian documentation. Inventory writes remain dry-run until `--apply`.
