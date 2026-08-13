# Arhitectură

[English](ARCHITECTURE.md)

`libexec/gr-update` este helperul tranzacțional accesibil prin `gr self-update`. Rulează ca root, verifică tagul semnat cu cheia publică fixată, testează instalarea izolat, creează backup și face rollback dacă instalarea live eșuează.

`bin/gr` este un CLI Python fără dependențe. El folosește API-ul HTTPS phpIPAM pentru inventar și metadate SSH, seiful GPG/pass per utilizator pentru parole, OpenSSH sau clientul `ssh1` izolat și baza IEEE comună din `/var/lib/gr`.

`libexec/validate-ssh` validează concurent dispozitivele `sw*`, iar `libexec/collect-version` păstrează ieșirea brută și produce inventar JSON. Ambele reutilizează logica CLI-ului.

`libexec/collect-config` rulează comenzile de configurație ale driverului și
salvează numai modificările normalizate în arhiva Git globală privată
`/var/lib/gr/config-archive`, accesibilă grupului `gr-config`. Autentificarea
folosește seiful privat al operatorului, iar scrierea folosește lock global.
Un commit este creat numai când conținutul diferă; gr nu configurează remote.

`libexec/snmp-manager` rezolvă template-uri după model/OS, inventariază și
testează SNMP, controlează scrierile tranzacționale și reconciliază phpIPAM cu
LibreNMS. Catalogul editabil este date; activarea scrierii cere și un handler
de cod revizuit. Handlerul modifică running, verifică structura și accesul
autentificat, salvează numai la succes și altfel face rollback.

Registrul de drivere include în prezent comportamente generic, Cisco IOS,
Cisco Small Business adaptiv, Dell SmartFabric OS10, HPE
ArubaOS-Switch/ProVision și HPE Comware 7. Profilurile de credențiale nu sunt
folosite pentru deducerea driverului de echipament. Autodetecția folosește mai
întâi cea mai nouă dovadă de inventar reușită, apoi vendorul neambiguu, iar
echipamentele necunoscute devin `generic`. Schimbările aplicate folosesc API-ul
dedicat de scriere și verificare GET.

Configurația comună este `/etc/gr/config.json`; `~/.config/gr/config.json`
suprascrie valorile utilizatorului și combină profilurile SSH, SNMP și de
monitorizare.
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

Actualizările phpIPAM folosesc aplicația de scriere numai după `--apply`, verifică rezultatul prin GET și produc rapoarte private. Registrele IEEE sunt actualizate atomic și sunt căutate prin longest-prefix matching.
