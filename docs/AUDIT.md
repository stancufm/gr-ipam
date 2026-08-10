# SSH session auditing

[Română](AUDIT.ro.md)

`gr` can record every byte sent through an interactive SSH session. Recording includes stdin, stdout and stderr. Consequently, a session file can contain passwords typed at prompts, tokens, private data and commands.

## Configuration

Global defaults in `/etc/gr/config.json` or the user override:

```json
"ssh_audit_enabled": true,
"ssh_audit_dir": "~/.local/state/gr/audit"
```

Enable or disable one connection explicitly:

```bash
gr --ssh --audit core-switch
gr --ssh --no-audit core-switch
```

The per-session option overrides the global setting. Auditing requires an interactive terminal.

## Storage and format

A connection creates:

```text
<audit-dir>/<hostname-or-ip>/<hostname-or-ip>-<UTC-start>.ses
```

Directories have mode `0700`; files have mode `0600`. `.ses` is JSON Lines. The first record contains metadata, every data record contains an elapsed timestamp, stream name and Base64-encoded original bytes, and the final record contains the exit status. This preserves terminal bytes exactly and distinguishes stdin, stdout and stderr.

Browse targets first, then narrow the list to one hostname or IP and select a
session without memorizing storage paths:

```bash
gr audit show
gr audit show core-switch
gr audit show core-switch latest
gr audit show 192.0.2.10 core-switch-20260806T120000.000000Z
```

The first command lists target names, IPs, session counts and the latest UTC
timestamp. The second lists the matching session tokens and exit status.
`latest` replays the newest recording. Direct paths remain supported:

```bash
gr audit show ~/.local/state/gr/audit/core-switch/core-switch-20260806T120000.000000Z.ses
```

Replay defaults to stdout and stderr. Stdin remains stored in the `.ses` file
but is omitted from the normal terminal view because most devices echo typed
characters back on stdout; combining both copies would visually duplicate the
command. Use the forensic or single-stream forms when needed:

```bash
gr audit show core-switch latest --include-stdin
gr audit show core-switch latest --stream stdin
gr audit show core-switch latest --stream stderr
```

Interactive replay automatically uses `less`, or `more` when `less` is not
available. Pipes and redirected output never start a pager. Override the pager
with `GR_PAGER` or `PAGER`, or disable it for one replay:

```bash
gr audit show core-switch latest --no-more
GR_PAGER="less -R" gr audit show core-switch latest
```

## Bash completion

The system installer places completion in `/etc/bash_completion.d/gr`. Start a
new Bash session or load it immediately with:

```bash
source /etc/bash_completion.d/gr
```

Completion includes commands, valid options and values, SSH profiles, audited
hostnames/IPs and the sessions belonging to a selected target. Bash normally
shows ambiguous candidates after two Tab presses. To show them on the first Tab
in a Cisco-like style, set this before Bash completion is loaded:

```bash
export GR_COMPLETION_CISCO_STYLE=1
```

For a persistent setting, put the export before the system Bash-completion
source line in `~/.bashrc`. The completion source can also be printed with
`gr completion bash`.

## Security and operations

Session files are deliberately excluded from Git. They must be protected like credentials: restrict access, encrypt backups, define retention and deletion rules, and never attach them to public issues. Replay exposes captured stdin, including passwords typed with terminal echo disabled. Automated vault passwords passed through `sshpass` do not traverse terminal stdin and are not copied into the audit file unless the remote side displays them.

Recording is flushed after every frame and synchronized on normal session completion. A hard power loss can leave a valid prefix without the final status record.
