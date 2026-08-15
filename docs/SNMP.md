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
      "source_address": "192.0.2.20",
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

`sources` is the approved list rendered into device-side SNMP ACLs.
`source_address` is the local address that Net-SNMP must bind when the management
host is multi-homed or owns a service/VIP address. It is optional, but when set it
must also occur in `sources`. This prevents a test from silently leaving through
an unapproved primary address while the device ACL permits a different local
address. Configure it without touching the vault:

```text
gr config set snmp_profiles.monitoring-v3.source_address 192.0.2.20
```

## Workflow

```text
gr snmp templates --target 192.0.2.10
gr snmp capabilities --ip 192.0.2.10
gr snmp assign --ip 192.0.2.10 --profile monitoring-v3 --apply
gr snmp inventory-sync --report ~/.local/state/gr/device-version/REPORT.json
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22 --apply
gr snmp test --all
gr snmp report --all --mode ports --profile monitoring-v3
```

`inventory-sync` imports only successful model/firmware facts from a version
collector JSON report into address metadata. It is also dry-run until `--apply`.

Only templates with `apply_supported: true`, the requested action in
`supported_actions`, and a reviewed workflow execute. Templates select a
vendor handler in `/usr/local/libexec/gr/snmp-handlers`; the handler owns prompt
recognition, interactive confirmations, CLI-safe secret encoding, exact legacy
cleanup and normalized structural verification. Templates remain declarative
and contain no credentials or site inventory.
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

The Aruba handler creates random, session-only initialization secrets for the
first-time `snmpv3 enable` dialog and removes the temporary `initial` user. The
Cisco Business handler answers the Engine ID confirmation without representing
it as a configuration command. Comware recognizes both EXEC and system-view
prompts. PLANET derives a unique Engine ID from the device MAC held in phpIPAM
and implements the reviewed firmware's unusual PRIV/AUTH order. Dell OS10 treats
an authenticated SNMP probe as the algorithm proof because the CLI masks
localized keys. Handler output is redacted before verification or reporting.

Firmware families with inconsistent AES support or unsafe ACL semantics remain
report/test-only. A template never infers control-plane, interface or global
management ACLs.

`gr snmp capabilities` is a read-only gate for candidate handlers. It enters
configuration mode only to request contextual help from deliberately incomplete
`snmp-server ... ?` commands. A static safety validator refuses any candidate
command that could create an object. Every contextual-help line is cancelled
with Ctrl-C before the interactive client can append a newline, including when
the firmware exposes `<cr>` as a valid completion. The command reports normalized
capabilities rather than a complete configuration. It does not read SNMP
credentials. Candidate templates remain `apply_supported: false` until this
probe and a complete transactional pilot succeed on a representative device.

Cisco Business uses two older CLI dialects that must not be treated as IOS.
Cisco's 250/350 documentation defines firmware 2.x users as
`... v3 auth sha AUTH priv PRIV`; the privacy algorithm is implicit and varies
by model/firmware, so the IOS tokens `priv aes 128` are invalid. Cisco's 220 documentation omits
the `v3` token from the user command and uses `show snmp-server ...` plus
`snmp-server engineid`. The package therefore contains separate 2.x and 220/1.1
candidate handlers with unquoted, whitespace-free password encoding. See the
[Cisco Business 350 SNMP command reference](https://www.cisco.com/c/en/us/td/docs/switches/lan/csbms/CBS_250_350/CLI/cbs-350-cli-/snmp-commands.html)
and [Cisco 220 SNMP command reference](https://www.cisco.com/c/en/us/td/docs/switches/lan/csbss/CBS220/CLI-Guide/b_220CLI/snmp_commands.html).
SG350X/SG350XG firmware 2.5.0.83, SG350X-24PD firmware 2.3.0.130 and
SG350X-48MP firmware 2.4.0.91, plus SG350-28P, SG250X-24P and SG250-08HP
firmware 2.4.0.94, are
represented by narrower SHA/DES templates. The handlers are transactionally
enabled after sw64/sw65/sw67, sw66/sw68/sw69 and sw51 respectively passed local
and LibreNMS authPriv probes, conditional save, final archive and LibreNMS poll.
The 2.4.0.94 pilots on sw20, sw30 and sw31 also validated removal of legacy
communities, post-cleanup probes and token-only Cisco Business removal syntax.
SG220-50P firmware 1.1.3.1 uses the distinct Cisco 220 grammar: views require
`subtree 1 oid-mask all viewtype`, groups require both read and write views,
the user command omits `v3`, and an implicit privacy password creates DES. The
sw15 pilot passed structural verification, both authPriv probes, conditional
save, removal of its legacy community, final archive, phpIPAM association and
LibreNMS poll.
SG220-26P firmware 1.1.3.1 is not dialect-uniform. Sw16 uses `engineid default`,
a view expressed as `iso included`, a group using `read`, a user command without
`v3` whose implicit privacy password creates DES, and the bare `snmp-server`
command to enable the agent. The sw16 pilot passed shadow and LibreNMS authPriv
probes before save, removed one legacy community, passed both probes again,
saved and archived the final state, and completed phpIPAM association and a
successful LibreNMS poll. Read-only contextual help on sw21 and sw37 instead
confirmed the SG220-50P-style `subtree/oid-mask/viewtype` and
`read-view/write-view` grammar. The catalog therefore scopes both SG220-26P
dialects by IP and leaves unknown units blocked instead of guessing from model
and firmware alone.
The sw51 template submits engine-ID confirmations with a newline and waits two
seconds before structural verification, matching the pacing of the successful
manual pilot and allowing the SNMPv3 user database to settle.
Other Cisco Business 2.x combinations remain blocked because their privacy
dialect cannot be inferred from the product family alone.
Contextual help that accepts an implicit privacy password is reported as
`implicit-unverified`; it is not treated as proof of AES because affected
firmware can create a DES user with the same command shape.
Interactive Cisco Business sessions request a 512-column PTY. This prevents
firmware line-editor redraws of long SNMP user commands from resembling fresh
prompts and advancing the transactional command queue prematurely.
Save sessions also recognize only the narrow destination/overwrite prompts
emitted by `copy running-config startup-config`. A failed save now rolls the
unsaved running configuration back; an archive failure after a confirmed save
is reported separately and never misreported as a save failure.
For only these explicitly marked templates, structural verification accepts an
omitted privacy-algorithm label as AES128 when the user and SHA authentication
are present; an explicit DES or no-privacy label is rejected. The shadow and
monitoring-server authPriv tests are still mandatory before save.
Verification scopes authentication and privacy labels to the requested user's
output block, so unrelated no-privacy users cannot affect the decision.
If an explicitly marked implicit-AES template reports an unreliable privacy
label while engine, view, group, user and SHA are all verified, gr may run the
AES128 authPriv tests as a functional probe. It saves only when both the local
and monitoring-server probes succeed; any failure triggers rollback.
For diagnostics, the 2.x handler also verifies `show snmp` reports the agent as
enabled. After a failed AES128 probe it may attempt one authNoPriv read to
distinguish an auth-only user from an unreachable/disabled agent; this result
never authorizes save.
Transactional output includes only a bounded `CLI_SAFE_DIAGNOSTICS` list of
standalone device warnings and errors. Echoed prompt/command lines are always
discarded because terminal repaint fragments may contain only part of a secret
and cannot be made safe by full-value replacement. Complete or sensitive
transcripts are not kept.

The initial catalog incorporates the pilot evidence:

| Family | Handler/action policy | Evidence boundary |
|---|---|---|
| Cisco IOS/IOS XE | transactional SHA/AES128, group ACL | consistent CLI, rollback and save verified |
| Cisco CBS250-8T-D 3.1.1.7 | configure/rotate | six-device rollout and engine confirmation validated; legacy cleanup not exercised |
| Cisco SG/SF 250/350 firmware 2.x | blocked handler, report/test | SG350XG-2F10 2.5.0.83 accepted the documented command but created `Privacy Method: None`; 32-hex and 16-character alphanumeric privacy inputs both failed the local AES128 gate and rolled back without save, before the monitoring test |
| Cisco SG350X/SG350XG 2.5.0.83 | transactional SHA/DES configure/rotate | sw64, sw65 and sw67 passed both authPriv probes; sw65/sw67 also validated prompted save, final archive and LibreNMS poll |
| Cisco SG350X-24PD 2.3.0.130 | transactional SHA/DES configure/rotate | sw66, sw68 and sw69 passed both authPriv probes, prompted save, final archive and LibreNMS poll |
| Cisco SG350X-48MP 2.4.0.91 | transactional SHA/DES configure/rotate | sw51 passed structural SHA/DES verification, both authPriv probes, conditional save, archive, phpIPAM association and LibreNMS poll |
| Cisco SG350-28P, SG250X-24P and SG250-08HP 2.4.0.94 | transactional SHA/DES configure/rotate/cleanup | sw20, sw30 and sw31 passed structural and two-source authPriv verification, conditional save, archive and LibreNMS poll; sw20/sw30 also validated legacy-community removal and post-cleanup probes |
| Cisco SG220-50P firmware 1.1.3.1 | transactional SHA/DES configure/rotate/cleanup | sw15 passed structural and two-source authPriv verification, conditional save, legacy-community cleanup, archive, phpIPAM association and LibreNMS poll |
| Cisco SG220-26P firmware 1.1.3.1, sw16 dialect | IP-scoped transactional SHA/DES configure/rotate/cleanup | sw16 confirmed the simple CLI dialect, passed both authPriv probes before and after legacy cleanup, saved and archived the final state, and completed phpIPAM/LibreNMS association and poll |
| Cisco SG220-26P firmware 1.1.3.1, sw21/sw37 dialect | IP-scoped transactional SHA/DES configure/rotate/cleanup | both targets confirmed the SG220-50P-style subtree/read-view/write-view grammar through non-mutating contextual help; sw21 passed both authPriv probes before and after legacy cleanup, saved/archived the final state, and completed phpIPAM/LibreNMS association and poll |
| Cisco SF220-24P firmware 1.1.3.1 | transactional SHA/DES configure/rotate/cleanup | contextual help on sw17, sw18 and sw19 confirmed one dialect; sw17 passed structural verification, both authPriv probes, conditional save, legacy cleanup and retest, final archive, phpIPAM association and LibreNMS poll |
| Other Cisco Business | report/test | no reviewed model/firmware-specific handler |
| Aruba 2920 WB.15/WB.16 | configure/rotate | adaptive initialization, SHA/AES and v3-only validated |
| HPE Comware 7 | configure/rotate, process ACL | system-view workflow validated on the three pilot devices |
| Dell OS10 | rotate only, no ACL | user replacement and SNMP proof validated; blank-state group/view creation was not |
| PLANET SGS-6310 2.2.0E | configure/rotate, group ACL | privacy/auth ordering and exact process ACL validated; legacy cleanup not exercised |
| FortiOS | report/test | query-source and interface exposure must be reviewed explicitly |

Sites may clone a template and narrow it with `model_regex`, `device_os_regex`
and `os_version_regex`; write support must remain false until its complete apply,
verify, save and rollback behavior is tested on a representative device.
The package catalog is the source for new handler capabilities. Because
`/etc/gr/snmp-templates.json` is intentionally preserved on upgrade, the loader
merges it with the packaged catalog. Newer packaged generations replace stale
generated IDs while retaining site-only IDs; a local catalog at the current
generation may override package IDs.
When `GR_SNMP_TEMPLATES` is set explicitly for a temporary validation or
recovery run, it is authoritative and does not merge the persistent configured
catalog.

## Reports and monitoring

Selectors are `--ip` (repeatable), `--range`, `--subnet`, `--file` (text/CSV) and
`--all`. Add repeatable `--exclude-ip` for OOBM/duplicate paths that must not be
treated as independent managed devices. `--managed-only` limits reports to rows
with a device driver or explicit SNMP/monitoring intent:

```text
gr snmp report --subnet 192.0.2.0/24 --mode inventory
gr snmp report --file devices.csv --mode live
gr snmp report --all --mode offline
gr snmp report --range 192.0.2.1-192.0.2.50 --mode ports
gr snmp report --all --managed-only --exclude-ip 192.0.2.250 --mode inventory
```

Live reports execute template-specific show commands. Offline reports inspect the
global configuration archive. Port reports send an unauthenticated SNMPv3
discovery using a fictitious user; an unknown-user response proves an agent
answered without exposing a credential. UDP silence does not prove that SNMP is
closed and the result is explicitly best-effort.
When `--profile` is supplied, a ports report uses that profile's
`source_address`; otherwise routing selects the source automatically.
Reports are private mode 0600 under `snmp_report_dir` and must never be published.
Each run writes detailed JSON plus a comparison-friendly CSV summary; raw live
CLI output remains only in JSON. Inventory reports include model, OS version,
resolved template, write capability and supported actions so rollout eligibility
can be reviewed without joining another report.

Model/firmware metadata may be imported from multiple `collect-version` reports.
Later reports win for the same IP; the command remains a plan without `--apply`:

```text
gr snmp inventory-sync --report older.json --report newer.json
gr snmp inventory-sync --report older.json --report newer.json --apply
```

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
in the profile and then refreshes status/`last_polled`. The profile `host` must
be an exact phpIPAM hostname or IP with working SSH and sudo metadata. The
poller runs as the `librenms` account from `/opt/librenms`, matching the normal
LibreNMS CLI runtime, and failures report the actionable poller error rather
than the `gr exec` connection banner.
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
