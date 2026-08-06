# Reguli de dezvoltare gr-ipam

[English](AGENTS.md)

## Compatibilitate

CLI-ul rămâne fără dependențe Python, compatibil cu Python 3.7+ și Debian 10. phpIPAM este sursa de adevăr; folosiți numai câmpuri custom standard.

## Siguranță

Nu comiteți credențiale, tokenuri, chei, CA-uri interne, scanări, inventare, rapoarte sau fișiere de audit `.ses`. Separați aplicațiile API read/write. Scrierile sunt dry-run implicit și cer `--apply`. Clientul SSH legacy se selectează numai per dispozitiv. Nu faceți deploy în producție fără cerere explicită și nu adăugați reguli sudo largi.

## Flux

Porniți din `main` actualizat pe `codex/<nume>`. Păstrați commituri focalizate și actualizați documentația în ambele limbi. Înainte de commit rulați `.codex/setup.sh` și `git diff --check`; testați instalarea cu `--destdir`, scanați conținutul staged și deschideți PR. Folosiți versiuni semantice și GitHub Releases.

## Structură

`bin/gr` este CLI-ul principal; `libexec/` conține helper-ele; `examples/` șabloane fără date reale; `phpipam/` pregătirea serverului; `systemd/` actualizarea IEEE; `docs/` documentația EN/RO.
