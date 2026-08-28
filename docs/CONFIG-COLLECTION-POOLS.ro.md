# Pool-uri pentru colectarea programată a configurațiilor

[English](CONFIG-COLLECTION-POOLS.md)

GR colectează configurațiile în arhiva Git globală prin `gr collect config`.
Pool-urile denumite adaugă programare periodică fără credențiale, comenzi SSH
sau un inventar paralel în cron.

## Model de execuție și siguranță

phpIPAM rămâne autoritatea pentru ținte, hostname-uri, drivere și metadate SSH.
Un pool conține numai selectori. Fiecare țintă trebuie să aibă SSH activ,
profil, driver explicit diferit de `generic` și comandă de colectare. O țintă
respinsă oprește pool-ul înaintea oricărei conexiuni la echipamente.

Rulările programate folosesc contul de sistem dedicat și blocat
`gr-collector`. Nu depind de loginul unui administrator, de
`loginctl enable-linger` sau de home-ul unei persoane. Comenzile GR interactive
continuă să folosească configurația și Vault-ul operatorului curent.

Schedulerul:

- este dezactivat la instalare și upgrade;
- folosește un lock neblocant pentru a evita rulările suprapuse;
- limitează workerii la 1-12 și validează fiecare setare;
- reîncearcă eșecurile după `retry_interval`;
- verifică markerul HA activ și fereastra opțională de mentenanță;
- creează commit numai pentru configurații normalizate modificate.

Într-o instalare HA, collectorul primește numai drept de traversare, nu de
listare sau citire, pe `/etc/jumpserver-ha`, pentru a verifica markerul fix și
world-readable `active`. Installerul folosește un ACL dedicat utilizatorului;
fișierele HA protejate își păstrează permisiunile limitate la grup. Mecanismul
funcționează indiferent dacă GR sau `jumpserver-ha` este instalat primul.

Lock-ul este în `.git` al arhivei, deci nu poate apărea ca artefact neversionat.

## Configurație și credențiale dedicate

Serviciul citește `/etc/gr/collector.json`; pornește de la
`examples/collector.json`. Starea privată este în
`/var/lib/gr-collector/config-collection`. Configurează autentificarea API și
profilurile SSH criptate special pentru `gr-collector`. Nu copia integral
home-ul sau cheile private ale unui utilizator. Validează accesul API și Vault
într-o sesiune controlată a contului de serviciu înainte de activarea timerului.

Administratorul îl poate inițializa dintr-un TTY fără a-i activa shell de
login:

```text
sudo -u gr-collector env HOME=/var/lib/gr-collector \
  gr --config /etc/gr/collector.json init --configure-auth
sudo -u gr-collector env HOME=/var/lib/gr-collector \
  gr --config /etc/gr/collector.json doctor --api
```

Pool-urile nu conțin secrete în clar. GR nu salvează fraza GPG pentru rulări
neasistate. Mediul trebuie să ofere contului de serviciu un mecanism aprobat de
deblocare neinteractivă; altfel timerul rămâne oprit și pool-urile se rulează
interactiv.

Setările `config_collection` sunt `state_dir`, `scheduler_enabled`,
`active_marker` și `pools`. Fiecare pool cere `interval` și cel puțin un
selector dintre `ips`, `hostname_regex`, `vendor` sau `driver`. Selectorii se
combină cu AND. Sunt disponibile `enabled`, `retry_interval`, `workers`,
`exclude_ips`, `exclude_hostnames` și `maintenance_window` în ora
Europe/Bucharest. Intervalele folosesc `m`, `h` sau `d`, între 15 minute și 365
zile. `gr collect config pools` raportează suprapunerile ca atenție.

## Comenzi

```text
gr collect config pools
gr collect config status
gr collect config --pool critical
gr collect config --due
```

`pools` și `status` sunt read-only. `--pool` rulează imediat un pool; `--due`
respectă activarea, markerul HA, intervalul, retry-ul și fereastra de
mentenanță. Comenzile directe folosesc în continuare operatorul curent.

Liniile `RESULT` eșuate includ un motiv stabil, de exemplu
`ssh-key-exchange`, `ssh-host-key`, `ssh-authentication` sau
`connection-timeout`. Sumarul schedulerului nu copiază stderr-ul SSH brut și
nu include secrete.

După configurare și validare pe nodul HA activ:

```text
sudo systemctl daemon-reload
sudo systemctl start gr-config-collect@critical.service
sudo systemctl enable --now gr-config-collect.timer
systemctl status gr-config-collect.timer
journalctl -u gr-config-collect.service
```

Unitatea template permite rularea explicită a unui pool sub identitatea de
serviciu. Instalarea și upgrade-ul nu activează timerul. La demotion, markerul
HA blochează `--due`; timerul trebuie dezactivat și ca protecție suplimentară.

## Arhivă și HA

`/var/lib/gr/config-archive` aparține `gr-collector:gr-config` și are modul
`2770`. Operatorii din `gr-config` pot citi istoricul și pot face colectări
interactive explicite, dar nu dețin procesul programat. Configurațiile pot
conține secrete, deci grupul rămâne restrâns.
Installerul înregistrează numai această cale exactă drept Git
`safe.directory`; nu activează niciodată o regulă wildcard.

Proiectul `jumpserver-ha` este singura autoritate de replicare spre standby. El
păstrează proprietarii numerici, ACL-urile și atributele extinse și menține
colectarea oprită pe standby până la promovare. Nu configura o a doua cale Git
și nu porni timerul GR pe ambii peers.

## Recuperare

Verifică starea cu configurația colectorului și jurnalul systemd. Repară
metadatele phpIPAM, Vault-ul sau accesul la echipament, apoi rulează numai
pool-ul afectat. Eșecul devine eligibil după `retry_interval`, iar succesul
manual actualizează atomic aceeași stare.
