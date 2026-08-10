# Instalare și upgrade

[English](INSTALL.md)

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
