# Auditarea sesiunilor SSH

[English](AUDIT.md)

`gr` poate înregistra fiecare octet transferat într-o sesiune SSH interactivă. Sunt capturate separat stdin, stdout și stderr. Prin urmare, fișierul poate conține parole introduse la prompt, tokenuri, date private și comenzi.

## Configurare

Valori globale în `/etc/gr/config.json` sau în configurația utilizatorului:

```json
"ssh_audit_enabled": true,
"ssh_audit_dir": "~/.local/state/gr/audit"
```

Activare sau dezactivare pentru o singură conectare:

```bash
gr --ssh --audit core-switch
gr --ssh --no-audit core-switch
```

Opțiunea sesiunii are prioritate față de setarea globală. Auditarea necesită un terminal interactiv.

## Stocare și format

O conectare creează:

```text
<director-audit>/<hostname-sau-ip>/<hostname-sau-ip>-<start-UTC>.ses
```

Directoarele au modul `0700`, iar fișierele `0600`. Formatul `.ses` este JSON Lines. Prima înregistrare conține metadatele, fiecare cadru conține timpul relativ, canalul și octeții originali codificați Base64, iar ultima înregistrare conține codul de ieșire. Astfel se păstrează exact datele și separarea stdin/stdout/stderr.

Navigarea pornește de la echipament, apoi restrânge lista la sesiunile
hostname-ului sau IP-ului ales, fără memorarea căilor:

```bash
gr audit show
gr audit show core-switch
gr audit show core-switch latest
gr audit show 192.0.2.10 core-switch-20260806T120000.000000Z
```

Prima comandă afișează hostname-ul, IP-ul, numărul sesiunilor și cea mai recentă
dată UTC. A doua afișează sesiunile și codurile lor de ieșire. `latest` redă
ultima sesiune. Calea directă rămâne compatibilă:

```bash
gr audit show ~/.local/state/gr/audit/core-switch/core-switch-20260806T120000.000000Z.ses
```

Redarea implicită include stdout și stderr. Stdin rămâne integral în fișierul
`.ses`, dar este omis din vizualizarea normală deoarece majoritatea
echipamentelor retransmit caracterele tastate pe stdout; combinarea celor două
copii ar dubla vizual comenzile. Pentru analiză completă sau un singur flux:

```bash
gr audit show core-switch latest --include-stdin
gr audit show core-switch latest --stream stdin
gr audit show core-switch latest --stream stderr
```

Redarea interactivă folosește automat `less`, iar în lipsa lui `more`. Pipe-urile
și redirectările nu pornesc pagerul. Pagerul poate fi ales prin `GR_PAGER` sau
`PAGER`, ori dezactivat pentru o redare:

```bash
gr audit show core-switch latest --no-more
GR_PAGER="less -R" gr audit show core-switch latest
```

## Autocomplete Bash

Installerul global salvează completarea în `/etc/bash_completion.d/gr`.
Deschideți o sesiune Bash nouă sau încărcați-o imediat:

```bash
source /etc/bash_completion.d/gr
```

Sunt completate comenzile, opțiunile și valorile valide, profilurile SSH,
hostname-urile/IP-urile auditate și sesiunile țintei selectate. Bash afișează
implicit variantele ambigue după două apăsări Tab. Pentru afișare de la prima
apăsare, în stil Cisco, setați înainte de încărcarea completării:

```bash
export GR_COMPLETION_CISCO_STYLE=1
```

Pentru persistență, puneți exportul în `~/.bashrc` înaintea încărcării
Bash-completion. Sursa poate fi afișată și cu `gr completion bash`.

## Securitate și operare

Fișierele de sesiune sunt excluse din Git și trebuie protejate ca niște credențiale: acces minim, backup criptat, reguli de retenție și ștergere, fără atașare la issue-uri publice. Redarea expune stdin, inclusiv parolele tastate când ecoul terminalului era oprit. Parolele automate transmise de `sshpass` nu traversează stdin-ul terminalului și nu sunt copiate în audit decât dacă sistemul distant le afișează.

Fiecare cadru este salvat imediat, iar fișierul este sincronizat la închiderea normală. O oprire brutală poate lăsa un prefix valid fără înregistrarea finală.
