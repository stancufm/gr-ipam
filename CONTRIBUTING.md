# Contributing

[Română](CONTRIBUTING.ro.md)

Use a short-lived branch for every change:

```bash
git checkout main
git pull --ff-only
git checkout -b codex/short-description
```

Before committing:

```bash
python3 -m py_compile bin/gr libexec/validate-ssh libexec/collect-version
sh -n install.sh
sh install.sh --destdir /tmp/gr-test \
  --base-url https://ipam.example.net --username api-test
```

Do not use production credentials or inventory in fixtures. Update relevant English and Romanian
documentation with every behavioral change. Submit a pull request and merge
only after checks pass.

Versioning follows semantic versioning. Releases should include the source
archive and a SHA-256 checksum.
