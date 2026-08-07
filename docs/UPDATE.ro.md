# Actualizare semnată a aplicației

[English](UPDATE.md)

`gr self-update` actualizează instalarea globală dintr-un tag semantic mai nou, semnat. Nu modifică înregistrări phpIPAM; acestea rămân responsabilitatea comenzii `gr update`.

## Inițializarea încrederii

Updaterul acceptă numai cheia GPG publică de release instalată de administrator. Instalați pachetul inițial cu cheia publică și adresa HTTPS a repository-ului:

```bash
sudo sh install.sh \
  --base-url https://ipam.example.net \
  --username gr-api \
  --release-key ./project-release-key.asc \
  --update-repository https://github.com/stancufm/gr-ipam.git
```

Sunt create `/etc/gr/release-key.asc` și `/etc/gr/update.json`. Cheia privată de semnare trebuie păstrată offline sau într-un mediu protejat al maintainerului și nu se instalează niciodată pe jumpserver.

## Comenzi

```bash
gr self-update check
gr self-update
gr self-update --dry-run
gr self-update --version v1.2.0
gr self-update --yes
```

Verificarea și dry-run-ul rulează fără privilegii. Actualizarea live apelează helperul privilegiat minimal prin `sudo`, astfel încât administratorul poate introduce parola în același terminal interactiv. `--yes` elimină numai confirmarea; nu ocolește sudo, verificarea semnăturii sau controalele de siguranță.

## Tranzacția de actualizare

Helperul:

1. citește configurația HTTPS administrată de root;
2. descoperă taguri stricte `vX.Y.Z` și refuză downgrade-ul;
3. descarcă numai tagul ales într-un repository temporar;
4. importă cheia publică într-un keyring temporar și verifică tagul;
5. impune corespondența dintre tag și `VERSION`;
6. face o instalare izolată `DESTDIR` și verifică versiunea;
7. creează backup privat în `/var/backups/gr/`;
8. instalează păstrând `/etc/gr/config.json`, configurația updaterului și cheia publică;
9. validează CLI-ul instalat și rulează verificarea independentă de credențiale `gr doctor --system`;
10. restaurează automat backupul dacă eșuează un pas ulterior stagingului.

Un lock din `/run/lock/` împiedică actualizările simultane. Backupurile reușite sunt păstrate intenționat pentru retenție și recuperare controlate de administrator.

## Cerințe pentru release

Maintainerul actualizează `VERSION` și `GR_VERSION` la aceeași versiune semantică, face commit, creează un tag adnotat semnat cu prefixul `v` și îl publică. Tagurile nesemnate, versiunile necorespunzătoare, repository-urile fără HTTPS și downgrade-urile sunt refuzate.
