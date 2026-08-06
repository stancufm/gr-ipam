# `gr` — integrare phpIPAM și SSH

[English](GR-PHPIPAM.en.md)

Clientul global este instalat pe jump server în `/usr/local/bin/gr`. Documentația
completă este disponibilă prin `gr docs` sau `gr help`; `gr --help` afișează
rezumatul comenzilor.

## Configurație și autentificare

Configurația comună este `/etc/gr/config.json`, iar certificatul CA pin-uit este
`/etc/gr/phpipam-ca.pem`. Parola API nu este globală: fiecare utilizator o
salvează în propriul fișier `~/.config/gr/credentials`, cu mod `0600`:

```bash
gr auth configure
gr auth test
```

Dacă există `~/.config/gr/config.json`, acesta este combinat peste configurația
globală; numai cheile definite local sunt suprascrise. Dicționarul
`ssh_profiles` este combinat pe numele profilului. `--config PATH` dezactivează
combinarea și folosește exclusiv fișierul indicat.

Pentru inițializarea și verificarea unui utilizator nou:

```bash
gr init
gr init --configure-auth
gr doctor
gr doctor --api
```

`gr init` creează directoarele private cu mod `0700`. `gr doctor` nu afișează
secrete; varianta `--api` testează autentificarea existentă fără prompt.
Aplicația permanentă `gr-app` este read-only. Operațiile `update` și
`migrate-ssh` folosesc aplicația separată `gr-migrate`.

## Căutare

Comanda principală este `find`:

```bash
gr find ipam.example.net
gr find switch
gr find 192.0.2.22
gr 192.0.2.22
gr subnet 192.0.2.0/24
```

Forma fără subcomandă rămâne o prescurtare pentru `find`. Vechea subcomandă
`search` este păstrată ca alias pentru compatibilitate.

## Auditarea sesiunii SSH

Auditul integral se activează global prin `ssh_audit_enabled` sau pentru o conectare prin `gr --ssh --audit ȚINTĂ`; `--no-audit` îl dezactivează pentru sesiunea curentă. Fișierele private `.ses` păstrează separat stdin, stdout și stderr, inclusiv parole tastate, și pot fi redate cu `gr audit show FIȘIER`. Consultați [ghidul de audit](AUDIT.ro.md).

## Conectare SSH

```bash
gr find corefw --ssh
gr --ssh corefw
gr --ssh --user root --port 2222 corefw
gr --ssh --profile cisco sw10
gr --ssh --client legacy sw40
gr --ssh --no-vault ipam.example.net
```

Dacă există un singur rezultat, conexiunea pornește automat fără prompt de
selecție. Pentru două sau mai multe rezultate, acestea sunt numerotate, inclusiv
duplicatele, iar destinația este selectată explicit. Conexiunea se face la IP,
cu `ssh -F /dev/null`, deci nu folosește `~/.ssh/config`.

Câmpurile phpIPAM folosite sunt:

```text
custom_ssh_enabled
custom_ssh_user
custom_ssh_port
custom_ssh_profile
custom_ssh_jump
custom_ssh_client
```

`custom_ssh_client` este optional si accepta `normal` sau `legacy`. Valoarea
absenta si `normal` folosesc clientul standard `/usr/bin/ssh`. Valoarea
`legacy` foloseste exclusiv `/usr/bin/ssh1`, pentru echipamente vechi care nu
pot negocia cu OpenSSH standard. Optiunea `--client` suprascrie valoarea doar
pentru conexiunea curenta. Clientul legacy nu este activat global.

Dacă SSH este activat, dar userul lipsește, se folosește automat utilizatorul
Linux care rulează `gr`. Dacă portul lipsește, se folosește portul `22`.
Opțiunile `--user` și `--port` suprascriu valorile numai pentru conexiunea
curentă și nu modifică phpIPAM.

## Seif criptat pentru parole SSH

Parolele SSH pot fi păstrate per utilizator în `pass`, criptate cu GPG. Ele nu
sunt salvate în phpIPAM, configurația `gr`, linia de comandă sau fișiere
plaintext. Inițializare:

```bash
gpg --full-generate-key
gpg --list-secret-keys --keyid-format LONG
gr vault init <GPG-ID-sau-email>
gr vault set cisco
gr vault test cisco
gr vault list
```

Profilele sunt definite de administrator, de exemplu `network-admin` și
`linux-admin`. Fiecare profil indică numai numele secretului, de exemplu
`gr/network-admin`. `custom_ssh_profile` din phpIPAM selectează profilul automat;
`--profile` îl suprascrie pentru conexiunea curentă.

Când secretul există, `gr` îl decriptează în memorie și îl transmite către
`sshpass` printr-un descriptor de fișier anonim. Verificarea cheii serverului
rămâne activă. Dacă secretul nu există, `gr` revine la promptul OpenSSH normal.
Opțiunea `--no-vault` dezactivează explicit seiful pentru conexiunea curentă.

`custom_ssh_profile` poate selecta local un `identity_file` din `ssh_profiles`,
iar `custom_ssh_jump` este transmis către OpenSSH prin `-J`. În phpIPAM nu se
salvează parole, chei private, passphrase-uri sau tokenuri.

## Actualizare din linia de comandă

`gr update` este dry-run implicit. Scrierea necesită `--apply`, este urmată de
verificare GET și produce un raport de audit în `~/.local/state/gr/updates/`.

```bash
gr update 192.0.2.22 --hostname ipam.example.net
gr update 192.0.2.22 --ssh-enabled yes --ssh-user operator --ssh-port 22
gr update 192.0.2.22 --ssh-profile linux-admin --ssh-jump jump.example.net
gr update 192.0.2.22 --clear-ssh-profile --clear-ssh-jump
gr update 192.0.2.40 --ssh-client legacy

# după verificarea preview-ului:
gr update 192.0.2.22 --ssh-user operator --ssh-port 22 --apply
```

Câmpurile acceptate sunt hostname, activare SSH, user, port, profile și jump.
Pentru ștergere există `--clear-hostname`, `--clear-ssh-user`,
`--clear-ssh-port`, `--clear-ssh-profile` și `--clear-ssh-jump`. La o eroare de
scriere sau verificare, comanda încearcă revenirea la valorile anterioare.

## Migrare și sincronizare

```bash
gr migrate-ssh
gr migrate-ssh --apply --limit 1
gr migrate-ssh --apply

gr sync
gr sync --target ssh
```

Migrarea istorică parsează `[port][user]` din `/etc/hosts`, scrie câmpurile SSH
și salvează rapoarte `0600` în `~/.local/state/gr/migrations/`. Sincronizarea
SSH este dry-run implicit și necesită `--apply` pentru scriere.

phpIPAM este sursa de adevăr pentru inventar și hostname. Scrierea și exportul
pentru `/etc/hosts` sunt dezactivate prin `hosts_sync_enabled=false`.
`/etc/hosts` conține numai intrările locale obligatorii și identitatea
serverului jump; `gr` nu îl regenerează.

Fallback-ul către configurația SSH istorică este dezactivat prin
`ssh_legacy_fallback=false`. Scriptul vechi rămâne disponibil în `/usr/bin/gr`,
dar nu mai este executat automat la deschiderea sesiunii.

## Baza locala IEEE si vendorul dispozitivelor

`gr` descarca atomic registrele oficiale IEEE MA-L, MA-M si MA-S intr-un cache
global. Cautarea foloseste cel mai lung prefix disponibil (36, 28, apoi
24 biti), fara transmiterea MAC-urilor catre servicii externe.

```bash
sudo gr vendor update-db
gr vendor lookup E8:D3:22:45:47:46
gr vendor lookup 4C:E1:75:A6:76:C6 F8:0B:CB:1E:43:46
```

Baza si metadatele cu URL, numar de inregistrari si SHA-256 sunt salvate global
in `/var/lib/gr/ieee-vendors/`. Directorul este detinut de root si poate fi citit
de toti utilizatorii; actualizarea necesita `sudo`. Calea poate fi schimbata cu
cheia `vendor_db_dir` din configuratia `gr`.

Sincronizarea phpIPAM este dry-run implicit si foloseste campul `device_vendor`:

```bash
gr vendor sync
gr vendor sync --apply
gr vendor sync --apply --overwrite
```

Fara `--overwrite`, valorile existente diferite sunt raportate drept conflicte
si nu sunt modificate. Fiecare rulare produce un audit JSON in
`~/.local/state/gr/vendor-sync/`. MAC-urile local-administrate, adresele fara MAC
si prefixele necunoscute nu sunt scrise in phpIPAM.

Actualizarea bazei globale rulează și automat, săptămânal, prin timerul systemd
`gr-vendor-update.timer`. Ultima execuție poate fi verificată cu:

```bash
systemctl status gr-vendor-update.timer
journalctl -u gr-vendor-update.service
```

## Validare SSH și inventar operațional

Validarea folosește metadatele phpIPAM, profilurile și seiful utilizatorului:

```bash
gr ssh validate                         # listare fără conexiuni
gr ssh validate --run --workers 6
gr ssh validate --run --ip 192.0.2.50
```

Rapoartele sunt private în `~/.local/state/gr/switch-ssh-validation/`.

Colectarea versiunii necesită o țintă explicită. `--all` este intenționat
obligatoriu pentru operațiile în masă:

```bash
gr collect version --ip 192.0.2.50
gr collect version --all --vendor cisco --workers 4
```

Comanda rulează `show version`, păstrează ieșirea brută și raportul JSON cu mod
`0600` în `~/.local/state/gr/device-version/`.
