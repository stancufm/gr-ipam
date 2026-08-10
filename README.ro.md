# gr-ipam

[English](README.md)

`gr-ipam` este un CLI multi-utilizator pentru jump servere Debian care folosesc phpIPAM drept sursă de adevăr pentru inventarul de rețea și metadatele conexiunilor SSH.

Poate căuta adrese, deschide conexiuni SSH, păstra parolele dispozitivelor într-un seif criptat per utilizator, actualiza baza IEEE OUI, sincroniza producătorii, valida accesul la switch-uri, colecta versiuni și audita integral sesiunile SSH.

## Proprietăți principale

- phpIPAM rămâne sursa de adevăr, fără modificări de schemă sau sursă;
- parolele API și SSH sunt private fiecărui utilizator;
- aplicațiile API de citire și scriere sunt separate;
- scrierile sunt dry-run implicit și necesită `--apply`;
- algoritmii SSH vechi sunt izolați per dispozitiv;
- auditul SSH este configurabil global sau per sesiune și produce fișiere private.
- autocomplete-ul Bash acoperă comenzile, valorile valide și navigarea în audit.

## Cerințe și instalare

Debian 10+, Python 3.7+, `openssh-client` și phpIPAM prin HTTPS. Opțional: `sshpass`, `pass`, `gnupg`, clientul izolat `/usr/bin/ssh1` și systemd.

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
gr audit show core-switch latest
gr config show
gr update 192.0.2.10 --ssh-enabled yes --ssh-user operator --apply
gr vendor lookup e8:d3:22:00:00:01
gr ssh validate
gr collect version --ip 192.0.2.10
gr self-update check
```

## Documentație

- [Instalare](docs/INSTALL.ro.md)
- [Arhitectură](docs/ARCHITECTURE.ro.md)
- [Securitate](docs/SECURITY-MODEL.ro.md)
- [Audit SSH](docs/AUDIT.ro.md)
- [Actualizare semnată](docs/UPDATE.ro.md)
- [Ghid complet](docs/GR-PHPIPAM.ro.md)
- [Pregătire phpIPAM](phpipam/SETUP.ro.md)
- [Contribuții](CONTRIBUTING.ro.md)

Versiunea `1.4.0` nu include credențiale, chei, exporturi de inventar sau adrese interne. Proiectul este disponibil sub [licența MIT](LICENSE).
