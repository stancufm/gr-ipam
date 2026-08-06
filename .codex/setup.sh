#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"

python3 -c 'import ast,sys; [ast.parse(open(path, encoding="utf-8").read(), filename=path) for path in sys.argv[1:]]' \
  bin/gr libexec/validate-ssh libexec/collect-version
sh -n install.sh
sh -n .codex/setup.sh

test -f AGENTS.md
test -f examples/config.json
test -f phpipam/SETUP.md

echo "gr-ipam development checks passed"
