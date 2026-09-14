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
- `gr device save` este dry-run implicit și cere `--apply` înainte să trimită
  comanda de persistare definită de driver.

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
| `gr ssh validate ...` | Listează sau testează accesul SSH adaptat driverului pentru un IP, pool, interval, subnet sau toate țintele. |
| `gr device save ...` | Previzualizează sau persistă configurația running după IP, model ori pentru toate driverele eligibile. |

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

Persistarea configurației running se face numai după verificarea planului:

```console
gr device save --ip 192.0.2.50
gr device save --ip 192.0.2.50 --apply
gr device save --model "SG350*"
gr device save --model "SG350*" --model "C9200*" --apply
gr device save --all
gr device save --all --apply
```

`--ip` și `--model` pot fi repetate. Modelul este comparat fără diferență între
litere mari și mici și acceptă wildcard-urile `*` și `?` față de câmpul
phpIPAM `device_model`. `--all` înseamnă toate adresele cu driver explicit
diferit de `generic`; metadatele SSH/Vault incomplete sunt raportate ca
blocate, fără presupuneri. Cisco IOS, Cisco Business, PLANET, Dell OS10,
ArubaOS-Switch și Comware folosesc secvența de save înregistrată în driver.
FortiOS este raportat `automatic`, deoarece modificările sunt persistate imediat
și nu există o comandă running-to-startup. Sesiunile aplicate sunt auditate
privat, fără înregistrarea credențialelor injectate din Vault.

Validarea SSH în masă este tot read-only și cere întotdeauna un selector
explicit:

```console
gr ssh validate --ip 192.0.2.50
gr ssh validate --pool switch-cisco-ios --run
gr ssh validate --range 192.0.2.10-192.0.2.69 --run
gr ssh validate --subnet 192.0.2.0/24 --run
gr ssh validate --all
```

Validatorul cere metadate SSH active și complete, un driver explicit diferit
de `generic` și un `device_vendor` care corespunde vendorului înregistrat al
driverului. Secvența read-only este aleasă din catalogul driverului, iar
echipamentele care necesită login interactiv folosesc handlerul lor nativ.
Metadatele lipsă sau contradictorii sunt raportate fără deschiderea unei
conexiuni. Parolele circulă printr-un descriptor privat și nu apar în argumente
sau rapoarte.

## Colectare și arhive

| Comandă | Scop |
|---|---|
| `gr collect version ...` | Colectează modelul, firmware-ul și dovezile de versiune. |
| `gr collect reports [latest]` | Navighează rapoartele de versiune salvate. |
| `gr collect config ...` | Arhivează configurațiile curente normalizate. |
| `gr collect config pools` | Validează pool-urile programate. |
| `gr collect config status` | Afișează planificarea și ultima stare a pool-urilor. |
| `gr config devices/history/view` | Navighează timpul extragerii, istoricul schimbărilor și configurațiile arhivate. |

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
