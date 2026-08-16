# Pool-uri pentru colectarea programată a configurațiilor

GR poate colecta configurațiile în arhiva Git globală prin
`gr collect config`. Pool-urile denumite adaugă programare periodică fără
credențiale, comenzi SSH sau un inventar paralel în cron.

## Model și siguranță

phpIPAM rămâne sursa de adevăr pentru ținte, hostname, driver și metadatele SSH.
Un pool conține numai selectori. Fiecare țintă rezolvată trebuie să aibă SSH
activ, profil, driver GR explicit diferit de `generic` și comandă de extragere.
O țintă respinsă oprește pool-ul înaintea oricărei conexiuni; nu este omisă
silencios.

Schedulerul:

- este dezactivat implicit și nu este activat de instalare sau upgrade;
- folosește un singur lock, astfel încât rulările manuale și timerul nu se
  suprapun;
- validează toate cheile și limitează workerii la 1-12;
- scrie atomic numai stare rezumativă sigură, cu mod `0600` într-un director
  `0700`;
- reîncearcă un pool eșuat după `retry_interval`, nu la fiecare tick;
- verifică opțional markerul nodului activ și fereastra de mentenanță;
- deleagă colectarea și commitul în arhivă colectorului existent.

Pool-urile nu conțin secrete. Parolele echipamentelor sunt citite din profilurile
SSH criptate existente. Pentru o rulare neasistată, utilizatorul serviciului
trebuie să poată decripta profilurile fără pinentry grafic. Verifică anterior în
aceeași sesiune cu `gr vault test PROFIL`; GR nu slăbește Vault-ul și nu salvează
fraza GPG pentru scheduler.

## Configurare

Adaugă obiectul `config_collection` în configurația JSON GR de sistem sau a
utilizatorului. Exemplul complet este în
`examples/config-collection-pools.json`.

- `state_dir`: starea per utilizator, implicit
  `~/.local/state/gr/config-collection`;
- `scheduler_enabled`: trebuie să fie `true` pentru ca `--due` să lucreze;
- `active_marker`: cale opțională care trebuie să existe pe nodul HA activ;
- `pools`: obiectele pool denumite.

Fiecare pool necesită `interval` și cel puțin un selector: `ips`,
`hostname_regex`, `vendor` sau `driver`. Selectorii aceluiași pool se combină cu
AND. Sunt acceptate `enabled`, `retry_interval`, `workers`, `exclude_ips`,
`exclude_hostnames` și o `maintenance_window` în ora locală Europe/Bucharest,
cu `days`, `start` și `end`. Intervalele folosesc `m`, `h` sau `d`, între 15
minute și 365 zile.

Pool-urile trebuie să nu se suprapună. `gr collect config pools` raportează
suprapunerile ca atenție pentru a evita colectarea dublă.

## Comenzi

```text
gr collect config pools
gr collect config status
gr collect config --pool critical
gr collect config --due
```

`pools` rezolvă inventarul și eligibilitatea fără a contacta echipamentele.
`status` citește numai starea locală. `--pool` rulează imediat un pool;
`--due` respectă activarea schedulerului, markerul HA, intervalul, retry-ul și
fereastra de mentenanță. Comenzile directe existente rămân neschimbate.

## Timer systemd al utilizatorului

Pachetul instalează `gr-config-collect.service` și `.timer` în
`/etc/systemd/user`. Unitățile rulează ca operatorul, pentru a utiliza
configurația API și Vault-ul său, fără un cont hardcodat. După configurarea și
validarea pool-urilor pe nodul activ:

```text
systemctl --user daemon-reload
systemctl --user enable --now gr-config-collect.timer
systemctl --user status gr-config-collect.timer
journalctl --user -u gr-config-collect.service
```

Pentru rulare fără login interactiv, administratorul poate activa explicit
systemd user lingering pentru contul ales. Se face numai pe peer-ul HA activ.
La demotion se dezactivează timerul sau se elimină markerul activ. Upgrade-urile
păstrează starea timerului și nu îl activează.

Arhiva autoritativă `/var/lib/gr/config-archive` trebuie replicată pe standby cu
owner, grup și mod păstrate. Standby-ul poate citi arhiva, dar nu colectează până
la promovarea validată.

## Recuperare

La eșec, verifică `gr collect config status` și jurnalul utilizatorului. Repară
metadatele phpIPAM, disponibilitatea Vault-ului sau accesul la echipament, apoi
rulează manual pool-ul afectat. Nu este nevoie să ștergi `state.json`: eșecul
devine eligibil după `retry_interval`, iar succesul manual actualizează atomic
aceeași stare.
