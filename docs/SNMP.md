# Template-driven SNMP management

`gr snmp` inventories, tests, plans, configures and monitors SNMP without putting
passphrases in phpIPAM, command-line arguments, reports or session audits. Write
operations are dry-run by default and require `--apply`.

## Inventory model

phpIPAM remains the source of device identity and intent. The installer/schema
helper manages these address custom fields:

- `device_model`: model used by template selectors;
- `snmp_enabled`, `snmp_profile`, `snmp_template`: SNMP intent, vault profile and
  optional per-address template override;
- `monitoring_enabled`, `monitoring_profile`, `monitoring_device_id`: expected
  monitoring association. LibreNMS remains authoritative for current state.

Template selection is deterministic: an address `snmp_template` override wins,
then the most specific matching IP, model, native device OS, OS version, vendor
and driver selector. Native device OS is joined through the address `deviceId`;
selection still works without it if the API account cannot list native devices.
The shipped catalog is `/etc/gr/snmp-templates.json`; package defaults remain in
`/usr/local/share/gr/snmp/templates.json`. Local edits survive upgrades.

Example profiles (names and vault paths are site-defined):

```json
{
  "snmp_profiles": {
    "monitoring-v3": {
      "username": "snmp-monitor",
      "auth_protocol": "SHA",
      "privacy_protocol": "AES",
      "sources": ["192.0.2.20", "192.0.2.21", "192.0.2.22"],
      "auth_secret": "gr/snmpv3/monitoring-v3/auth",
      "privacy_secret": "gr/snmpv3/monitoring-v3/priv"
    }
  },
  "monitoring_profiles": {
    "librenms": {
      "type": "librenms",
      "url": "https://monitoring.example.net/api/v0",
      "ca_file": "/etc/ssl/certs/ca-certificates.crt",
      "token_secret": "gr/monitoring/librenms/token"
    }
  }
}
```

Store values with `pass insert`; only secret names belong in configuration.
Interactive credentials use `--prompt-credentials` and are never accepted as
plain command-line options. Net-SNMP receives credentials through a mode-0600
temporary configuration, not `-A`/`-X` process arguments.

## Workflow

```text
gr snmp templates --target 192.0.2.10
gr snmp assign --ip 192.0.2.10 --profile monitoring-v3 --apply
gr snmp inventory-sync --report ~/.local/state/gr/device-version/REPORT.json
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22 --apply
gr snmp test --all
```

`inventory-sync` imports only successful model/firmware facts from a version
collector JSON report into address metadata. It is also dry-run until `--apply`.

Only templates with `apply_supported: true` and a reviewed workflow execute.
Before every applied change, the current running configuration must be collected
successfully into the global Git archive. Configuration is then applied to
running state, SNMPv3 is tested, and only then is it saved. Failure triggers
template rollback. After save, the final configuration is collected again.
Approved source addresses come from the SNMP profile or explicit `--source`
options. There is no permissive/default source. A configure operation refuses
pre-existing managed object names instead of risking destructive rollback.
Rotation additionally requires
`--previous-profile`, so rollback can recreate the previous user. Cisco IOS
legacy cleanup discovers exact community lines without displaying them, removes
them, tests v3, and can restore the exact lines before save.

Firmware families with interactive initialization, inconsistent AES support,
masked localized keys or unsafe ACL semantics are intentionally report/test-only
until a derived model/OS template and handler are reviewed. A template never
infers control-plane, interface or global management ACLs.

The initial catalog incorporates the pilot evidence:

| Family | Initial policy | Reason |
|---|---|---|
| Cisco IOS/IOS XE | transactional SHA/AES128, group ACL | consistent CLI, rollback and save verified |
| Cisco CBS250 | report/test | engine-ID confirmations and syntax vary by firmware |
| Cisco SG/SF legacy | report/test | several releases created users but did not validate AES |
| ArubaOS-Switch 15/16 | report/test | `snmpv3 enable` has firmware-dependent secret dialogs |
| HPE Comware 7 | report/test | needs a dedicated system-view transaction handler |
| Dell OS10 | report/test | no process ACL on tested firmware; localized keys are masked |
| PLANET SGS | report/test | nonstandard order and group ACL syntax require a derived handler |
| FortiOS | report/test | query-source and interface exposure must be reviewed explicitly |

Sites may clone a template and narrow it with `model_regex`, `device_os_regex`
and `os_version_regex`; write support must remain false until its complete apply,
verify, save and rollback behavior is tested on a representative device.

## Reports and monitoring

Selectors are `--ip` (repeatable), `--range`, `--subnet`, `--file` (text/CSV) and
`--all`:

```text
gr snmp report --subnet 192.0.2.0/24 --mode inventory
gr snmp report --file devices.csv --mode live
gr snmp report --all --mode offline
gr snmp report --range 192.0.2.1-192.0.2.50 --mode ports
```

Live reports execute template-specific show commands. Offline reports inspect the
global configuration archive. Port reports send an unauthenticated SNMPv3
discovery using a fictitious user; an unknown-user response proves an agent
answered without exposing a credential. UDP silence does not prove that SNMP is
closed and the result is explicitly best-effort.
Reports are private mode 0600 under `snmp_report_dir` and must never be published.
Each run writes detailed JSON plus a comparison-friendly CSV summary; raw live
CLI output remains only in JSON.

LibreNMS validation compares device presence, `status`, `last_polled` and the
phpIPAM address `lastSeen`:

```text
gr snmp monitor --all --monitoring-profile librenms
gr snmp monitor --ip 192.0.2.10 --monitoring-profile librenms --add
gr snmp monitor --ip 192.0.2.10 --monitoring-profile librenms --add --apply
gr snmp monitor --all --monitoring-profile librenms --profile monitoring-v3 --sync-credentials
gr snmp monitor --ip 192.0.2.10 --monitoring-profile librenms --poll --apply
```

The first command is read-only. `--add` remains a plan until `--apply`; successful
associations are written back to phpIPAM. Periodic tests and reports may be run by
an external scheduler. `--sync-credentials --apply` updates the SNMPv3 fields of
existing LibreNMS devices; the next poll is the authoritative verification.
`--poll --apply` runs that poll immediately through the monitoring host stored
in the profile and then refreshes status/`last_polled`.
Credential rotation is deliberately an explicit reviewed operation: configure a
new vault profile, run `rotate --previous-profile OLD --profile NEW` as a dry-run,
apply in a maintenance window, synchronize LibreNMS, then assign the new profile
in phpIPAM. This command chain is suitable for a site scheduler, but `--apply`
must never be enabled without change-window controls and failure notification.

## Installation and validation

The installer requires Debian, Python 3.7+, Net-SNMP tools, SSH/sshpass, pass/GPG,
the isolated legacy SSH client and the existing phpIPAM prerequisites. With
`--phpipam-config`, it idempotently creates all custom fields. After install run:

```text
gr doctor --api
gr snmp templates
gr snmp report --ip 192.0.2.10 --mode inventory
```

`gr doctor` validates `snmpget` and the template schema. Back up the global
configuration archive before a rollout, start with one device, and verify both
the SNMP test and LibreNMS poll before expanding a batch.
