# Model de securitate

[English](SECURITY-MODEL.md)

Actualizarea aplicației acceptă numai repository-uri HTTPS și taguri semnate cu cheia publică de release fixată de administrator. Cheia privată nu este prezentă pe jumpserver.

Administratorul jump serverului controlează codul și configurația globală. Fiecare utilizator controlează credențiala API, cheia GPG, seiful și rapoartele sale. phpIPAM este de încredere pentru inventar și metadate, nu pentru parole; verificarea cheilor host SSH rămâne activă.

Credențialele și rapoartele au `0600`, directoarele private `0700`, parolele SSH sunt criptate cu pass/GPG, iar `sshpass` primește parola prin descriptor anonim. Scrierile cer `--apply`, aplicațiile API read/write sunt separate și algoritmii vechi rămân în clientul izolat.

Auditul SSH poate conține integral parole tastate, tokenuri și date afișate. Fișierele `.ses` trebuie accesate minimal, păstrate pe stocare criptată, supuse unei politici de retenție și excluse din Git, ticketing și mesagerie. `--no-audit` trebuie permis sau interzis prin politica organizației.

Nu publicați configurații reale, credențiale, chei, CA-uri interne, exporturi phpIPAM, scanări, rapoarte sau audituri. Rulați `gr doctor --api`, revizuiți periodic permisiunile și rotiți parolele. Vulnerabilitățile cu date sensibile se raportează privat proprietarului repository-ului.
