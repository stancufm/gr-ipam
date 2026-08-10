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
  --install-dependencies  Install missing Debian packages with apt-get
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
install_dependencies=0
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
    --install-dependencies) install_dependencies=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" -ne 0 ] && [ -z "$destdir" ]; then
  echo "Run this installer with sudo/root (or use --destdir for a test install)." >&2
  exit 2
fi

required_packages="python3 openssh-client sshpass pass gnupg ca-certificates git bash-completion less systemd"

check_dependencies() {
  missing_packages=
  for dependency_package in $required_packages; do
    if ! dpkg-query -W -f='${Status}' "$dependency_package" 2>/dev/null | grep -q '^install ok installed$'; then
      missing_packages="$missing_packages $dependency_package"
    fi
  done
  missing_packages=${missing_packages# }
}

if [ -z "$destdir" ]; then
  command -v dpkg-query >/dev/null 2>&1 || {
    echo "Cannot verify dependencies: dpkg-query is not available (Debian is required)." >&2
    exit 2
  }
  check_dependencies
  if [ -n "$missing_packages" ] && [ "$install_dependencies" -eq 1 ]; then
    command -v apt-get >/dev/null 2>&1 || {
      echo "Cannot install dependencies: apt-get is not available." >&2
      exit 2
    }
    echo "Installing required Debian packages: $missing_packages"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y $missing_packages
    check_dependencies
  fi
  if [ -n "$missing_packages" ]; then
    echo "Missing required Debian packages: $missing_packages" >&2
    echo "Install them with:" >&2
    echo "  sudo apt-get update && sudo apt-get install $missing_packages" >&2
    echo "Or re-run this installer with --install-dependencies." >&2
    exit 2
  fi
  if ! command -v ssh1 >/dev/null 2>&1; then
    echo "Missing required legacy SSH client: /usr/bin/ssh1" >&2
    echo "Install the separately packaged gr legacy SSH client, then re-run this installer." >&2
    exit 2
  fi
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
  "$destdir/etc/systemd/system" "$destdir/etc/bash_completion.d"
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
install -m 0644 "$package_dir/completions/gr.bash" "$destdir/etc/bash_completion.d/gr"

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
elif [ -r "$package_dir/release/project-release-key.asc" ]; then
  install -m 0644 "$package_dir/release/project-release-key.asc" "$destdir/etc/gr/release-key.asc"
fi

python3 -c 'import ast,sys; [ast.parse(open(path, encoding="utf-8").read(), filename=path) for path in sys.argv[1:]]' \
  "$package_dir/bin/gr" "$package_dir/libexec/validate-ssh" "$package_dir/libexec/collect-version"
sh -n "$package_dir/libexec/gr-update"
bash -n "$package_dir/completions/gr.bash"

if [ -z "$destdir" ]; then
  systemctl daemon-reload
  if [ "$enable_timer" -eq 1 ]; then
    systemctl enable --now gr-vendor-update.timer
  fi
fi

echo "Installed gr. Each user should run: gr init --configure-auth"
echo "Then validate with: gr doctor --api"
