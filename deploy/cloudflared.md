# Cloudflare Tunnel za api.terpenstation.com

Server nema otvoren port: `cloudflared` sam otvara vezu prema Cloudflareu, a Cloudflare na nju šalje promet za `api.terpenstation.com` (W09). Postavljeno 26. 10. 2026; tunel se zove `trgovina`.

1. Cloudflare nadzorna ploča: **Networking → Tunnels → Create a tunnel** (vrsta *Cloudflared*), ime `trgovina`, **Create Tunnel**.

2. **Setup Environment:** Debian, 64-bit. Naredbe pod **Install and Run** pokreću se kao root na Netcupu: instaliraju `cloudflared` iz Cloudflareova repozitorija i servis s ključem tunela, pa se tunel sam diže pri svakom paljenju servera. Ključ je u naredbi i ne ide ni u chat ni u repo. Naredbe počinju sa `sudo`, pa na Debianu bez njega prvo `apt-get install -y sudo`. Kad se server u ploči pokaže kao *Connected*, **Continue**.

3. Na stranici tunela `trgovina`: kartica **Routes → Add route → Published application**:
   - Subdomain: `api`, Domain: `terpenstation.com`, Path prazno
   - Service URL: `http://127.0.0.1:8090`

   **Networking → Routes** u izborniku lijevo je za privatne mreže (Tunnel CIDR, Tunnel Hostname, Mesh); to nije ovo.

4. Provjera s bilo kojeg računala: `https://api.terpenstation.com/zdravlje` vraća `ok`.
