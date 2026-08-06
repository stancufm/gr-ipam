# Pregătirea phpIPAM pentru gr

[English](SETUP.md)

Creați două aplicații API separate: una read-only pentru căutare/inventar și una cu drepturile minime necesare pentru operațiile explicite `--apply`. Folosiți HTTPS și o CA de încredere; nu stocați parole SSH în phpIPAM.

Adăugați câmpurile custom standard pentru adrese: `ssh_enabled`, `ssh_user`, `ssh_port`, `ssh_profile`, `ssh_jump`, `ssh_client` și, dacă este folosită sincronizarea IEEE, `device_vendor`. Profilul este doar un nume care selectează secretul criptat local. `ssh_client` acceptă `normal` sau `legacy`.

Acordați utilizatorului API numai subrețelele și operațiile necesare. Verificați aplicația read-only cu `gr auth test` și `gr doctor --api`. Previzualizați orice migrare sau actualizare fără `--apply`, limitați primul pilot și revizuiți raportul privat înainte de extindere.

phpIPAM rămâne sursa de adevăr pentru hostname și inventar. Nu modificați schema sau codul phpIPAM și nu importați credențiale, chei ori fișiere de audit.
