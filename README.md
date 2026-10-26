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
3. **Varijable Workera** (Settings → Variables): `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (kao *Secret*), `ALLOWED_DOMAINS` = `terpenstation.com,www.terpenstation.com`.
4. U `static/admin/config.yml` zamijeni `RACUN` u `base_url` adresom Workera (PR).
5. **Frend:** GitHub račun s njegovim mailom, poziv u ovaj repo s pravom pisanja (Settings → Collaborators). Na njegovom mobitelu otvori `terpenstation.com/admin`, prijava kroz GitHub, pa *Dodaj na početni zaslon*.

**Dnevnik uzgoja** (W8) je druga zbirka u CMS-u. Zapis ima naslov, datum, tekst, fotke ili video (MP4 do 25 MB), fazu i sortu; kvačica „Objavljeno” ga skriva. Dnevnik se pojavi u izborniku čim postoji prvi objavljeni zapis, a zapisi sorte i na stranici proizvoda.

## 3. Mail

1. Google Admin: alias `narudzbe@terpenstation.com` na korisniku sales@.
2. Na sales@: novi app password, ime „trgovina” (botov ostaje kakav je).
3. Gmail → Postavke → Računi → *Šalji poštu kao*: dodaj `narudzbe@terpenstation.com`.
4. Filter: *Prima* ili *Šalje* `narudzbe@terpenstation.com` → *Preskoči pristiglu poštu*, oznaka „Narudžbe”. Bot čita samo INBOX (W16).

Promjena lozinke Google računa poništi oba app passworda; tada se prave novi i upisuju u `.env` bota i trgovine.

## 4. Server (Netcup)

Postavljeno 26. 10. 2026. na Debianu 13 (Python 3.13; `git`, `sqlite3` i `curl` su već bili na serveru). Spaja se iz PowerShella: `ssh root@<IP servera>`.

Kao root:

```bash
apt-get install -y python3-venv
useradd -m -s /bin/bash trgovina
su - trgovina -c 'git clone https://github.com/zuki666/terpenstation-web.git'
su - trgovina -c 'cd terpenstation-web && python3 -m venv .venv && .venv/bin/pip install ".[backend]"'
```

Repo je javan, pa ga server klonira preko HTTPS-a, bez deploy ključa. Ako repo postane privatan, `git pull` prestaje raditi: tada kao `trgovina` `ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519`, javni ključ u GitHub → repo → Settings → Deploy keys (samo čitanje) i `git remote set-url origin git@github.com:zuki666/terpenstation-web.git`.

`.env` kao `trgovina` (`su - trgovina`). Tajna linkova nastane sama, a app password se zalijepi u `read`, pa nije ni na ekranu ni u povijesti naredbi:

```bash
cd terpenstation-web && cp deploy/.env.example .env && chmod 600 .env
sed -i "s|^TAJNA_LINKOVA=.*|TAJNA_LINKOVA=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')|" .env
read -rsp "App password: " LOZ; echo
```

Kad `read` primi app password:

```bash
sed -i "s|^SMTP_LOZINKA=.*|SMTP_LOZINKA=${LOZ// /}|" .env && unset LOZ
grep -c "^SMTP_LOZINKA=[a-z]\{16\}$" .env     # 1
.venv/bin/python -m backend migriraj
exit
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

**Zapisnik:** `journalctl -u trgovina -f`. Kopije baze su u `backup/` (30 dana).

## 5. BOX NOW (W4)

U `postavke.toml` (`[boxnow]`): `partner_id`, `skladiste` (Warehouse ID); u `.env`: `BOXNOW_API_URL`, `BOXNOW_CLIENT_ID`, `BOXNOW_CLIENT_SECRET`. Dok `partner_id` nije upisan, blagajna umjesto karte paketomata ima probno polje za ID paketomata. Widget radi samo s produkcijom.

Pošiljka nastaje klikom na link u mailu trgovini, pa na gumb (W19); ponovni klik vraća istu naljepnicu. Otkazivanje ide kroz BOX NOW partnerski portal.

## Nova država

Bez promjene koda (SPEC §10): `drzave/<kod>.toml`, `jezici/<jezik>.toml` (test javi ključ koji fali), `sadrzaj/stranice/<kod>/*.md`, jezik u `locales` u `static/admin/config.yml`. Izbornik država i `hreflang` pojave se sami.
