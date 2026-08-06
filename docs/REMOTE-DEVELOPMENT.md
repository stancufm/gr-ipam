# Remote development with Codex

The recommended development environment is a dedicated Linux account on a
jump server or development host. The Codex desktop app connects through SSH and
starts the remote Codex app server using the account's login shell. Repository
files, commands, credentials, permissions and tools remain on the Linux host.

## Host preparation

1. Install Codex CLI for the unprivileged development user and ensure `codex`
   is available on `PATH` in a login shell.
2. Authenticate with `codex login --device-auth` on headless hosts.
3. Clone this repository into a user-owned development directory.
4. Give Git only repository-scoped credentials. A dedicated GitHub deploy key
   with write access is suitable for a single repository.
5. Confirm `.codex/setup.sh` succeeds before opening the project.

## Desktop SSH entry

Use one concrete SSH alias; pattern-only hosts are not discovered:

```sshconfig
Host jump-server-codex
    HostName jump.example.net
    Port 22
    User developer
    IdentityFile ~/.ssh/id_ed25519_jump_server
    IdentitiesOnly yes
```

Confirm `ssh jump-server-codex`, then use **Settings → Connections** in the
Codex desktop app to add the host and select the remote checkout.

## Security boundaries

- Codex runs as the unprivileged SSH user.
- The repository is writable; the rest of the server remains outside the
  normal workspace sandbox.
- Commands requiring network or access outside the workspace remain subject to
  approval.
- `sudo` stays interactive and is used only for an explicitly requested
  installation or service change.
- Never expose a Codex app-server listener directly to a shared/public network;
  remote project access is transported through SSH.

## Daily workflow

```bash
git checkout main
git pull --ff-only
git checkout -b codex/short-description
.codex/setup.sh
# implement and test
git diff --check
git push -u origin codex/short-description
```

Open a pull request and merge only after the validation workflow passes.
