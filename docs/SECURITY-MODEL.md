# Security model

[Română](SECURITY-MODEL.ro.md)

## Trust boundaries

- The jump server administrator controls global code and configuration.
- Each Linux user controls only their API credential, GPG key, vault and reports.
- The locked `gr-collector` service identity owns only scheduled-collection
  configuration, state and least-privilege credentials; it is not a human
  login account.
- phpIPAM is trusted for inventory and connection metadata, not for passwords.
- Managed devices remain protected by normal SSH host-key verification.

## Controls

- global executables and shared data are root-owned;
- self-update accepts only HTTPS repositories and tags signed by the pinned project release key;
- API credentials require mode `0600`;
- user state directories use mode `0700`;
- vault secrets are encrypted using `pass` and GPG;
- passwords are passed to `sshpass` through an anonymous file descriptor;
- `gr exec --sudo` passes the sudo password only on remote standard input,
  never in argv; an optional `sudo_password_secret` prevents credential reuse;
- write commands require explicit `--apply`;
- read and write API applications are separated;
- legacy algorithms are delegated to a separate client on selected devices;
- static SSH configuration and `/etc/hosts` are not required;
- SSH audits use private directories/files but may deliberately contain typed credentials.
- the global configuration archive is writable by `gr-collector` and by
  explicitly authorized interactive operators in `gr-config`;
- HA replication is delegated exclusively to `jumpserver-ha`, with active-node
  fencing and explicit secret exclusions.

## Deployment rules

Never commit:

- `/etc/gr/config.json` from a real environment;
- credentials, tokens, GPG or SSH private keys;
- phpIPAM exports or network scan reports;
- generated validation/version reports;
- real internal CA files unless publication is intentional.

Run `gr doctor --api` after installation and upgrades. Review phpIPAM API-user
permissions periodically and rotate API/SSH passwords according to local policy.

## Reporting vulnerabilities

Do not open a public issue containing credentials, internal IP addresses or
exploit details. Contact the repository owner privately until a dedicated
security advisory process is configured.
