# Ghid complet gr și phpIPAM

[English](GR-PHPIPAM.md)

## Configurare

`/etc/gr/config.json` conține URL-ul phpIPAM, aplicațiile API, utilizatorul, CA-ul, fișierul de credențiale, opțiunile SSH, profilurile și baza IEEE. `~/.config/gr/config.json` suprascrie valorile per utilizator. Inițializați cu `gr init --configure-auth` și verificați cu `gr doctor --api`.

Metadatele provin din câmpurile custom standard `ssh_enabled`, `ssh_user`,
`ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client`, `device_driver` și
`device_vendor`. phpIPAM nu stochează parole. `ssh_profile` selectează numai
credențialele, iar `device_driver` selectează independent comportamentul CLI.

## Căutare și SSH

```bash
gr find <text-sau-ip>
gr find <text-sau-ip> --details
gr <ip>
gr subnet <cidr>
gr --ssh <text-sau-ip>
gr --ssh --user operator --port 2222 --profile network-admin --driver cisco-ios <țintă>
```

Dacă există un singur rezultat, conectarea este automată; altfel se afișează selectorul. Override-urile CLI sunt valabile numai pentru sesiunea curentă. `--no-vault` forțează promptul OpenSSH. Clientul legacy este selectat numai prin metadata/CLI și nu slăbește clientul normal.

Tabelul compact afișează câmpul phpIPAM `lastSeen` imediat după `STATUS`.

### Login secundar Cisco Small Business

Unele switchuri Cisco Small Business stabilesc conexiunea SSH și apoi afișează
propriile prompturi `User Name:` și `Password:`. Comportamentul se selectează
independent în phpIPAM:

```json
"shared-network": {"password_secret": "gr/shared-network"}
```

În phpIPAM, `ssh_profile` indică profilul de credențiale necesar, iar
`device_driver=cisco-small-business` selectează comportamentul. `gr --ssh`
răspunde prompturilor secundare și apoi
predă CLI-ul interactiv operatorului. `gr collect version` folosește același
driver, încearcă dezactivarea paginării cu `terminal datadump`, rulează
`show version` pentru firmware, rulează `show system` pentru model/datele de sistem și închide
sesiunea. Fiecare comandă este trimisă numai după reapariția promptului CLI.
Pe modelele Sx220, `terminal datadump` poate să nu fie suportată, `show version`
conține deja modelul, iar două comenzi `exit` sunt necesare deoarece prima doar
iese din modul privilegiat. Parola injectată nu este scrisă în rapoartele
collect.

Echipamentele Dell SmartFabric OS10 folosesc `device_driver=dell-os10`.
Driverul rulează `show version` și extrage versiunea OS și `System Type`,
independent de profilul de credențiale SSH selectat.

`--details` păstrează sumarul compact și apoi afișează toate câmpurile returnate
de phpIPAM pentru fiecare adresă găsită. Câmpurile sunt sortate, valorile pe mai
multe linii sunt indentate, iar structurile JSON rămân lizibile. Afișarea este
read-only și poate fi combinată și cu `--ssh`.

## Audit SSH

```bash
gr --ssh --audit <țintă>
gr --ssh --no-audit <țintă>
gr audit show
gr audit show <hostname-sau-ip>
gr audit show <hostname-sau-ip> latest
gr audit show <hostname-sau-ip> latest --no-more
```

`ssh_audit_enabled` stabilește politica globală, iar `ssh_audit_dir` directorul rădăcină. Fișierele se salvează în `<director>/<hostname-sau-ip>/<hostname-sau-ip>-<UTC>.ses`, cu `0700/0600`. Sunt capturate fără pierderi stdin, stdout și stderr, inclusiv parolele tastate. Consultați [ghidul de audit](AUDIT.ro.md).

Redarea normală afișează stdout/stderr printr-un pager automat și omite stdin
pentru a evita dublarea ecoului de terminal. `--include-stdin` reactivează
vizualizarea completă, `--stream` izolează un canal, iar `--no-more` dezactivează
paginarea.

## Autocomplete Bash

Installerul global oferă completare pentru comenzi, opțiuni și navigarea
dinamică în audit. Deschideți un shell nou sau rulați
`source /etc/bash_completion.d/gr`. Dacă setați
`GR_COMPLETION_CISCO_STYLE=1` înainte de încărcare, opțiunile ambigue sunt
afișate de la prima apăsare Tab. `gr completion bash` afișează scriptul instalat.

## Autentificare și seif

```bash
gr auth configure
gr auth test
gr vault init <GPG-ID>
gr vault set <profil>
gr vault test <profil>
gr vault list
```

Credențiala API are modul `0600`. Parolele SSH sunt criptate de pass/GPG și transmise către sshpass prin descriptor anonim.

## Sincronizare și actualizări

`gr sync` și `gr export` generează configurație SSH și, numai dacă este activat explicit, `/etc/hosts`. `gr update <ip>` afișează schimbarea; scrierea necesită `--apply` și verificare GET. `gr migrate-ssh` migrează metadatele vechi, dry-run implicit.

## Producători și operații

```bash
sudo gr vendor update-db
gr vendor lookup <mac>
gr vendor sync
gr vendor sync --apply
gr ssh validate [--run] [--ip IP]
gr collect version --ip IP
```

Baza IEEE comună este actualizată atomic. Sincronizările și colectările produc rapoarte private. Nu comiteți rapoarte, inventare sau audituri.

### Colectarea inventarului de versiuni

```bash
gr collect version --all [--vendor VENDOR] [--workers N]
gr collect version --ip IP [--ip IP ...] [--vendor VENDOR] [--workers N]
```

Comanda citește adresele din phpIPAM, selectează înregistrările al căror
`device_vendor` corespunde producătorului cerut, necesită metadate SSH active și
un profil în seiful SSH, apoi rulează `show version` prin clientul normal sau
clientul legacy izolat ales pentru fiecare dispozitiv. Nu modifică phpIPAM sau
configurația echipamentelor.

Driverul provine din câmpul phpIPAM `device_driver`, nu din profilul de
credențiale. `--driver` îl suprascrie numai pentru conexiunea interactivă
curentă. Dacă valoarea lipsește, înregistrările Cisco folosesc fallback
`cisco-ios`, iar ceilalți producători `generic`.

Opțiuni:

- `--all` selectează toate adresele eligibile care corespund lui `--vendor`;
- `--ip IP` limitează colectarea la o adresă și poate fi repetat; filtrul de
  producător și cerințele SSH/profil se aplică în continuare;
- `--vendor VENDOR` compară fără diferență între litere mari și mici câmpul
  phpIPAM `device_vendor`; valoarea implicită este `cisco`;
- `--workers N` stabilește numărul de sesiuni SSH paralele; implicit este `4`,
  iar valoarea efectivă este limitată la intervalul `1..12`.

Fiecare rulare creează un director privat cu timestamp în
`~/.local/state/gr/device-version/`. Acesta conține outputul brut `show version`
pentru fiecare dispozitiv, un depozit persistent per utilizator pentru cheile host și
`<vendor>-show-version-report.json` cu modelul, firmware-ul, familia OS, uptime,
seria, imaginea de sistem, ROM-ul, stderr și rezultatul. Parserul este destinat
în principal outputului Cisco; alt producător este util numai dacă suportă
`show version` și un format compatibil.

### Migrarea driverelor din gr 1.x

Versiunea 2 nu mai folosește la runtime `session_driver` din profilurile de
credențiale. Înainte de eliminarea cheilor vechi din configurație:

```bash
gr migrate-drivers
gr migrate-drivers --apply
```

Migrarea copiază asocierile vechi în câmpul phpIPAM `device_driver`, generează
un raport privat și verifică GET fiecare scriere. `--limit` permite un pilot,
iar `--overwrite` necesită `--apply`.

Cheile host sunt păstrate în `~/.local/state/gr/known_hosts`. Cheile noi sunt
acceptate și raportate `added`; o cheie schimbată produce `changed` și nu este
înlocuită automat.

Codul de ieșire este `0` dacă toate dispozitivele reușesc, `1` dacă nu există
niciun dispozitiv eligibil și `2` dacă cel puțin o conexiune eșuează sau expiră.

Rulările complete pot fi navigate fără memorarea căilor rapoartelor:

```bash
gr collect reports
gr collect reports latest
gr collect reports <timestamp-raport>
gr collect reports <timestamp-raport> --raw
gr collect reports <timestamp-raport> --no-more
```

Prima comandă afișează câte un rând pentru fiecare rulare, cu timestampul,
numărul de dispozitive și totalurile `success`/`failed`/`timeout`. Selectarea lui
`latest` sau a unui ID afișează implicit un tabel de echipamente. Coloanele sunt
obținute din toate atributele disponibile, cu excepția `stderr`, `raw_report`,
`system_image`, `rom` și `uptime`. `--raw` afișează fișierul JSON original fără
transformare. Ambele formate folosesc pagerul automat; `--no-more` scrie direct
în terminal. Autocomplete-ul Bash propune `latest`, toate ID-urile și opțiunile
de afișare. Rapoartele sunt căutate în `device_version_dir`, implicit
`~/.local/state/gr/device-version`, configurabil global sau per user.

## Diagnostic și documentație

`gr doctor --api` verifică fișierele, permisiunile, dependențele, baza IEEE și API-ul. `gr docs --language en` afișează ghidul englez, iar `gr docs --language ro` ghidul român. Toate scrierile de inventar rămân dry-run până la `--apply`.

### Inventarul configurației

```bash
gr config show
```

Inventarul afișează toate opțiunile acceptate de versiunea instalată. Pentru
fiecare opțiune compară valoarea implicită documentată, valoarea globală din
`/etc/gr/config.json`, suprascrierea utilizatorului activ din
`~/.config/gr/config.json`, valoarea efectivă normalizată și sursa ei.
Opțiunile obligatorii fără valoare implicită sunt marcate `<required>`.
Comanda este read-only și nu citește credențiala API separată sau seiful SSH.
