# Pool-uri pentru colectarea programată a configurațiilor

GR are deja `gr collect config` și arhiva Git globală. Propunerea adaugă
pool-uri declarative și scheduler, fără credențiale sau comenzi SSH în cron.

Interfața propusă este `--pool`, `--due`, `pools` și `status`. phpIPAM rămâne
sursa de adevăr; se acceptă numai ținte cu driver GR explicit și SSH activ.

Pachetul GR instalează unitățile systemd atât la instalare nouă, cât și la
upgrade și execută `daemon-reload`. Timerul rămâne dezactivat implicit și se
activează explicit doar pe nodul HA activ. Upgrade-ul nu pornește colectări.

Arhiva `/var/lib/gr/config-archive` trebuie inclusă în exportul HA; standby-ul
o replică, dar nu scrie în ea până la promovare manuală validată.
