# Ghid complet gr și phpIPAM

[English](GR-PHPIPAM.md)

## Configurare

`/etc/gr/config.json` conține URL-ul phpIPAM, aplicațiile API, utilizatorul, CA-ul, fișierul de credențiale, opțiunile SSH, profilurile și baza IEEE. `~/.config/gr/config.json` suprascrie valorile per utilizator. Inițializați cu `gr init --configure-auth` și verificați cu `gr doctor --api`.

Metadatele SSH provin din câmpurile standard custom ale adreselor: `ssh_enabled`, `ssh_user`, `ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client`. phpIPAM nu stochează parole. Profilul selectează un secret din pass/GPG.

## Căutare și SSH

```bash
gr find <text-sau-ip>
gr find <text-sau-ip> --details
gr <ip>
gr subnet <cidr>
gr --ssh <text-sau-ip>
gr --ssh --user operator --port 2222 --profile network-admin <țintă>
```

Dacă există un singur rezultat, conectarea este automată; altfel se afișează selectorul. Override-urile CLI sunt valabile numai pentru sesiunea curentă. `--no-vault` forțează promptul OpenSSH. Clientul legacy este selectat numai prin metadata/CLI și nu slăbește clientul normal.

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
