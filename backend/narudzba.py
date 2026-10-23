"""POST /narudzba: zaštita, provjera, upis, mailovi i preusmjeravanje na zahvalu."""

import json
import logging
import secrets
import sqlite3
from datetime import datetime
from urllib.parse import urlencode

from flask import Request, Response, redirect

from backend import baza
from backend.iscrtavanje import ZONA
from backend.iznosi import Iznosi, izracunaj
from backend.katalog import KatalogNedostupan
from backend.okolina import Okolina
from backend.provjera import Provjera, provjeri, vrijednosti
from web.postavke import drzava_po_kodu
from web.predlosci import podaci_blagajne, put_stranice

log = logging.getLogger(__name__)


def ip_klijenta(zahtjev: Request) -> str:
    # Cloudflare Tunnel stavlja pravu adresu kupca u CF-Connecting-IP; remote_addr je tunel.
    return zahtjev.headers.get("CF-Connecting-IP") or zahtjev.remote_addr or ""


def poruka(okolina: Okolina, drzava: dict, sadrzaj: tuple[str, list[str]], status: int) -> Response:
    naslov, retci = sadrzaj
    html = okolina.iscrtavac.stranica(
        "poruka.html",
        drzava,
        None,
        {
            "naslov": naslov,
            "retci": retci,
            "obrazac": None,
        },
    )
    return Response(html, status=status, mimetype="text/html")


class Narudzba:
    def __init__(self, okolina: Okolina, veza: sqlite3.Connection, zahtjev: Request) -> None:
        self.okolina = okolina
        self.veza = veza
        self.zahtjev = zahtjev
        self.v = vrijednosti(zahtjev.form)
        self.drzava = drzava_po_kodu(okolina.drzave, self.v["drzava"]) or okolina.drzave[0]
        self.t = okolina.iscrtavac.jezik(self.drzava)

    def _blagajna(
        self, katalog: dict, provjera: Provjera | None, obavijest: str | None, status: int
    ) -> Response:
        """Ista blagajna s porukama uz polja, bez gubitka upisanog."""
        stavke = provjera.stavke if provjera else []
        javne = [
            {k: s[k] for k in ("id", "naziv", "oznaka", "cijena_c", "kolicina")} for s in stavke
        ]
        vrijednosti_obrasca = {**self.v, "verzija": katalog.get("verzija", "")}
        html = self.okolina.iscrtavac.stranica(
            "blagajna.html",
            self.drzava,
            katalog,
            {
                "naslov": self.t["blagajna"]["naslov"],
                "v": vrijednosti_obrasca,
                "greske": provjera.greske if provjera else {},
                "obavijest": obavijest,
                "boxnow": self.okolina.postavke["boxnow"],
                "blagajna_js": podaci_blagajne(self.drzava, self.okolina.postavke, javne),
            },
        )
        return Response(html, status=status, mimetype="text/html")

    def _odbij(self) -> Response | None:
        t = self.t["greske"]
        zastita = self.okolina.postavke["zastita"]
        if self.v["web"]:
            log.warning("narudžba odbijena: popunjeno polje-mamac (%s)", ip_klijenta(self.zahtjev))
            return poruka(self.okolina, self.drzava, (t["odbijeno"], []), 400)
        broj = baza.zahtjeva_s_ip(self.veza, "narudzbe", ip_klijenta(self.zahtjev))
        if broj >= zastita["narudzbi_po_ip_na_sat"]:
            log.warning(
                "narudžba odbijena: %d narudžbi s %s u sat", broj, ip_klijenta(self.zahtjev)
            )
            return poruka(
                self.okolina, self.drzava, (t["previse"], [self.drzava["firma"]["email"]]), 429
            )
        return None

    def _prebrzo(self) -> bool:
        try:
            sekundi = float(self.v["sekundi"])
        except ValueError:
            return True
        return sekundi < self.okolina.postavke["zastita"]["najmanje_sekundi_na_obrascu"]

    def obradi(self) -> Response:
        odbijeno = self._odbij()
        if odbijeno:
            return odbijeno
        try:
            katalog = self.okolina.katalog.dohvati(self.drzava)
        except KatalogNedostupan as greska:
            log.error("narudžba nije moguća: %s", greska)
            return poruka(self.okolina, self.drzava, (self.t["greske"]["katalog"], []), 503)
        if self._prebrzo():
            return self._blagajna(katalog, None, self.t["blagajna"]["prebrzo"], 422)
        provjera = provjeri(self.v, self.drzava, self.t, katalog)
        if provjera.greske:
            return self._blagajna(katalog, provjera, None, 422)
        iznosi = izracunaj(provjera.stavke, self.drzava, self.v["dostava"], self.v["placanje"])
        if self.v["ukupno_c"] != str(iznosi.ukupno_c):
            log.info(
                "cijene promijenjene: obrazac %s, katalog %s", self.v["ukupno_c"], iznosi.ukupno_c
            )
            return self._blagajna(katalog, provjera, self.t["blagajna"]["cijene_promijenjene"], 409)
        return self._upisi(provjera, iznosi)

    def _upisi(self, provjera: Provjera, iznosi: Iznosi) -> Response:
        p = provjera.podaci
        boxnow = p["dostava"] == "boxnow"
        podaci = {
            **{k: p[k] for k in ("ime", "email", "telefon", "dostava", "placanje")},
            **{k: p[k] or None for k in ("tvrtka", "oib", "napomena")},
            # Neobavezno polje: nepoznata vrijednost se ne odbija, nego se ne sprema.
            "izvor": p["izvor"]
            if p["izvor"] in self.okolina.postavke["trgovina"]["izvori"]
            else None,
            "paketomat_id": p["paketomat_id"] if boxnow else None,
            "paketomat_adresa": (p["paketomat_adresa"] or None) if boxnow else None,
            **{k: None if boxnow else p[k] for k in ("ulica", "postanski_broj", "mjesto")},
            "drzava": self.drzava["kod"],
            "stavke": json.dumps(provjera.stavke, ensure_ascii=False),
            **{
                k: getattr(iznosi, k)
                for k in ("meduzbroj_c", "dostava_c", "naknada_c", "ukupno_c", "pdv_c")
            },
            "token": secrets.token_urlsafe(16),
            "ip": ip_klijenta(self.zahtjev),
        }
        broj = baza.upisi_narudzbu(self.veza, podaci, datetime.now(ZONA).year)
        log.info("narudžba %s: %s, %s, %d c", broj, p["dostava"], p["placanje"], iznosi.ukupno_c)
        n = baza.narudzba(self.veza, broj)
        self.okolina.slanje.posalji_narudzbu(self.veza, n, self.drzava)
        # Zahvala ide preko sajta, da se košarica isprazni na adresi na kojoj živi.
        hvala = put_stranice(self.drzava, self.t, "hvala")
        upit = urlencode({"n": broj, "t": n["token"]})
        return redirect(f"{self.okolina.postavke['sajt']['adresa']}{hvala}?{upit}", code=303)
