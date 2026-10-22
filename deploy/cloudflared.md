# Cloudflare Tunnel za api.terpenstation.com

Server nema otvoren port: `cloudflared` sam otvara vezu prema Cloudflareu, a Cloudflare na nju šalje promet za `api.terpenstation.com` (W09).

Naredbe se pokreću kao root na Netcupu, jedna po jedna; Claude ih u chatu vodi korak po korak.

1. Instalacija (Debian/Ubuntu), prema uputama na <https://pkg.cloudflare.com>:

   ```sh
   mkdir -p --mode=0755 /usr/share/keyrings
   curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
   echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | tee /etc/apt/sources.list.d/cloudflared.list
   apt-get update && apt-get install cloudflared
   ```

2. U Cloudflare nadzornoj ploči: **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**, ime `trgovina`. Ploča pokaže naredbu `cloudflared service install <token>`; pokreni je na serveru. Tunel se tada sam diže pri svakom paljenju servera.

3. U istom tunelu, kartica **Public Hostname → Add a public hostname**:
   - Subdomain: `api`, Domain: `terpenstation.com`
   - Service: `HTTP`, URL: `127.0.0.1:8090`

4. Provjera s bilo kojeg računala: `curl https://api.terpenstation.com/zdravlje` vraća `ok`.
