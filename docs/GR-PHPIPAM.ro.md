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
propriile prompturi `User Name:` și `Password:`, iar altele ajung direct în
promptul CLI. Driverul adaptiv recunoaște ambele fluxuri. Comportamentul se selectează
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

Colectarea este considerată reușită după ce toate comenzile de date au revenit
la promptul CLI. Comenzile de închidere sunt urmărite separat, astfel încât un
echipament care închide conexiunea după primul `exit` nu mai este raportat fals
ca eșuat.

Echipamentele Dell SmartFabric OS10 folosesc `device_driver=dell-os10`.
Driverul rulează `show version` și extrage versiunea OS și `System Type`,
independent de profilul de credențiale SSH selectat.

Echipamentele HPE ArubaOS-Switch/ProVision folosesc
`device_driver=hpe-arubaos-switch`. Driverul interactiv confirmă ecranul
`Press any key to continue`, dezactivează paginarea cu `no page`, rulează
`show version` și `show system` și extrage identificatorul de
produs HP, modelul și revizia software. Userul SSH și profilul parolei rămân
metadate independente.

Echipamentele HPE Comware 7 folosesc `device_driver=hpe-comware7`. Driverul
interactiv recunoaște promptul `<hostname>`, dezactivează paginarea cu
`screen-length disable`, rulează `display version` și `display device
manuinfo` și închide sesiunea cu `quit`. El extrage release-ul Comware,
produsul/modelul, imaginea de sistem, BootROM și serialul de fabricație când
sunt disponibile.

Echipamentele FortiGate cu FortiOS folosesc `device_driver=fortigate-fortios`.
Driverul colectează read-only prin `get system status`, iar configurația este
arhivată cu `show full-configuration`. Nu intră niciodată în modul de
configurare, iar profilul de credențiale rămâne independent de driver.

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
Un upgrade înlocuiește fișierul, dar nu poate modifica funcțiile deja încărcate
în shell-ul curent. Dacă `gr driver<Tab>` nu propune `list` și `detect`, rulați:

```bash
source /etc/bash_completion.d/gr
```

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

Rezultatele căutării folosesc tabelul standard de inventar. Adăugați `--brief`
la `gr TERMEN` sau `gr find TERMEN` pentru a afișa numai `IP`, `HOSTNAME`, `SSH`
și `DESCRIPTION`; `--brief` și `--details` se exclud reciproc. Adăugați
`--show-vendor` în oricare format pentru coloana phpIPAM `device_vendor`.

`gr sync` și `gr export` generează configurație SSH și, numai dacă este activat explicit, `/etc/hosts`. `gr update <ip>` afișează schimbarea, inclusiv pentru `--device-driver` și `--device-vendor`; scrierea necesită `--apply` și verificare GET. `gr migrate-ssh` migrează metadatele vechi, dry-run implicit.

```bash
gr update 10.22.10.76 --hostname sw76 --ssh-enabled yes --ssh-user admin \
  --ssh-profile admin --device-driver hpe-comware7 --device-vendor hpe-comware
gr update 10.22.10.76 --hostname sw76 --ssh-enabled yes --ssh-user admin \
  --ssh-profile admin --device-driver hpe-comware7 --device-vendor hpe-comware --apply
```

## Producători și operații

```bash
sudo gr vendor update-db
gr vendor list
gr vendor lookup <mac>
gr vendor sync
gr vendor sync --apply
gr ssh validate [--run] [--ip IP]
gr collect version --ip IP
```

Baza IEEE comună este actualizată atomic. Sincronizările și colectările produc rapoarte private. Nu comiteți rapoarte, inventare sau audituri.
`gr vendor list` citește valorile distincte `device_vendor` din phpIPAM și
afișează numărul adreselor. Aceleași valori reale alimentează autocomplete
pentru `--vendor` și `--device-vendor`.

### Colectarea inventarului de versiuni

```bash
gr collect version --all [--vendor VENDOR] [--workers N]
gr collect version --all-drivers [--workers N]
gr collect version --ip IP [--ip IP ...] [--vendor VENDOR] [--workers N]
```

Comanda citește adresele din phpIPAM, selectează înregistrările al căror
`device_vendor` corespunde producătorului cerut, necesită metadate SSH active și
un profil în seiful SSH, apoi rulează `show version` prin clientul normal sau
clientul legacy izolat ales pentru fiecare dispozitiv. Nu modifică phpIPAM sau
configurația echipamentelor.

Driverul provine din câmpul phpIPAM `device_driver`, nu din profilul de
credențiale. `--driver` îl suprascrie numai pentru conexiunea interactivă
curentă. Dacă valoarea lipsește, driverul este întotdeauna `generic`; vendorul
nu selectează niciodată implicit driverul.

Opțiuni:

- `--all` fără `--vendor` selectează toate adresele cu driver explicit diferit
  de `generic`; dacă este furnizat, `--vendor` filtrează suplimentar selecția;
- `--all-drivers` ignoră vendorul și hostname-ul și selectează fiecare adresă
  care are în phpIPAM un `device_driver` explicit diferit de `generic`;
- `--ip IP` limitează colectarea la o adresă și poate fi repetat; vendorul nu
  este filtrat decât dacă se furnizează `--vendor`. O țintă cu driver efectiv
  `generic` este respinsă înainte de SSH, împreună cu instrucțiuni pentru
  `gr driver detect`;
- `--vendor VENDOR` compară fără diferență între litere mari și mici câmpul
  phpIPAM `device_vendor`; nu există vendor implicit;
- `--workers N` stabilește numărul de sesiuni SSH paralele; implicit este `4`,
  iar valoarea efectivă este limitată la intervalul `1..12`.

Fiecare rulare creează un director privat cu timestamp în
`~/.local/state/gr/device-version/`. Acesta conține outputul brut `show version`
pentru fiecare dispozitiv, un depozit persistent per utilizator pentru cheile host și
`<vendor>-show-version-report.json` (sau `all-drivers-show-version-report.json`)
cu criteriile de generare, modelul, firmware-ul, familia OS, uptime, seria,
imaginea de sistem, ROM-ul, stderr și rezultatul. Parserul este controlat de
driverul fiecărui echipament și suportă familiile implementate Cisco, Dell OS10,
HPE ArubaOS-Switch, HPE Comware și PLANET SGS.

`gr collect reports` afișează fiecare raport pe o linie. Coloana `CRITERIA`
arată cum a fost generat (`vendor=... all`, IP-urile selectate sau
`driver!=generic`). Rapoartele vechi fără criterii salvate sunt marcate `legacy`.
Timestampurile afișate sunt convertite din UTC în `Europe/Bucharest` și au
formatul `YYYY-MM-DD HH:MM:SS`; ID-urile stabile și valorile JSON rămân UTC.

### Arhiva globală de configurații

`gr collect config` extrage configurația curentă folosind comenzile definite de
driver și salvează textul normalizat în repository-ul Git global privat
`/var/lib/gr/config-archive`. Arhiva aparține grupului `gr-config`; numai membrii
autorizați pot citi sau colecta configurații. Profilurile și seiful de parole
rămân per utilizator și nu sunt introduse în Git.

```bash
gr collect config --all [--vendor VENDOR] [--workers N]
gr collect config --ip IP [--ip IP ...] [--vendor VENDOR] [--workers N]
```

Comenzile fiecărui driver sunt afișate de `gr driver list`. Țintele `generic`
sunt respinse. Colectarea folosește lock global, normalizează outputul de
terminal și păstrează câte un fișier pentru fiecare IP. Un commit este creat
numai dacă s-a schimbat cel puțin o configurație. Interogările periodice
identice nu creează commit și nu dublează fișiere; Git comprimă diferențele.

Navigarea arhivei comune:

```bash
gr config devices
gr config devices sw
gr config history sw50
gr config view sw50
gr config view sw50 latest
gr config view sw50 <revizie>
gr config view sw50 <revizie> --no-more
```

`devices` afișează țintele, numărul versiunilor și ultima colectare. `history`
listează reviziile Git pentru un hostname sau IP exact. `view` folosește pagerul
automat și afișează ultima configurație sau una istorică. Autocomplete-ul
propune dinamic echipamentele și reviziile. gr nu configurează niciun remote
pentru această arhivă; publicarea configurațiilor necesită o decizie separată.

### Migrarea driverelor din gr 1.x

Versiunea 2 nu mai folosește la runtime `session_driver` din profilurile de
credențiale. Înainte de eliminarea cheilor vechi din configurație:

```bash
gr migrate-drivers
gr migrate-drivers --apply
```

### Detectarea automată a driverului

`gr driver detect` clasifică echipamentele folosind cea mai nouă înregistrare
reușită din rapoartele de inventar și metadatele vendor neambigue din phpIPAM.
Dovada de model și familie OS are prioritate față de vendor. Dacă nu există o
dovadă sigură, driverul detectat este intenționat `generic`. Profilurile de
credențiale, userii și porturile SSH nu sunt folosite ca dovezi și nu sunt
modificate.

Lista driverelor implementate și comenzile operaționale deținute de fiecare:

```bash
gr driver list
```

Selecția acceptă IP-uri exacte, subnet CIDR, range inclusiv, câmpurile normale
de căutare sau toate adresele phpIPAM:

```bash
gr driver detect --ip 10.22.10.25 --ip 10.22.10.53
gr driver detect --subnet 10.22.10.0/24
gr driver detect --range 10.22.10.10-69
gr driver detect --find sw
gr driver detect --all
```

Fiecare selector acceptă `--apply`. Fără acesta, detecția este întotdeauna
preview read-only. Cu `--apply`, gr modifică numai `custom_device_driver`,
verifică fiecare scriere prin GET și încearcă rollback la eșec:

```bash
gr driver detect --ip 10.22.10.25 --apply
gr driver detect --subnet 10.22.10.0/24 --apply
gr driver detect --range 10.22.10.10-69 --apply
gr driver detect --find sw --apply
gr driver detect --all --apply
```

Vendorul este o dovadă separată și nu selectează implicit driverul. Fluxul
complet pentru vendor este:

```bash
sudo gr vendor update-db
gr vendor list
gr vendor lookup 00:11:22:33:44:55
gr vendor sync
gr vendor sync --apply
gr vendor sync --apply --overwrite
```

Folosiți `--overwrite` numai după analiza conflictelor. Corecția manuală a
driverului se previzualizează înainte de aplicare:

```bash
gr update 10.22.10.50 --device-driver cisco-small-business
gr update 10.22.10.50 --device-driver cisco-small-business --apply
gr update 10.22.10.50 --clear-device-driver --apply
gr 10.22.10.50 --details
gr 10.22.10.50 --show-vendor
```

Autocomplete-ul Bash acoperă `gr driver`, subcomenzile, selectorii, numele
driverelor și vendorii reali din phpIPAM. `gr completion drivers` și
`gr completion vendors` afișează listele de candidați pentru automatizări.

Comanda este dry-run implicit și afișează driverul curent, cel detectat, dovada
și starea planificată. `--apply` scrie fiecare `custom_device_driver` schimbat,
îl verifică prin GET și încearcă rollback la eșec. Fiecare rulare creează un
raport JSON privat în `~/.local/state/gr/driver-detection/`.

```bash
gr driver detect --range 10.22.10.10-69 --apply
gr driver detect --find "Linux Jump" --apply
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
