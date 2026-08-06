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

Redarea tuturor octeților:

```bash
gr audit show ~/.local/state/gr/audit/core-switch/core-switch-20260806T120000.000000Z.ses
```

## Securitate și operare

Fișierele de sesiune sunt excluse din Git și trebuie protejate ca niște credențiale: acces minim, backup criptat, reguli de retenție și ștergere, fără atașare la issue-uri publice. Redarea expune stdin, inclusiv parolele tastate când ecoul terminalului era oprit. Parolele automate transmise de `sshpass` nu traversează stdin-ul terminalului și nu sunt copiate în audit decât dacă sistemul distant le afișează.

Fiecare cadru este salvat imediat, iar fișierul este sincronizat la închiderea normală. O oprire brutală poate lăsa un prefix valid fără înregistrarea finală.
