# Dezvoltare remote cu Codex

[English](REMOTE-DEVELOPMENT.md)

Folosiți un cont Linux dedicat și neprivilegiat pe un host de dezvoltare. Instalați Codex CLI în PATH-ul shell-ului login, autentificați cu `codex login --device-auth`, clonați repository-ul într-un director deținut de utilizator și acordați Git numai credențiale pentru acest repository. Verificați `.codex/setup.sh`.

Configurați în desktop un alias SSH concret, cu cheie dedicată și `IdentitiesOnly yes`. Accesul la proiect este transportat prin SSH; nu expuneți listenerul app-server. `sudo` rămâne interactiv și este folosit numai pentru operații cerute explicit.

```bash
git checkout main
git pull --ff-only
git checkout -b codex/descriere
.codex/setup.sh
# implementare și teste
git diff --check
git push -u origin codex/descriere
```

Deschideți PR și integrați numai după validări.
