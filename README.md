# Terpen Station webshop

Trgovina na [terpenstation.com](https://terpenstation.com): statični sajt na Cloudflare Pagesu, proizvodi kroz Sveltia CMS na `/admin`, a narudžbe prima mali backend na Netcupu (`api.terpenstation.com`, preko Cloudflare Tunnela). Veleprodajna stranica je na `/wholesale/`.

```
frend (mobitel) → terpenstation.com/admin (Sveltia CMS) → commit u ovaj repo
GitHub → Cloudflare Pages: python -m web gradi → dist/
kupac → sajt → košarica (localStorage) → blagajna → POST api.terpenstation.com/narudzba
api.terpenstation.com → Cloudflare Tunnel → Netcup, korisnik trgovina → gunicorn :8090 → SQLite, Gmail SMTP, BOX NOW
```

Pravila koda i raspored datoteka su u `CLAUDE.md`. Postavljanje se radi jednom, korak po korak u chatu s Claudeom (SPEC §13); ovdje je sažetak.

## Lokalno

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[razvoj]"
pytest && ruff check .

python -m web gradi            # sajt u dist/
python -m web posluzi          # http://localhost:8000
```

Probna narudžba s lokalnim backendom (u drugom terminalu), mailovi idu u pravi inbox:

```bash
export SAJT_ADRESA=http://localhost:8000 SAJT_API=http://localhost:8090
export SMTP_LOZINKA='app password trgovina' TAJNA_LINKOVA=proba
python -m web gradi            # obrazac blagajne sad šalje na localhost:8090
python -m backend migriraj
python -m backend posluzi      # http://localhost:8090
```

Mail trgovini ide na `[mail].trgovina` iz `postavke.toml`; za probu se tamo privremeno upiše vlastita adresa. Bez Gmaila: `SMTP_POSLUZITELJ=127.0.0.1:1025` šalje u lokalni hvatač mailova (bez TLS-a i prijave).

## 1. Cloudflare Pages

Sadašnji Pages projekt je napravljen uploadom zipa i ne može se spojiti na GitHub, pa se radi novi.

1. **Workers & Pages → Create → Pages → Connect to Git**, repo `zuki666/terpenstation-web`, grana `main`.
2. Build command: `pip install .[web] && python -m web gradi`; Build output directory: `dist`.
3. Environment variable `PYTHON_VERSION` = `3.12` ako zadani Python u gradnji nije 3.11 ili noviji.
4. Kad prva gradnja prođe: na starom projektu makni domenu `terpenstation.com`, na novom je dodaj (**Custom domains**).

Svaki commit (i svako spremanje u CMS-u) pokrene gradnju; za minutu-dvije promjena je na sajtu. Kad gradnja padne, ostaje zadnja dobra verzija.

## 2. CMS na /admin

Prijava u Sveltia CMS ide preko GitHuba, kroz mali Cloudflare Worker.

1. **Worker:** na <https://github.com/sveltia/sveltia-cms-auth> gumb *Deploy to Cloudflare Workers*. Zapiši adresu Workera (`https://sveltia-cms-auth.<račun>.workers.dev`).
2. **GitHub OAuth aplikacija:** GitHub → Settings → Developer settings → OAuth Apps → New. Homepage `https://terpenstation.com`, Authorization callback URL `<adresa Workera>/callback`. Zapiši Client ID i napravi Client secret.
3. **Varijable Workera** (Settings → Variables): `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (kao *Secret*), `ALLOWED_DOMAINS` = `terpenstation.com`.
4. U `static/admin/config.yml` zamijeni `RACUN` u `base_url` adresom Workera (PR).
5. **Frend:** GitHub račun s njegovim mailom, poziv u ovaj repo s pravom pisanja (Settings → Collaborators). Na njegovom mobitelu otvori `terpenstation.com/admin`, prijava kroz GitHub, pa *Dodaj na početni zaslon*.

## 3. Mail

1. Google Admin: alias `narudzbe@terpenstation.com` na korisniku sales@.
2. Na sales@: novi app password, ime „trgovina” (botov ostaje kakav je).
3. Gmail → Postavke → Računi → *Šalji poštu kao*: dodaj `narudzbe@terpenstation.com`.
4. Filter: *Prima* ili *Šalje* `narudzbe@terpenstation.com` → *Preskoči pristiglu poštu*, oznaka „Narudžbe”. Bot čita samo INBOX (W16).

Promjena lozinke Google računa poništi oba app passworda; tada se prave novi i upisuju u `.env` bota i trgovine.

## 4. Server (Netcup)

Kao root:

```bash
adduser --disabled-password --gecos "" trgovina
su - trgovina
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 && cat ~/.ssh/id_ed25519.pub
```

Javni ključ ide u GitHub → repo → Settings → Deploy keys (samo čitanje). Zatim kao `trgovina`:

```bash
git clone git@github.com:zuki666/terpenstation-web.git && cd terpenstation-web
python3 -m venv .venv && .venv/bin/pip install ".[backend]"
cp deploy/.env.example .env && nano .env      # SMTP_LOZINKA i TAJNA_LINKOVA
.venv/bin/python -m backend migriraj
```

Kao root:

```bash
cp /home/trgovina/terpenstation-web/deploy/trgovina*.service /home/trgovina/terpenstation-web/deploy/trgovina*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now trgovina.service trgovina-mailovi.timer trgovina-backup.timer
curl http://127.0.0.1:8090/zdravlje          # ok
```

Tunel za `api.terpenstation.com`: `deploy/cloudflared.md`.

**Ažuriranje** nakon spojenog PR-a: kao `trgovina` `git pull && .venv/bin/pip install ".[backend]" && .venv/bin/python -m backend migriraj`, pa kao root `systemctl restart trgovina`.

**Dnevnik:** `journalctl -u trgovina -f`. Kopije baze su u `backup/` (30 dana).

## 5. BOX NOW (W4)

U `postavke.toml` (`[boxnow]`): `partner_id`, `skladiste` (Warehouse ID); u `.env`: `BOXNOW_API_URL`, `BOXNOW_CLIENT_ID`, `BOXNOW_CLIENT_SECRET`. Dok `partner_id` nije upisan, blagajna umjesto karte paketomata ima probno polje za ID paketomata. Widget radi samo s produkcijom.

Pošiljka nastaje klikom na link u mailu trgovini, pa na gumb (W19); ponovni klik vraća istu naljepnicu. Otkazivanje ide kroz BOX NOW partnerski portal.

## Nova država

Bez promjene koda (SPEC §10): `drzave/<kod>.toml`, `jezici/<jezik>.toml` (test javi ključ koji fali), `sadrzaj/stranice/<kod>/*.md`, jezik u `locales` u `static/admin/config.yml`. Izbornik država i `hreflang` pojave se sami.
