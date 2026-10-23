# CLAUDE.md — Terpen Station webshop

Lagani B2C webshop na terpenstation.com: statični sajt na Cloudflare Pagesu (gradnja u Pythonu), Sveltia CMS na `/admin` za proizvode i mali Flask backend na Netcupu za narudžbe. Narudžba je mail trgovini uz potvrdu kupcu; nema admin panela ni Telegrama.

Specifikacija (`SPEC.md`), odluke (`ODLUKE.md`), status (`STATUS.md`) i kontekst (`KONTEKST.md`) vode se u claude.ai Projektu „b2c web”. Kad se razilaze: ODLUKE > SPEC > KONTEKST. Pravna pitanja su riješena izvan projekta i ne otvaraju se (W01).

## Rad

- Gradi se korak po korak (W1–W6 u `STATUS.md`). Jedan korak = jedna grana i jedan pull request. Merge ide kad prođu testovi i ruff; korak je gotov (☑) tek kad prođe njegov kriterij.
- Frend sprema proizvode kroz CMS izravno u `main`; Claudeov kod uvijek ide kroz PR.
- Svako odstupanje od SPEC-a upisuje se kao nova odluka u `ODLUKE.md`.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[razvoj]"
python -m web gradi && python -m web posluzi     # sajt na http://localhost:8000
python -m backend migriraj                       # prvo pokretanje i nakon nove migracije
pytest
ruff check . && ruff format --check .
```

Python 3.11+ (zbog `tomllib`); server ima 3.13.

## Gdje je što

| Što | Gdje |
|---|---|
| Zajedničke postavke (mail, BOX NOW, zaštita, kategorije) | `postavke.toml` |
| Država: put, valuta, PDV, dostave, plaćanja, cijene, primatelj | `drzave/<kod>.toml` |
| Svi tekstovi sučelja, mailova i grešaka, oblik iznosa, URL-ovi | `jezici/<jezik>.toml` |
| Proizvodi (piše CMS) | `sadrzaj/proizvodi/*.json` |
| Pravne stranice | `sadrzaj/stranice/<kod>/<ključ>.md` |
| Predlošci stranica i mailova (isti za sve države) | `predlosci/` |
| Gradnja sajta | `web/` |
| Backend | `backend/`, migracije u `backend/migracije/` |
| systemd, primjer `.env`, Tunnel | `deploy/` |

## Pravila koda

- Imena datoteka, funkcija, varijabli, stupaca i ključeva na hrvatskom, bez dijakritika.
- Komentar objašnjava zašto, nikad što. Bez zakomentiranog koda, povijesti razvoja i AI tragova.
- Jedna funkcija, jedan posao. Datoteka do ~300 redaka, funkcija do ~60, najviše 4 parametra. Nema `utils.py`; pomoćna funkcija živi uz ono čemu služi.
- Tekstovi su u `jezici/`, postavke države u `drzave/`, proizvodi u `sadrzaj/`, nikad u kodu. Država se nikad ne kopira kao kod.
- Iznosi su cijeli brojevi u centima; decimalni broj samo na ulazu (CMS) i izlazu (prikaz).
- Cijene narudžbe računa backend iz objavljenog `proizvodi.json`; cijena iz preglednika se ne koristi (W14).
- Neispravan proizvod ne ruši gradnju: preskače se uz upozorenje (W15).
- `try/except` samo oko mreže (SMTP, BOX NOW, dohvat `proizvodi.json`) i na granici zahtjeva.
- Jinja ima `StrictUndefined` i autoescape: tekst koji fali ruši gradnju i test, ne prazni stranicu.
- `logging`, ne `print`. Ruff (E, F, I, B, UP, C90, PLR, T20, ERA; max-complexity 10, max-args 4) mora proći bez upozorenja.
- Ovisnosti po grupama u `pyproject.toml` (web, backend, razvoj). Novi paket samo uz jak razlog i odluku u ODLUKE.
- Bez kolačića; posjete broji samo Cloudflare Web Analytics, koji Cloudflare ubacuje sam (W34). Košarica je u localStorage, uz rad u memoriji kad ne radi (W18).

## Baza

- SQLite u WAL načinu; veza se otvara samo kroz `baza.povezi()`.
- Migracije su `backend/migracije/NNN_ime.sql`. Spojena migracija se nikad ne mijenja; promjena sheme je nova datoteka bez `BEGIN`/`COMMIT`.
- Vremena u bazi su UTC (`datetime('now')`); prikaz je po zagrebačkom vremenu.
- Narudžba se upiše prije slanja maila; neposlani mail (stupac `mail_*` je NULL) ponavlja timer.

## Tajne

`.env` na serveru, nikad u gitu; popis je u `deploy/.env.example`. Varijabla iz okoline ima prednost pred `.env`. Backend pri pokretanju javi sve tajne koje fale i izađe s kodom 2.
