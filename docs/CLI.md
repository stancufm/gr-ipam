# GR command index

This is the installed entry point for GR documentation. Use `gr COMMAND --help`
for syntax and `gr docs TOPIC` for the complete guide behind a workflow.

## Safety model

- phpIPAM is the inventory and intent source of truth.
- Inventory, SNMP and monitoring writes are previews until `--apply` is used.
- Weak SSH algorithms are isolated in `/usr/bin/ssh1` and selected per address
  with `ssh_client=legacy`; GR never enables them globally.
- SSH and SNMP passwords are read from the current identity's encrypted Vault
  and are not placed in process arguments.
- `gr device probe` never creates a session transcript and accepts only
  read-only commands, session controls and contextual help ending in `?`.

## Inventory and access

| Command | Purpose |
|---|---|
| `gr find TERMS` | Search phpIPAM by IP, hostname, description, owner, MAC or port. |
| `gr --ssh TERMS` | Select a match and open its driver-aware interactive SSH session. |
| `gr subnet CIDR` | List phpIPAM addresses in a subnet. |
| `gr update IP ...` | Preview or apply hostname, SSH, driver and vendor metadata. |
| `gr driver list` | Show implemented drivers and their collection commands. |
| `gr driver detect ...` | Detect or apply a driver from collected inventory. |
| `gr vendor ...` | Inspect/update IEEE data and reconcile phpIPAM vendors. |
| `gr ssh validate` | List or test SSH metadata for switch targets. |

## Commands and device CLIs

`gr exec TARGET -- COMMAND` runs a normal SSH remote command, such as a Linux
shell command. Appliances that require a second interactive login cannot accept
an SSH exec request; use the native driver-aware probe instead:

```console
gr device probe legacy-switch \
  --command "terminal datadump" \
  --command "show logging" \
  --command "configure terminal" \
  --command "logging ?" \
  --command "end"
```

Contextual help is rendered and cancelled with Ctrl-C without executing the
editable line. Firmware that retains it is recovered with Ctrl-U/Ctrl-C, still
without a newline. GR waits for the real prompt between commands, declines an
optional Cisco Business password-expiry change, applies bounded session/idle
timeouts and redacts the Vault password from returned output.

## Collection and archives

| Command | Purpose |
|---|---|
| `gr collect version ...` | Collect model, firmware and version evidence. |
| `gr collect reports [latest]` | Browse saved version reports. |
| `gr collect config ...` | Archive normalized running configurations. |
| `gr collect config pools` | Validate scheduled pool definitions. |
| `gr collect config status` | Show pool scheduling and recent state. |
| `gr config devices/history/view` | Browse extraction time, change history and archived configurations. |

Complete scheduling guide: `gr docs config-pools`.

## SNMP

Start with `gr snmp --help` and `gr docs snmp`.

| Command | Purpose |
|---|---|
| `gr snmp templates [--target TARGET]` | List templates or resolve one target. |
| `gr snmp capabilities ...` | Probe a candidate CLI dialect using safe contextual help. |
| `gr snmp test ...` | Test SNMP credentials without modifying a device. |
| `gr snmp report ...` | Produce offline, ports, inventory or live reports. |
| `gr snmp assign ...` | Preview/apply SNMP intent fields in phpIPAM. |
| `gr snmp inventory-sync ...` | Import model/OS/vendor evidence from version reports. |
| `gr snmp configure ...` | Plan/apply a transactional SNMPv3 template. |
| `gr snmp rotate ...` | Rotate managed SNMPv3 credentials transactionally. |
| `gr snmp cleanup ...` | Remove legacy SNMP v1/v2 configuration transactionally. |
| `gr snmp monitor ...` | Compare/reconcile phpIPAM devices with LibreNMS. |

`configure`, `rotate`, `cleanup`, `assign` and monitoring mutations remain
dry-run until `--apply` is explicitly supplied.

## Configuration, Vault and diagnostics

| Command | Purpose |
|---|---|
| `gr config show` | Show default/global/user/effective configuration. |
| `gr config set/unset ...` | Manage supported settings without editing JSON. |
| `gr init --configure-auth` | Initialize private state and phpIPAM credentials. |
| `gr doctor --api` | Validate installation, Vault prerequisites and phpIPAM. |
| `gr vault list/set/test/reset-agent` | Manage encrypted SSH secrets. |
| `gr audit show ...` | Browse intentionally recorded interactive sessions. |
| `gr self-update ...` | Verify and install signed releases. |

## Documentation topics

```console
gr docs list
gr docs guide
gr docs snmp
gr docs config-pools
gr docs audit
gr docs architecture
gr docs security
gr docs install
gr docs update
gr docs snmp --language ro
```
