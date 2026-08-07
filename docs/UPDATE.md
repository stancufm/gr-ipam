# Signed self-update

[Română](UPDATE.ro.md)

`gr self-update` updates the system-wide installation from a newer signed semantic release tag. It does not update phpIPAM records; that remains the purpose of `gr update`.

## Trust bootstrap

The updater trusts only a public GPG release key installed by an administrator. Install the initial package with the public key and the HTTPS repository URL:

```bash
sudo sh install.sh \
  --base-url https://ipam.example.net \
  --username gr-api \
  --release-key ./project-release-key.asc \
  --update-repository https://github.com/stancufm/gr-ipam.git
```

This creates `/etc/gr/release-key.asc` and `/etc/gr/update.json`. The private signing key must remain offline or in a protected maintainer environment and must never be installed on a jump server.

## Commands

```bash
gr self-update check
gr self-update
gr self-update --dry-run
gr self-update --version v1.2.0
gr self-update --yes
```

Checks and dry-runs execute without privilege. A live update invokes the minimal privileged helper through `sudo`, so the administrator can enter a sudo password in the same interactive terminal. `--yes` skips only the confirmation; it does not bypass sudo, signature verification or any safety check.

## Update transaction

The helper:

1. reads the root-owned HTTPS repository configuration;
2. discovers strict `vX.Y.Z` tags and refuses downgrades;
3. fetches only the selected tag into a temporary repository;
4. imports the pinned public key into a temporary keyring and verifies the tag;
5. requires the tag and package `VERSION` to match;
6. performs an isolated `DESTDIR` installation and version check;
7. creates a private backup under `/var/backups/gr/`;
8. installs while preserving `/etc/gr/config.json`, the update configuration and release key;
9. validates the installed CLI and runs the credential-independent `gr doctor --system` check;
10. restores the backup automatically if a post-staging step fails.

A lock under `/run/lock/` prevents concurrent updates. Successful backups are deliberately retained for administrator-controlled retention and recovery.

## Release requirements

Maintainers must update `VERSION` and `GR_VERSION` to the same semantic version, commit the release, create a signed annotated tag with the matching `v` prefix, and publish that tag. Unsigned tags, mismatched versions, non-HTTPS repositories and downgrades are rejected.
