# gr-ipam development guidance

## Scope and compatibility

- Keep the CLI dependency-free and compatible with Python 3.7 or newer.
- Preserve Debian 10 compatibility unless a major release explicitly changes it.
- Treat phpIPAM as the inventory and hostname source of truth.
- Use standard phpIPAM custom fields; do not patch phpIPAM source or schema directly.

## Safety

- Never commit real credentials, tokens, private keys, internal CA material,
  network scans, inventory exports, validation reports, or internal addressing.
- Keep read and write API applications separate.
- All write operations must remain dry-run by default and require `--apply`.
- Never broaden legacy SSH algorithms globally; select the isolated legacy
  client only through per-device metadata.
- Do not deploy to a production jump server unless the user explicitly asks.
- Do not add broad passwordless sudo rules. Administrative operations must be
  explicit and reviewable.

## Workflow

- Start changes from an up-to-date `main` on a `codex/<short-name>` branch.
- Keep commits focused and update documentation with behavior changes.
- Before committing, run `.codex/setup.sh` and `git diff --check`.
- Push the branch and open a pull request; merge only after GitHub Actions pass.
- Use semantic version tags and GitHub releases for user-facing versions.

## Project layout

- `bin/gr`: main CLI and shared phpIPAM/SSH logic.
- `libexec/`: operational helpers invoked by the main CLI.
- `examples/`: configuration templates without real infrastructure values.
- `phpipam/`: phpIPAM preparation documentation.
- `systemd/`: shared IEEE database update units.
- `docs/`: installation, architecture, security, and command documentation.

## Verification

- Parse every Python entry point with the oldest supported grammar.
- Validate shell syntax with `sh -n install.sh` and `sh -n .codex/setup.sh`.
- Exercise installation through `--destdir`; never overwrite the active system
  installation during an ordinary development test.
- Scan staged content for secrets and organization-specific values before push.
