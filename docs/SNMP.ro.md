# Administrare SNMP pe bază de template-uri

`gr snmp` inventariază, testează, planifică, configurează și verifică monitorizarea
SNMP fără a pune parolele în phpIPAM, argumentele proceselor, rapoarte sau audituri.
Orice scriere este implicit dry-run și necesită `--apply`.

## Modelul de inventar

phpIPAM rămâne sursa identității și intenției. Helperul de schemă gestionează
`device_model`, `snmp_enabled`, `snmp_profile`, `snmp_template`,
`monitoring_enabled`, `monitoring_profile` și `monitoring_device_id`. LibreNMS
rămâne sursa autoritativă pentru starea curentă.

Selecția template-ului este deterministă: suprascrierea `snmp_template` per IP,
apoi cel mai specific selector după IP, model, OS-ul dispozitivului nativ,
versiune OS, vendor și driver. OS-ul nativ este asociat prin `deviceId`; selecția
continuă să funcționeze fără el dacă utilizatorul API nu poate lista devices.
Catalogul local este `/etc/gr/snmp-templates.json`; upgrade-ul nu îl suprascrie.
Secretele AUTH/PRIV și tokenul LibreNMS se păstrează în `pass`; configurația
conține doar numele intrărilor din seif. `--prompt-credentials` citește parolele
fără ecou. Net-SNMP folosește un fișier temporar 0600, nu argumentele `-A/-X`.

Lista `sources` reprezintă sursele aprobate introduse în ACL-urile SNMP ale
echipamentelor. Câmpul opțional `source_address` este adresa locală de care se
leagă Net-SNMP atunci când serverul de administrare are mai multe adrese sau o
adresă VIP. Dacă este definită, adresa trebuie să existe și în `sources`. Astfel,
testul nu pleacă accidental de pe adresa principală neaprobată de ACL. Configurarea
nu atinge seiful:

```text
gr config set snmp_profiles.monitoring-v3.source_address 192.0.2.20
```

## Flux sigur

```text
gr snmp templates --target 192.0.2.10
gr snmp capabilities --ip 192.0.2.10
gr snmp assign --ip 192.0.2.10 --profile monitoring-v3 --apply
gr snmp inventory-sync --report ~/.local/state/gr/device-version/RAPORT.json
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22
gr snmp configure --ip 192.0.2.10 --source 192.0.2.20 --source 192.0.2.21 --source 192.0.2.22 --apply
gr snmp test --all
gr snmp report --all --mode ports --profile monitoring-v3
```

`inventory-sync` importă numai rezultatele reușite model/firmware din raportul
JSON al colectorului de versiuni. Rămâne dry-run până la `--apply`.

Se execută numai template-urile marcate `apply_supported`, care includ acțiunea
cerută în `supported_actions` și au handler tranzacțional revizuit. Handlerul din
`/usr/local/libexec/gr/snmp-handlers` gestionează prompturile, confirmările
interactive, codarea sigură a secretelor, cleanup-ul legacy exact și verificarea
structurală normalizată. Template-urile rămân declarative și nu conțin
credențiale sau inventarul organizației. Înaintea fiecărei schimbări, configurația curentă trebuie
colectată cu succes în arhiva Git globală. Configurația rămâne apoi în running,
se testează SNMPv3 și se salvează numai după succes, apoi configurația finală
este arhivată din nou. La eșec se execută rollback.
Sursele aprobate provin din profilul SNMP sau din opțiuni `--source` explicite;
nu există o sursă implicită/permisivă. `configure` refuză nume de obiecte deja
existente, evitând un rollback distructiv. Rotația cere obligatoriu
`--previous-profile`, pentru a putea recrea credențialele precedente. Cleanup-ul
Cisco IOS extrage intern liniile community exacte, fără afișare, le elimină,
testează v3 și le poate restaura înainte de save.

Handlerul Aruba generează secrete temporare aleatorii, valabile numai în sesiune,
pentru dialogul inițial și elimină userul `initial`. Handlerul Cisco Business
răspunde confirmării Engine ID fără a o trata drept comandă. Comware recunoaște
prompturile EXEC și system-view. PLANET generează Engine ID unic din MAC-ul din
phpIPAM și respectă ordinea particulară PRIV/AUTH. Pe Dell, algoritmii sunt
dovediți prin test SNMP autentificat deoarece CLI-ul maschează cheile. Outputul
este redactat înainte de verificare sau raportare.

Familiile cu AES inconsistent sau ACL-uri riscante rămân report/test-only. Nu se
deduc și nu se aplică ACL-uri pe control-plane, interfață sau management global.

`gr snmp capabilities` este poarta read-only pentru handlerele candidate. Intră
în modul de configurare numai pentru help contextual, folosind comenzi
`snmp-server ... ?` intenționat incomplete. Un validator static refuză orice
comandă candidat care ar putea crea un obiect. Fiecare linie de help contextual
este anulată cu Ctrl-C înainte ca clientul interactiv să poată adăuga newline,
inclusiv când firmware-ul oferă `<cr>` drept completare validă. Rezultatul conține numai
capabilități normalizate, nu configurația completă. Comanda nu citește
credențiale SNMP. Template-ul rămâne `apply_supported: false` până când această
probă și un pilot tranzacțional complet reușesc pe un echipament reprezentativ.

Cisco Business folosește două dialecte CLI vechi care nu trebuie confundate cu
IOS. Pentru firmware 2.x pe seriile 250/350, documentația Cisco definește userul
ca `... v3 auth sha AUTH priv PRIV`; algoritmul privacy este implicit și diferă
în funcție de model/firmware, deci tokenii IOS `priv aes 128` sunt invalizi. Pe seria 220, comanda userului nu
conține `v3`, iar verificarea folosește `show snmp-server ...` și
`snmp-server engineid`. Pachetul conține de aceea handlere candidate separate,
cu parole neîncadrate în ghilimele și fără spații. Vezi
[referința Cisco Business 350](https://www.cisco.com/c/en/us/td/docs/switches/lan/csbms/CBS_250_350/CLI/cbs-350-cli-/snmp-commands.html)
și [referința Cisco 220](https://www.cisco.com/c/en/us/td/docs/switches/lan/csbss/CBS220/CLI-Guide/b_220CLI/snmp_commands.html).
SG350X/SG350XG cu firmware 2.5.0.83, SG350X-24PD cu firmware 2.3.0.130 și
SG350X-48MP cu firmware 2.4.0.91, plus SG350-28P, SG250X-24P și SG250-08HP
cu firmware 2.4.0.94, sunt
reprezentate de template-uri SHA/DES restrânse. Handlerele sunt activate
tranzacțional după ce sw64/sw65/sw67, sw66/sw68/sw69, respectiv sw51, au trecut
probele authPriv din shadow și LibreNMS, save-ul condiționat, arhivarea finală
și poll-ul LibreNMS. Piloții 2.4.0.94 pe sw20, sw30 și sw31 au validat și
eliminarea community legacy, probele după cleanup și sintaxa Cisco Business
care elimină numai tokenul community. Template-ul sw51 trimite confirmările engine ID cu newline
și așteaptă două secunde înainte de verificarea structurală, reproducând ritmul
pilotului manual reușit și permițând stabilizarea bazei userilor SNMPv3.
SG220-50P cu firmware 1.1.3.1 folosește gramatica distinctă Cisco 220: view-urile
cer `subtree 1 oid-mask all viewtype`, grupurile cer atât read-view cât și
write-view, comanda userului omite `v3`, iar parola privacy implicită creează
DES. Pilotul sw15 a trecut verificarea structurală, ambele probe authPriv,
save-ul condiționat, eliminarea community legacy, arhivarea finală, asocierea
phpIPAM și poll-ul LibreNMS.
SG220-26P cu firmware 1.1.3.1 nu are un dialect uniform. Sw16 folosește
`engineid default`, view scris `iso included`, grup cu `read`, comandă de user
fără `v3` a cărei parolă privacy implicită creează DES și comanda simplă
`snmp-server` pentru activarea agentului. Pilotul sw16 a trecut probele authPriv
din shadow și LibreNMS înainte de save, a eliminat o community legacy, a trecut
din nou ambele probe, a salvat și arhivat starea finală și a finalizat asocierea
phpIPAM plus poll-ul LibreNMS. Help-ul contextual read-only de pe sw21 și sw37 a
confirmat în schimb gramatica de tip SG220-50P cu
`subtree/oid-mask/viewtype` și `read-view/write-view`. Catalogul limitează de
aceea ambele dialecte SG220-26P după IP și păstrează blocate unitățile
necunoscute, fără a ghici numai din model și firmware.
Restul combinațiilor Cisco Business 2.x rămân
blocate deoarece dialectul privacy nu poate fi dedus numai din familie.
Help-ul contextual care acceptă o parolă privacy implicită este raportat drept
`implicit-unverified`; nu este considerat dovadă AES, deoarece același format
de comandă poate crea un user DES pe firmware-urile afectate.
Sesiunile interactive Cisco Business solicită un PTY de 512 coloane. Astfel,
redesenarea comenzilor SNMP lungi de către editorul CLI nu mai poate semăna cu
un prompt nou și nu poate avansa prematur coada tranzacțională de comenzi.
Sesiunile de save recunosc numai prompturile restrânse de destinație/suprascriere
emise de `copy running-config startup-config`. Un save eșuat retrage acum
configurația running nesalvată; un eșec de arhivare după save confirmat este
raportat separat și nu mai apare incorect drept eșec de save.
Numai pentru aceste template-uri marcate explicit, verificarea structurală
acceptă lipsa etichetei algoritmului privacy ca AES128 dacă userul și
autentificarea SHA sunt prezente; o etichetă explicită DES sau fără privacy este
respinsă. Testele authPriv din shadow și de pe serverul de monitorizare rămân
obligatorii înainte de save.
Verificarea limitează etichetele de autentificare și privacy la blocul userului
cerut, astfel încât alți useri fără privacy nu pot influența decizia.
Dacă un template marcat explicit cu AES implicit raportează o etichetă privacy
nesigură, dar engine, view, grup, user și SHA sunt validate, gr poate rula
testele authPriv AES128 ca probă funcțională. Salvează numai dacă reușesc atât
proba locală, cât și cea de pe serverul de monitorizare; orice eșec face rollback.
Pentru diagnostic, handlerul 2.x verifică și că `show snmp` raportează agentul
activ. După eșecul probei AES128 poate încerca o singură citire authNoPriv pentru
a separa un user doar cu autentificare de un agent inaccesibil/dezactivat;
acest rezultat nu poate autoriza save.
Outputul tranzacțional include numai lista limitată `CLI_SAFE_DIAGNOSTICS` cu
avertismente și erori independente emise de echipament. Liniile de prompt sau
comandă repetate de terminal sunt eliminate complet: fragmentele redesenate pot
conține numai o parte dintr-un secret și nu pot fi securizate prin înlocuirea
valorii complete. Nu se păstrează transcript complet sau sensibil.

Catalogul inițial include concluziile piloților:

| Familie | Handler/acțiuni | Limita validării |
|---|---|---|
| Cisco IOS/IOS XE | tranzacțional SHA/AES128, ACL pe grup | CLI, rollback și save validate |
| Cisco CBS250-8T-D 3.1.1.7 | configure/rotate | rollout pe șase echipamente și confirmarea engine validate; cleanup legacy neprobat |
| Cisco SG/SF 250/350 firmware 2.x | handler blocat, report/test | SG350XG-2F10 2.5.0.83 a acceptat comanda documentată, dar a creat `Privacy Method: None`; atât cheia de 32 hex, cât și passphrase-ul alfanumeric de 16 caractere au eșuat pragul AES128 local și au fost retrase fără save, înaintea testului din LibreNMS |
| Cisco SG350X/SG350XG 2.5.0.83 | configure/rotate tranzacțional SHA/DES | sw64, sw65 și sw67 au trecut ambele probe authPriv; sw65/sw67 au validat și save-ul cu prompt, arhiva finală și poll-ul LibreNMS |
| Cisco SG350X-24PD 2.3.0.130 | configure/rotate tranzacțional SHA/DES | sw66, sw68 și sw69 au trecut ambele probe authPriv, save-ul cu prompt, arhiva finală și poll-ul LibreNMS |
| Cisco SG350X-48MP 2.4.0.91 | configure/rotate tranzacțional SHA/DES | sw51 a trecut verificarea structurală SHA/DES, ambele probe authPriv, save-ul condiționat, arhivarea, asocierea phpIPAM și poll-ul LibreNMS |
| Cisco SG350-28P, SG250X-24P și SG250-08HP 2.4.0.94 | configure/rotate/cleanup tranzacțional SHA/DES | sw20, sw30 și sw31 au trecut verificarea structurală, probele authPriv din ambele surse, save-ul, arhivarea și poll-ul LibreNMS; sw20/sw30 au validat și eliminarea community legacy plus retestarea |
| Cisco SG220-50P firmware 1.1.3.1 | configure/rotate/cleanup tranzacțional SHA/DES | sw15 a trecut verificarea structurală, probele authPriv din ambele surse, save-ul condiționat, eliminarea community legacy, arhivarea, asocierea phpIPAM și poll-ul LibreNMS |
| Cisco SG220-26P firmware 1.1.3.1, dialect sw16 | configure/rotate/cleanup tranzacțional SHA/DES limitat pe IP | sw16 a confirmat dialectul CLI simplu, a trecut ambele probe authPriv înainte și după cleanup legacy, a salvat/arhivat starea finală și a finalizat asocierea phpIPAM plus poll-ul LibreNMS |
| Cisco SG220-26P firmware 1.1.3.1, dialect sw21/sw37 | configure/rotate/cleanup tranzacțional SHA/DES limitat pe IP | ambele ținte au confirmat prin help contextual nemodificator gramatica subtree/read-view/write-view de tip SG220-50P; sw21 a trecut ambele probe authPriv înainte și după cleanup legacy, a salvat/arhivat starea finală și a finalizat asocierea phpIPAM plus poll-ul LibreNMS |
| Cisco SF220-24P firmware 1.1.3.1 | configure/rotate/cleanup tranzacțional SHA/DES | help-ul contextual pe sw17, sw18 și sw19 a confirmat același dialect; sw17 a trecut verificarea structurală, ambele probe authPriv, save-ul condiționat, cleanup-ul legacy și retestarea, arhiva finală, asocierea phpIPAM și poll-ul LibreNMS |
| Restul Cisco Business | report/test | nu există încă handler validat pe model/firmware |
| Aruba 2920 WB.15/WB.16 | configure/rotate | inițializare adaptivă, SHA/AES și v3-only validate |
| HPE Comware 7 | configure/rotate, ACL pe proces | workflow system-view validat pe cele trei piloturi |
| Dell OS10 | numai rotate, fără ACL | înlocuirea userului și testul SNMP validate; grup/view de la zero nu |
| PLANET SGS-6310 2.2.0E | configure/rotate, ACL pe grup | ordinea parolelor și ACL-ul procesului validate; cleanup legacy neprobat |
| FortiOS | report/test | sursele query și expunerea interfeței trebuie revizuite explicit |

Un site poate clona un template și îl poate restrânge cu `model_regex`,
`device_os_regex` și `os_version_regex`. Scrierea rămâne dezactivată până când
apply, verify, save și rollback sunt testate integral pe un echipament reprezentativ.
Catalogul din pachet este sursa capabilităților noi. Deoarece
`/etc/gr/snmp-templates.json` este păstrat intenționat la upgrade, loaderul îl
combină cu cel din pachet. O generație nouă din pachet înlocuiește ID-urile vechi
generate, dar păstrează ID-urile locale suplimentare; catalogul local aflat la
generația curentă poate suprascrie ID-urile din pachet.
Când `GR_SNMP_TEMPLATES` este setat explicit pentru o validare sau recuperare
temporară, acesta este autoritar și nu este combinat cu catalogul persistent
configurat.

## Rapoarte și LibreNMS

Selectorii sunt `--ip`, `--range`, `--subnet`, `--file` (TXT/CSV) și `--all`.
`--exclude-ip` repetabil elimină traseele OOBM/duplicate care nu trebuie tratate
ca dispozitive independente. `--managed-only` limitează raportul la adresele cu
driver sau intenție SNMP/monitorizare explicită.
Modurile sunt `inventory`, `live`, `offline` și `ports`. Live rulează comenzile
show specifice template-ului; offline citește arhiva globală; ports folosește o
descoperire SNMPv3 neautentificată cu user fictiv. Un răspuns unknown-user
demonstrează existența agentului fără credențiale, dar lipsa răspunsului UDP nu
demonstrează că portul este închis.
Cu `--profile`, raportul ports folosește `source_address` din profil; fără profil,
sursa este aleasă automat de rutare.
Rapoartele sunt 0600 în `snmp_report_dir` și nu se publică.
Fiecare rulare produce JSON detaliat și un rezumat CSV comparativ; outputul CLI
live brut rămâne numai în JSON. Raportul inventory include modelul, versiunea OS,
template-ul rezolvat, capabilitatea de scriere și acțiunile permise.

Metadatele model/firmware pot fi importate din mai multe rapoarte
`collect-version`; ultimul raport pentru același IP are prioritate. Fără
`--apply` comanda afișează numai planul:

```text
gr snmp inventory-sync --report vechi.json --report nou.json
gr snmp inventory-sync --report vechi.json --report nou.json --apply
gr snmp report --all --managed-only --exclude-ip 192.0.2.250 --mode inventory
```

```text
gr snmp monitor --all --monitoring-profile librenms
gr snmp monitor --ip 192.0.2.10 --monitoring-profile librenms --add --apply
gr snmp monitor --all --monitoring-profile librenms --profile monitoring-v3 --sync-credentials
gr snmp monitor --ip 192.0.2.10 --monitoring-profile librenms --poll --apply
```

Validarea compară existența, `status`, `last_polled` din LibreNMS și `lastSeen`
din phpIPAM. Adăugarea este dry-run fără `--apply`, apoi asocierea validată se
salvează în phpIPAM. `--sync-credentials --apply` actualizează câmpurile SNMPv3
ale dispozitivelor LibreNMS existente, iar următorul poll este verificarea
autoritativă. `--poll --apply` rulează imediat acel poll prin hostul de
monitorizare din profil și recitește status/`last_polled`. Câmpul `host` din
profil trebuie să fie un hostname sau IP exact din phpIPAM, cu metadate SSH și
sudo funcționale. Poller-ul rulează ca utilizatorul `librenms` din
`/opt/librenms`, iar la eșec este afișat mesajul relevant al poller-ului, nu
bannerul de conectare `gr exec`. Testele și rapoartele
pot fi programate extern. Pentru rotație se
creează un profil nou în vault, se rulează dry-run cu
`rotate --previous-profile VECHI --profile NOU`, se aplică în mentenanță, se
sincronizează LibreNMS și apoi se asociază profilul nou în phpIPAM. Un scheduler
poate rula acest lanț numai cu controlul ferestrei și notificare la eșec.

## Instalare

Sunt necesare Debian, Python 3.7+, uneltele Net-SNMP, SSH/sshpass, pass/GPG,
clientul SSH legacy izolat și prerechizitele phpIPAM existente. Opțiunea
`--phpipam-config` creează idempotent câmpurile. După instalare:

```text
gr doctor --api
gr snmp templates
gr snmp report --ip 192.0.2.10 --mode inventory
```

Porniți cu un singur echipament, cu backup în arhiva globală, și extindeți lotul
numai după ce testul SNMP și poll-ul LibreNMS sunt reușite.
