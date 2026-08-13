# Pregătirea phpIPAM pentru gr

[English](SETUP.md)

Pentru o instalare nouă, pachetul include helperul idempotent
`phpipam/ensure-custom-fields.php`. După backupul bazei, copiați-l și rulați-l
local pe VM-ul phpIPAM:

```bash
sudo /usr/local/share/gr/phpipam/ensure-custom-fields.php \
  /var/www/html/phpipam/config.php
```

Acesta creează numai câmpurile lipsă, validează tipurile existente și
nu salvează sau afișează credențialele SQL. `gr doctor --api` verifică apoi din
jump server că întreaga schemă necesară este vizibilă prin API.

Creați două aplicații API separate: una read-only pentru căutare/inventar și una cu drepturile minime necesare pentru operațiile explicite `--apply`. Folosiți HTTPS și o CA de încredere; nu stocați parole SSH în phpIPAM.

Adăugați câmpurile custom standard pentru adrese: `ssh_enabled`, `ssh_user`,
`ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client`, `device_driver` și, dacă
este folosită sincronizarea IEEE, `device_vendor`, `device_model`, plus `os_version` pentru
versiunea OS/firmware asociată adresei. Profilul selectează numai
secretul criptat local. `ssh_client` acceptă `normal` sau `legacy`, iar
`device_driver` descrie comportamentul CLI independent de credențiale.

Pentru modulul SNMP adăugați `snmp_enabled`, `snmp_profile`, `snmp_template`,
`monitoring_enabled`, `monitoring_profile` și `monitoring_device_id`. Acestea
memorează intenția și asocierea, niciodată parole SNMP sau tokenul LibreNMS.

Acordați utilizatorului API numai subrețelele și operațiile necesare. Verificați aplicația read-only cu `gr auth test` și `gr doctor --api`. Previzualizați orice migrare sau actualizare fără `--apply`, limitați primul pilot și revizuiți raportul privat înainte de extindere.

Helperul creează și `custom_device_os` (varchar 128) pe tabela nativă `devices`
și verifică existența tipului nativ `Server`. Este idempotent și se oprește în
loc să modifice o coloană existentă incompatibilă.

phpIPAM rămâne sursa de adevăr pentru hostname și inventar. Nu modificați codul phpIPAM și nu importați credențiale, chei ori fișiere de audit.
