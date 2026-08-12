# Instalare și upgrade

[English](INSTALL.md)

Într-un mediu nou, copiați `phpipam/ensure-custom-fields.php` pe serverul
aplicației phpIPAM și rulați-l acolo după backupul bazei. API-ul de adrese nu
poate crea schema, iar credențialele SQL nu sunt copiate pe jump server.
Validarea post-instalare `gr doctor --api` este obligatorie și eșuează dacă
lipsește oricare dintre cele opt câmpuri necesare.

Pregătirea idempotentă creează și validează toate câmpurile necesare pe adrese
(`ssh_*`, `device_driver`, `device_vendor`, `os_version`),
`devices.device_os` și tipul nativ `Server`. După backupul bazei, pe serverul
aplicației phpIPAM poate fi integrată în instalare astfel:

```console
sudo ./install.sh --config /etc/gr/config.json \
  --phpipam-config /var/www/html/phpipam/config.php
```

Pe jump server installerul se rulează fără `--phpipam-config`, iar `gr doctor
--api` validează câmpurile de adresă prin API.

## Cerințe

Debian 10+, Python 3.7+ și acces HTTPS la phpIPAM. Toate dependențele sunt
obligatorii pentru ca fiecare funcționalitate documentată să fie disponibilă:

```bash
sudo apt-get update
sudo apt-get install python3 openssh-client sshpass pass gnupg ca-certificates git bash-completion less systemd
```

Clientul legacy trebuie instalat separat ca `/usr/bin/ssh1`. Installerul verifică
lista completă înainte să modifice sistemul. Dacă lipsesc pachete Debian, oprește
instalarea și afișează comanda exactă. Opțiunea `--install-dependencies` autorizează
explicit instalarea automată a pachetelor lipsă prin `apt-get`.

```bash
sudo sh install.sh --base-url https://ipam.example.net --username gr-api \
  --ca-file ./organization-ca.pem --install-dependencies --enable-timer
```

Fără `--ca-file` se folosește trust store-ul Debian. `--app-id` selectează aplicația read-only, iar `--migration-app-id` aplicația de scriere. `--config` instalează o configurație pregătită. Installerul nu copiază parole sau chei.

Pachetul oficial include și instalează automat cheia GPG publică a proiectului. Pentru un fork administrat separat puteți suprascrie repository-ul:

```bash
sudo sh install.sh --config /etc/gr/config.json \
  --update-repository https://github.com/stancufm/gr-ipam.git
```

Fiecare utilizator rulează:

```bash
gr init --configure-auth
gr doctor --api
```

`gr init` creează și depozitul privat persistent pentru cheile host în
`~/.local/state/gr/known_hosts`.

Installerul creează arhiva globală de configurații și grupul de autorizare.
Accesul se acordă explicit, urmat de un login nou:

```bash
sudo usermod -aG gr-config OPERATOR
```

`/var/lib/gr/config-archive` are modul `2770` și proprietarul `root:gr-config`.
Configurațiile pot conține secrete; nu acordați grupul inutil și nu configurați
un remote Git fără o destinație securizată analizată.

### Upgrade de la gr 1.x la 2.x

Creați câmpul custom standard phpIPAM `device_driver`, instalați 2.x, apoi
migrați înainte să eliminați cheile vechi `session_driver` din profilurile de
credențiale globale/per utilizator:

```bash
gr migrate-drivers
gr migrate-drivers --apply
gr doctor --api
```

Profilurile păstrează numai secrete/identity files, iar comportamentul CLI este
stocat per adresă în phpIPAM.

Configurația globală este `/etc/gr/config.json`, suprascrierea per utilizator este `~/.config/gr/config.json`. Pentru audit adăugați `ssh_audit_enabled` și `ssh_audit_dir`; directoarele sunt create privat la prima sesiune.

Autocomplete-ul global Bash este instalat în `/etc/bash_completion.d/gr`.
Deschideți un shell nou sau rulați `source /etc/bash_completion.d/gr`. Pentru
afișarea variantelor de la prima apăsare Tab, setați
`GR_COMPLETION_CISCO_STYLE=1` înainte de încărcarea completării.

## Actualizare semnată

După instalarea cheii publice:

```bash
gr self-update check
gr self-update --dry-run
gr self-update
```

Updaterul verifică tagul semnat, testează pachetul izolat, creează backup și face rollback la eroare. Consultați [actualizarea semnată](UPDATE.ro.md).

## Test și upgrade manual

Nu instalați peste sistem în testele obișnuite:

```bash
root=$(mktemp -d)
sh install.sh --destdir "$root" --base-url https://ipam.example.net --username api-test
"$root/usr/local/bin/gr" --help
```

La upgrade faceți backup configurației, instalați noua versiune, rulați `gr doctor --api` și verificați o căutare și o sesiune auditată de test. Pachetul instalează în `/usr/local/share/doc/gr/` documentația engleză și română.

Instalările cu `--destdir` omit intenționat verificarea dependențelor hostului,
deoarece sunt operații izolate de staging/test și nu activează servicii.
