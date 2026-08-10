# Pregătirea phpIPAM pentru gr

[English](SETUP.md)

Pentru o instalare nouă, pachetul include helperul idempotent
`phpipam/ensure-custom-fields.php`. După backupul bazei, copiați-l și rulați-l
local pe VM-ul phpIPAM:

```bash
sudo /usr/local/share/gr/phpipam/ensure-custom-fields.php \
  /var/www/html/phpipam/config.php
```

Acesta creează numai cele opt câmpuri lipsă, validează tipurile existente și
nu salvează sau afișează credențialele SQL. `gr doctor --api` verifică apoi din
jump server că întreaga schemă necesară este vizibilă prin API.

Creați două aplicații API separate: una read-only pentru căutare/inventar și una cu drepturile minime necesare pentru operațiile explicite `--apply`. Folosiți HTTPS și o CA de încredere; nu stocați parole SSH în phpIPAM.

Adăugați câmpurile custom standard pentru adrese: `ssh_enabled`, `ssh_user`,
`ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client`, `device_driver` și, dacă
este folosită sincronizarea IEEE, `device_vendor`. Profilul selectează numai
secretul criptat local. `ssh_client` acceptă `normal` sau `legacy`, iar
`device_driver` descrie comportamentul CLI independent de credențiale.

Acordați utilizatorului API numai subrețelele și operațiile necesare. Verificați aplicația read-only cu `gr auth test` și `gr doctor --api`. Previzualizați orice migrare sau actualizare fără `--apply`, limitați primul pilot și revizuiți raportul privat înainte de extindere.

phpIPAM rămâne sursa de adevăr pentru hostname și inventar. Nu modificați schema sau codul phpIPAM și nu importați credențiale, chei ori fișiere de audit.
