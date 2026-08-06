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

Replay all recorded bytes with:

```bash
gr audit show ~/.local/state/gr/audit/core-switch/core-switch-20260806T120000.000000Z.ses
```

## Security and operations

Session files are deliberately excluded from Git. They must be protected like credentials: restrict access, encrypt backups, define retention and deletion rules, and never attach them to public issues. Replay exposes captured stdin, including passwords typed with terminal echo disabled. Automated vault passwords passed through `sshpass` do not traverse terminal stdin and are not copied into the audit file unless the remote side displays them.

Recording is flushed after every frame and synchronized on normal session completion. A hard power loss can leave a valid prefix without the final status record.
