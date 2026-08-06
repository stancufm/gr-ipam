# Arhitectură

[English](ARCHITECTURE.md)

`bin/gr` este un CLI Python fără dependențe. El folosește API-ul HTTPS phpIPAM pentru inventar și metadate SSH, seiful GPG/pass per utilizator pentru parole, OpenSSH sau clientul `ssh1` izolat și baza IEEE comună din `/var/lib/gr`.

`libexec/validate-ssh` validează concurent dispozitivele `sw*`, iar `libexec/collect-version` păstrează ieșirea brută și produce inventar JSON. Ambele reutilizează logica CLI-ului.

Configurația comună este `/etc/gr/config.json`; `~/.config/gr/config.json` suprascrie valorile utilizatorului și combină profilurile SSH. Parola phpIPAM este în `~/.config/gr/credentials` cu `0600`, parolele SSH în `~/.password-store/gr/`, iar rapoartele și auditurile în `~/.local/state/gr/` cu directoare `0700` și fișiere `0600`.

La conectare, gr caută în phpIPAM, rezolvă utilizatorul, portul, profilul, jump host-ul și clientul, apoi pornește SSH spre IP. Dacă auditul este activ, un releu PTY captează separat stdin, stdout și stderr înainte de a le transmite terminalului și scrie cadre JSON Lines Base64 fără pierderi. Auditul global poate fi suprascris per sesiune.

Actualizările phpIPAM folosesc aplicația de scriere numai după `--apply`, verifică rezultatul prin GET și produc rapoarte private. Registrele IEEE sunt actualizate atomic și sunt căutate prin longest-prefix matching.
