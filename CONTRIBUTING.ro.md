# Contribuții

[English](CONTRIBUTING.md)

Pentru release, păstrați `VERSION` și `GR_VERSION` identice și publicați numai un tag adnotat semnat `vX.Y.Z`, după trecerea CI. Cheia privată de semnare nu se comite și nu se instalează pe jumpserver.

Păstrați compatibilitatea cu Python 3.7 și Debian 10. Nu adăugați dependențe Python în CLI și nu modificați sursa sau schema phpIPAM.

Porniți de pe un `main` actualizat și lucrați pe un branch `codex/<descriere>`:

```bash
git checkout main
git pull --ff-only
git checkout -b codex/descriere
.codex/setup.sh
git diff --check
```

Modificările de comportament trebuie însoțite de documentație în engleză și română. Testați instalarea numai cu `--destdir`. Nu comiteți credențiale, chei, CA-uri interne, fișiere `.ses`, rapoarte, scanări, inventare sau adrese interne. Operațiile de scriere rămân dry-run implicit și necesită `--apply`. Deschideți un pull request focalizat și integrați numai după trecerea GitHub Actions.
