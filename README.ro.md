# gr-ipam

[English](README.md)

`gr-ipam` este un CLI multi-utilizator pentru jump servere Debian care folosesc phpIPAM drept sursă de adevăr pentru inventarul de rețea și metadatele conexiunilor SSH.

Poate căuta adrese, deschide conexiuni SSH, păstra parolele dispozitivelor într-un seif criptat per utilizator, actualiza baza IEEE OUI, sincroniza producătorii, valida accesul la switch-uri, colecta versiuni, administra SNMPv3 pe bază de template-uri și audita integral sesiunile SSH.

## Proprietăți principale

- phpIPAM rămâne sursa de adevăr, fără modificări de schemă sau sursă;
- parolele API și SSH sunt private fiecărui utilizator;
- profilurile de credențiale, transportul SSH și driverele sunt straturi independente;
- driverele gestionează prompturile, comenzile și parsarea, fără să selecteze secrete;
- aplicațiile API de citire și scriere sunt separate;
- scrierile sunt dry-run implicit și necesită `--apply`;
- algoritmii SSH vechi sunt izolați per dispozitiv;
- auditul SSH este configurabil global sau per sesiune și produce fișiere private.
- parolele Vault respinse sunt diagnosticate din codul 5 `sshpass`, cu o
  reîncercare OpenSSH confirmată de operator pentru ținte generice.
- comenzile remote neinteractive pot reutiliza secretul SSH pentru sudo sau un
  secret sudo separat în profilul de credențiale.
- autocomplete-ul Bash acoperă comenzile, valorile valide și navigarea în audit.

## Cerințe și instalare

Debian 10+, Python 3.7+, `openssh-client`, uneltele Net-SNMP și phpIPAM prin HTTPS. Opțional: `sshpass`, `pass`, `gnupg`, clientul izolat `/usr/bin/ssh1` și systemd.

```bash
git clone https://github.com/stancufm/gr-ipam.git
cd gr-ipam
sudo sh install.sh --base-url https://ipam.example.net --username gr-api \
  --ca-file ./organization-ca.pem --enable-timer
gr init --configure-auth
gr doctor --api
```

Dacă phpIPAM folosește un certificat emis de o CA publică, omiteți `--ca-file`.

## Utilizare

```bash
gr find core-switch
gr find core-switch --details
gr --ssh core-switch
gr --ssh --audit core-switch
gr exec linux-server --sudo -- systemctl status nginx
gr config set ssh_audit_enabled true
gr audit show core-switch latest
gr config show
gr update 192.0.2.10 --ssh-enabled yes --ssh-user operator --apply
gr vendor list
gr vendor lookup e8:d3:22:00:00:01
gr ssh validate
gr collect version --ip 192.0.2.10
gr collect reports latest
gr snmp report --ip 192.0.2.10 --mode inventory
gr snmp test --ip 192.0.2.10
gr self-update check
```

## Documentație

- [Instalare](docs/INSTALL.ro.md)
- [Arhitectură](docs/ARCHITECTURE.ro.md)
- [Securitate](docs/SECURITY-MODEL.ro.md)
- [Audit SSH](docs/AUDIT.ro.md)
- [Administrare SNMP pe bază de template-uri](docs/SNMP.ro.md)
- [Actualizare semnată](docs/UPDATE.ro.md)
- [Ghid complet](docs/GR-PHPIPAM.ro.md)
- [Pregătire phpIPAM](phpipam/SETUP.ro.md)
- [Contribuții](CONTRIBUTING.ro.md)

Versiunea `2.6.1` nu include credențiale, chei, exporturi de inventar sau adrese interne. Proiectul este disponibil sub [licența MIT](LICENSE).
