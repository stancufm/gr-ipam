# Arhitectură

[English](ARCHITECTURE.md)

`libexec/gr-update` este helperul tranzacțional accesibil prin `gr self-update`. Rulează ca root, verifică tagul semnat cu cheia publică fixată, testează instalarea izolat, creează backup și face rollback dacă instalarea live eșuează.

`bin/gr` este un CLI Python fără dependențe. El folosește API-ul HTTPS phpIPAM pentru inventar și metadate SSH, seiful GPG/pass per utilizator pentru parole, OpenSSH sau clientul `ssh1` izolat și baza IEEE comună din `/var/lib/gr`.

`libexec/validate-ssh` validează concurent dispozitivele `sw*`, iar `libexec/collect-version` păstrează ieșirea brută și produce inventar JSON. Ambele reutilizează logica CLI-ului.

`libexec/collect-config` rulează comenzile de configurație ale driverului și
salvează numai modificările normalizate în arhiva Git globală privată
`/var/lib/gr/config-archive`, deținută de `gr-collector:gr-config` cu modul
`2770`. Rulările interactive folosesc seiful operatorului, iar cele programate
folosesc identitatea și configurația dedicate `gr-collector` din
`/etc/gr/collector.json`. Lock-ul este păstrat în `.git`, iar un commit este
creat numai când conținutul diferă; GR nu configurează remote.

Timerul systemd rulează ca `gr-collector`, este dezactivat implicit și este
blocat de markerul nodului HA activ. Proiectul independent `jumpserver-ha`
replică arhiva și datele identităților; standby-ul nu programează colectarea
înainte de promovare.

`libexec/config-collection-pools` rezolvă pool-urile declarative din inventarul
phpIPAM, serializează rulările programate și deleagă seturile eligibile către
`collect-config`. Starea schedulerului este separată de arhiva Git.

`libexec/snmp-manager` rezolvă template-uri după model/OS, inventariază și
testează; `libexec/snmp-handlers` separă comportamentul interactiv revizuit și
verificarea normalizată de template-urile SNMP declarative.
Managerul controlează scrierile tranzacționale și reconciliază phpIPAM cu
LibreNMS. Catalogul editabil este date; activarea scrierii cere și un handler
de cod revizuit. Handlerul modifică running, verifică structura și accesul
autentificat, salvează numai la succes și altfel face rollback.

Executorul nativ pentru CLI-uri interactive se află în `bin/gr`. El deține
PTY-ul, automatul celui de-al doilea login, coada de comenzi condiționată de
prompt, anularea help-ului contextual, limitele de timp și eliminarea secretelor
din rezultat. `gr device probe`, colectarea versiunii și colectarea configurației
reutilizează acest executor în locul sesiunilor `expect`, Paramiko sau Netmiko
imbricate.

Registrul de drivere include în prezent comportamente generic, Cisco IOS,
Cisco Small Business adaptiv, Dell SmartFabric OS10, HPE
ArubaOS-Switch/ProVision și HPE Comware 7. Profilurile de credențiale nu sunt
folosite pentru deducerea driverului de echipament. Autodetecția folosește mai
întâi cea mai nouă dovadă de inventar reușită, apoi vendorul neambiguu, iar
echipamentele necunoscute devin `generic`. Schimbările aplicate folosesc API-ul
dedicat de scriere și verificare GET.

Configurația comună este `/etc/gr/config.json`; `~/.config/gr/config.json`
suprascrie valorile utilizatorului și combină profilurile SSH, SNMP și de
monitorizare. Obiectul `config_collection` este combinat superficial, astfel
încât starea schedulerului poate fi suprascrisă fără duplicarea pool-urilor
comune.
Parola phpIPAM este în `~/.config/gr/credentials` cu `0600`, parolele SSH în
`~/.password-store/gr/`, cheile host persistente în
`~/.local/state/gr/known_hosts`, iar rapoartele și auditurile în
`~/.local/state/gr/` cu directoare `0700` și fișiere `0600`.
Parolele AUTH/PRIV și tokenurile de monitorizare rămân în intrări `pass` și nu
sunt salvate în phpIPAM. phpIPAM păstrează intenția/asocierea, LibreNMS este
autoritatea pentru existență, status și ultimul poll, iar `lastSeen` rămâne din
phpIPAM.

La conectare, gr caută în phpIPAM și rezolvă separat utilizatorul, portul,
profilul de credențiale, jump host-ul, clientul SSH și driverul dispozitivului.
Driverul gestionează prompturile, comenzile și parsarea fără să selecteze
parola. Dacă auditul este activ, un releu PTY captează separat stdin, stdout și
stderr înainte de a le transmite terminalului și scrie cadre JSON Lines Base64
fără pierderi. Auditul global poate fi suprascris per sesiune.

Codul 5 întors de `sshpass` este interpretat drept credențială Vault respinsă.
Pentru o țintă generică, operatorul poate aproba o singură reîncercare prin
promptul OpenSSH, fără salvarea parolei. Driverele automatizate se opresc până
la corectarea profilului Vault, deoarece handlerul lor necesită credențiala.

Pentru orice alt status nenul, dovezile stderr sunt clasificate și se afișează
un `SSH_DIAGNOSTIC` fără secrete. Clientul normal acceptă numai cheile host
văzute prima dată în magazinul privat gr, refuză cheile schimbate și folosește
încercări de conectare limitate plus keepalive.

Actualizările phpIPAM folosesc aplicația de scriere numai după `--apply`, verifică rezultatul prin GET și produc rapoarte private. Registrele IEEE sunt actualizate atomic și sunt căutate prin longest-prefix matching.
