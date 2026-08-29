# Indexul comenzilor GR

Acesta este punctul de intrare al documentației instalate. Folosiți
`gr COMANDĂ --help` pentru sintaxă și `gr docs SUBIECT` pentru ghidul complet.

## Model de siguranță

- phpIPAM este sursa de adevăr pentru inventar și intenție.
- Scrierile de inventar, SNMP și monitorizare sunt doar previzualizate până la
  folosirea explicită a opțiunii `--apply`.
- Algoritmii SSH vechi rămân izolați în `/usr/bin/ssh1` și sunt selectați per
  adresă prin `ssh_client=legacy`; GR nu îi activează global.
- Parolele SSH/SNMP sunt citite din Vault-ul criptat al identității curente și
  nu sunt introduse în argumentele proceselor.
- `gr device probe` nu creează transcript și acceptă numai comenzi read-only,
  controale de sesiune și help contextual terminat în `?`.

## Inventar și acces

| Comandă | Scop |
|---|---|
| `gr find TERMENI` | Caută în phpIPAM după IP, hostname, descriere, owner, MAC sau port. |
| `gr --ssh TERMENI` | Selectează o țintă și deschide sesiunea SSH adaptată driverului. |
| `gr subnet CIDR` | Listează adresele phpIPAM dintr-o clasă. |
| `gr update IP ...` | Previzualizează/aplică metadate hostname, SSH, driver și vendor. |
| `gr driver list` | Arată driverele și comenzile lor de colectare. |
| `gr driver detect ...` | Detectează/aplică driverul din inventarul colectat. |
| `gr vendor ...` | Verifică baza IEEE și reconciliază vendorii în phpIPAM. |
| `gr ssh validate` | Listează sau testează metadatele SSH ale switchurilor. |

## Comenzi și CLI-uri de echipamente

`gr exec ȚINTĂ -- COMANDĂ` rulează o comandă SSH remote normală, de exemplu o
comandă Linux. Echipamentele cu al doilea login interactiv nu acceptă cereri SSH
exec; pentru ele se folosește proba nativă adaptată driverului:

```console
gr device probe legacy-switch \
  --command "terminal datadump" \
  --command "show logging" \
  --command "configure terminal" \
  --command "logging ?" \
  --command "end"
```

Help-ul contextual este afișat și anulat cu Ctrl-C fără executarea liniei
editabile. Firmware-ul care păstrează linia este recuperat cu Ctrl-U/Ctrl-C,
tot fără newline. GR așteaptă promptul real între comenzi, răspunde negativ schimbării
opționale a parolei Cisco Business, limitează durata sesiunii și timpul de
așteptare per comandă și elimină parola Vault din rezultat.

## Colectare și arhive

| Comandă | Scop |
|---|---|
| `gr collect version ...` | Colectează modelul, firmware-ul și dovezile de versiune. |
| `gr collect reports [latest]` | Navighează rapoartele de versiune salvate. |
| `gr collect config ...` | Arhivează configurațiile curente normalizate. |
| `gr collect config pools` | Validează pool-urile programate. |
| `gr collect config status` | Afișează planificarea și ultima stare a pool-urilor. |
| `gr config devices/history/view` | Navighează arhiva globală de configurații. |

Ghid complet: `gr docs config-pools --language ro`.

## SNMP

Începeți cu `gr snmp --help` și `gr docs snmp --language ro`.

| Comandă | Scop |
|---|---|
| `gr snmp templates [--target ȚINTĂ]` | Listează template-urile sau rezolvă o țintă. |
| `gr snmp capabilities ...` | Verifică un dialect candidat prin help contextual sigur. |
| `gr snmp test ...` | Testează credențialele fără modificarea echipamentului. |
| `gr snmp report ...` | Produce rapoarte offline, porturi, inventar sau live. |
| `gr snmp assign ...` | Previzualizează/aplică intenția SNMP în phpIPAM. |
| `gr snmp inventory-sync ...` | Importă model/OS/vendor din rapoartele de versiune. |
| `gr snmp configure ...` | Planifică/aplică tranzacțional un template SNMPv3. |
| `gr snmp rotate ...` | Rotește tranzacțional credențialele SNMPv3 administrate. |
| `gr snmp cleanup ...` | Elimină tranzacțional configurația SNMP v1/v2 veche. |
| `gr snmp monitor ...` | Compară/reconciliază phpIPAM cu LibreNMS. |

`configure`, `rotate`, `cleanup`, `assign` și modificările de monitorizare rămân
dry-run până la folosirea explicită a opțiunii `--apply`.

## Configurare, Vault și diagnostic

| Comandă | Scop |
|---|---|
| `gr config show` | Arată configurația implicită/globală/user/efectivă. |
| `gr config set/unset ...` | Administrează setările fără editarea JSON. |
| `gr init --configure-auth` | Inițializează starea privată și autentificarea phpIPAM. |
| `gr doctor --api` | Validează instalarea, Vault-ul și phpIPAM. |
| `gr vault list/set/test/reset-agent` | Administrează secretele SSH criptate. |
| `gr audit show ...` | Navighează sesiunile înregistrate intenționat. |
| `gr self-update ...` | Verifică și instalează release-uri semnate. |

## Subiecte de documentație

```console
gr docs list
gr docs guide --language ro
gr docs snmp --language ro
gr docs config-pools --language ro
gr docs audit --language ro
gr docs architecture --language ro
gr docs security --language ro
gr docs install --language ro
gr docs update --language ro
```
