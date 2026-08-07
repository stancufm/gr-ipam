#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh --base-url URL --username USER [options]

Options:
  --app-id ID             Read-only phpIPAM API application (default: gr-app)
  --migration-app-id ID   Write-enabled application (default: gr-migrate)
  --ca-file PATH          CA certificate to install (PEM)
  --config PATH           Install a complete prepared config instead
  --release-key PATH      Public GPG key used to verify signed release tags
  --update-repository URL HTTPS Git repository used by gr self-update
  --destdir PATH          Package/test installation root (no systemd actions)
  --enable-timer          Enable the weekly IEEE update timer
  --help

No passwords, SSH keys or private GPG keys are copied by this installer.
EOF
}

base_url=
username=
app_id=gr-app
migration_app_id=gr-migrate
ca_source=
config_source=
destdir=
enable_timer=0
release_key_source=
update_repository=https://github.com/stancufm/gr-ipam.git
update_repository_set=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) base_url=$2; shift 2 ;;
    --username) username=$2; shift 2 ;;
    --app-id) app_id=$2; shift 2 ;;
    --migration-app-id) migration_app_id=$2; shift 2 ;;
    --ca-file) ca_source=$2; shift 2 ;;
    --config) config_source=$2; shift 2 ;;
    --release-key) release_key_source=$2; shift 2 ;;
    --update-repository) update_repository=$2; update_repository_set=1; shift 2 ;;
    --destdir) destdir=$2; shift 2 ;;
    --enable-timer) enable_timer=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" -ne 0 ] && [ -z "$destdir" ]; then
  echo "Run this installer with sudo/root (or use --destdir for a test install)." >&2
  exit 2
fi

package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -z "$config_source" ] && { [ -z "$base_url" ] || [ -z "$username" ]; }; then
  echo "--base-url and --username are required without --config." >&2
  exit 2
fi
if [ -n "$ca_source" ] && [ ! -r "$ca_source" ]; then
  echo "Cannot read CA file: $ca_source" >&2
  exit 2
fi
if [ -n "$release_key_source" ] && [ ! -r "$release_key_source" ]; then
  echo "Cannot read release key: $release_key_source" >&2
  exit 2
fi
case "$update_repository" in
  https://*) ;;
  *) echo "--update-repository must use HTTPS." >&2; exit 2 ;;
esac

install -d -m 0755 "$destdir/usr/local/bin" "$destdir/usr/local/libexec/gr" \
  "$destdir/usr/local/share/doc/gr" "$destdir/etc/gr" "$destdir/var/lib/gr/ieee-vendors" \
  "$destdir/etc/systemd/system"
install -m 0755 "$package_dir/bin/gr" "$destdir/usr/local/bin/gr"
install -m 0755 "$package_dir/libexec/validate-ssh" "$destdir/usr/local/libexec/gr/validate-ssh"
install -m 0755 "$package_dir/libexec/collect-version" "$destdir/usr/local/libexec/gr/collect-version"
install -m 0755 "$package_dir/libexec/gr-update" "$destdir/usr/local/libexec/gr/gr-update"
install -m 0644 "$package_dir"/docs/*.md "$destdir/usr/local/share/doc/gr/"
install -m 0644 "$package_dir"/README*.md "$package_dir"/CONTRIBUTING*.md "$destdir/usr/local/share/doc/gr/"
install -m 0644 "$package_dir"/phpipam/*.md "$destdir/usr/local/share/doc/gr/"
install -m 0644 "$package_dir/VERSION" "$destdir/usr/local/share/doc/gr/VERSION"
install -m 0644 "$package_dir/systemd/gr-vendor-update.service" "$destdir/etc/systemd/system/gr-vendor-update.service"
install -m 0644 "$package_dir/systemd/gr-vendor-update.timer" "$destdir/etc/systemd/system/gr-vendor-update.timer"

if [ -n "$config_source" ]; then
  install -m 0644 "$config_source" "$destdir/etc/gr/config.json"
else
  if [ -n "$ca_source" ]; then
    ca_target=/etc/gr/phpipam-ca.pem
  else
    ca_target=/etc/ssl/certs/ca-certificates.crt
  fi
  sed -e "s|https://ipam.example.net|$base_url|" \
      -e "s|\"gr-api\"|\"$username\"|" \
      -e "s|\"gr-app\"|\"$app_id\"|" \
      -e "s|\"gr-migrate\"|\"$migration_app_id\"|" \
      -e "s|/etc/gr/phpipam-ca.pem|$ca_target|" \
      "$package_dir/examples/config.json" > "$destdir/etc/gr/config.json"
  chmod 0644 "$destdir/etc/gr/config.json"
fi
if [ -n "$ca_source" ]; then
  install -m 0644 "$ca_source" "$destdir/etc/gr/phpipam-ca.pem"
fi

update_config="$destdir/etc/gr/update.json"
if [ ! -e "$update_config" ] || [ "$update_repository_set" -eq 1 ]; then
  python3 - "$update_repository" > "$update_config" <<'PY'
import json, sys
json.dump({"repository_url": sys.argv[1]}, sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
PY
  chmod 0644 "$update_config"
fi
if [ -n "$release_key_source" ]; then
  install -m 0644 "$release_key_source" "$destdir/etc/gr/release-key.asc"
fi

python3 -c 'import ast,sys; [ast.parse(open(path, encoding="utf-8").read(), filename=path) for path in sys.argv[1:]]' \
  "$package_dir/bin/gr" "$package_dir/libexec/validate-ssh" "$package_dir/libexec/collect-version"
sh -n "$package_dir/libexec/gr-update"

if [ -z "$destdir" ]; then
  command -v ssh >/dev/null || { echo "Missing dependency: openssh-client" >&2; exit 2; }
  command -v gpg >/dev/null || echo "WARNING: install gnupg to use the encrypted vault" >&2
  command -v pass >/dev/null || echo "WARNING: install pass to use the encrypted vault" >&2
  command -v sshpass >/dev/null || echo "WARNING: install sshpass for automatic password authentication" >&2
  systemctl daemon-reload
  if [ "$enable_timer" -eq 1 ]; then
    systemctl enable --now gr-vendor-update.timer
  fi
fi

echo "Installed gr. Each user should run: gr init --configure-auth"
echo "Then validate with: gr doctor --api"
