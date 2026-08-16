#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

python3 -c 'import ast,sys; [ast.parse(open(path, encoding="utf-8").read(), filename=path) for path in sys.argv[1:]]' \
  bin/gr libexec/validate-ssh libexec/collect-version libexec/collect-config \
  libexec/config-collection-pools libexec/snmp-manager \
  libexec/snmp-handlers
sh -n install.sh
sh -n .codex/setup.sh
sh -n libexec/gr-update
bash -n completions/gr.bash
python3 tests/test_audit.py
python3 tests/test_config.py
python3 tests/test_config_archive.py
python3 tests/test_collect.py
python3 tests/test_config_collection_pools.py
python3 tests/test_find.py
python3 tests/test_install.py
python3 tests/test_self_update.py
python3 tests/test_snmp.py

test -f AGENTS.md
test -f examples/config.json
test -f phpipam/SETUP.md
test -f release/project-release-key.asc
test -f completions/gr.bash
test -f snmp/templates.json
test -f systemd/gr-config-collect.service
test -f systemd/gr-config-collect.timer

echo "gr-ipam development checks passed"
