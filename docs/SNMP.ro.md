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

Catalogul inițial include concluziile piloților:

| Familie | Handler/acțiuni | Limita validării |
|---|---|---|
| Cisco IOS/IOS XE | tranzacțional SHA/AES128, ACL pe grup | CLI, rollback și save validate |
| Cisco CBS250-8T-D 3.1.1.7 | configure/rotate | rollout pe șase echipamente și confirmarea engine validate; cleanup legacy neprobat |
| Cisco SG/SF 220/250/350 și restul CBS | report/test | unele versiuni creează userul, dar AES nu răspunde |
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
monitorizare din profil și recitește status/`last_polled`. Testele și rapoartele
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
