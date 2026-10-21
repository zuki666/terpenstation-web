"""Flask aplikacija trgovine. Gunicorn: backend.aplikacija:stvori()"""

import hmac
import logging
import sqlite3
from contextlib import closing

import httpx
from flask import Flask, Response, g, request

from backend import baza, hub3, odustanak
from backend.boxnow import BoxNowGreska, ispravan_potpis, tijelo_zahtjeva
from backend.katalog import KatalogNedostupan
from backend.narudzba import Narudzba, poruka
from backend.okolina import Okolina, iz_postavki
from web.postavke import drzava_po_kodu

log = logging.getLogger(__name__)

NAJVECI_ZAHTJEV = 32 * 1024


def _veza(okolina: Okolina) -> sqlite3.Connection:
    if "veza" not in g:
        g.veza = baza.povezi(okolina.baza)
    return g.veza


def _narudzba_s_tokenom(okolina: Okolina, broj: str, token: str) -> dict | None:
    n = baza.narudzba(_veza(okolina), broj)
    return n if n and hmac.compare_digest(n["token"], token) else None


def _nije_nadjeno(okolina: Okolina) -> Response:
    t = okolina.iscrtavac.jezik(okolina.drzave[0])["greske"]
    return poruka(okolina, okolina.drzave[0], (t["nije_nadjeno_naslov"], [t["nije_nadjeno"]]), 404)


def _katalog_ili_nista(okolina: Okolina, drzava: dict) -> dict | None:
    """Stranica zahvale radi i kad sajt ne odgovara; tada samo bez izbornika."""
    try:
        return okolina.katalog.dohvati(drzava)
    except KatalogNedostupan:
        return None


def hvala(okolina: Okolina, broj: str, token: str) -> Response:
    n = _narudzba_s_tokenom(okolina, broj, token)
    drzava = drzava_po_kodu(okolina.drzave, n["drzava"]) if n else None
    if not drzava:
        return _nije_nadjeno(okolina)
    html = okolina.iscrtavac.stranica(
        "hvala.html",
        drzava,
        _katalog_ili_nista(okolina, drzava),
        {
            "naslov": f"{okolina.iscrtavac.jezik(drzava)['hvala']['broj']} {broj}",
            "n": n,
            "uplata": okolina.iscrtavac.uplata(n, drzava),
            "dostava": okolina.iscrtavac.opis_dostave(n, drzava),
        },
    )
    return Response(html, mimetype="text/html")


def barkod(okolina: Okolina, broj: str, token: str) -> Response:
    n = _narudzba_s_tokenom(okolina, broj, token)
    drzava = drzava_po_kodu(okolina.drzave, n["drzava"]) if n else None
    if not drzava or n["placanje"] != "uplata":
        return _nije_nadjeno(okolina)
    opis = okolina.iscrtavac.uplata(n, drzava)["opis"]
    odgovor = Response(hub3.png(hub3.niz(n, drzava["primatelj"], opis)), mimetype="image/png")
    odgovor.headers["Cache-Control"] = "private, max-age=86400"
    return odgovor


def _boxnow_greska(okolina: Okolina, drzava: dict, retci: list[str], status: int) -> Response:
    naslov = okolina.iscrtavac.jezik(drzava)["boxnow"]["greska_naslov"]
    return poruka(okolina, drzava, (naslov, [redak for redak in retci if redak]), status)


def _boxnow_potvrda(okolina: Okolina, n: dict, drzava: dict) -> Response:
    t = okolina.iscrtavac.jezik(drzava)["boxnow"]
    html = okolina.iscrtavac.stranica(
        "poruka.html",
        drzava,
        None,
        {
            "naslov": t["potvrda_naslov"].format(broj=n["broj"]),
            "retci": [t["potvrda_uvod"], okolina.iscrtavac.opis_dostave(n, drzava)],
            "obrazac": {"akcija": request.path, "gumb": t["napravi"]},
        },
    )
    return Response(html, mimetype="text/html")


def naljepnica(okolina: Okolina, broj: str, potpis: str) -> Response:
    """GET pokaže gumb, POST napravi pošiljku; postojeća pošiljka odmah vraća istu naljepnicu.

    Gumb postoji zato što programi za provjeru linkova u mailu znaju otvoriti GET, a pošiljka
    za neplaćenu narudžbu ne smije nastati sama.
    """
    n = baza.narudzba(_veza(okolina), broj)
    if not n or not ispravan_potpis(broj, potpis, okolina.tajna_linkova):
        return _nije_nadjeno(okolina)
    drzava = drzava_po_kodu(okolina.drzave, n["drzava"]) or okolina.drzave[0]
    t = okolina.iscrtavac.jezik(drzava)["boxnow"]
    if n["dostava"] != "boxnow":
        return _boxnow_greska(okolina, drzava, [t["nije_boxnow"]], 400)
    if okolina.boxnow is None:
        return _boxnow_greska(okolina, drzava, [t["nema_podataka"]], 503)
    if not n["boxnow_paket"] and request.method == "GET":
        return _boxnow_potvrda(okolina, n, drzava)
    return _napravi_naljepnicu(okolina, n, drzava)


def _napravi_naljepnicu(okolina: Okolina, n: dict, drzava: dict) -> Response:
    t = okolina.iscrtavac.jezik(drzava)["boxnow"]
    velicina = drzava["dostava"]["boxnow"]["velicina_pretinca"]
    try:
        paket = n["boxnow_paket"]
        if not paket:
            paket = okolina.boxnow.posiljka(
                tijelo_zahtjeva(n, okolina.postavke["boxnow"], velicina)
            )
            baza.upisi_boxnow(_veza(okolina), n["broj"], paket)
        pdf = okolina.boxnow.naljepnica(paket)
    except BoxNowGreska as greska:
        log.warning("BOX NOW za %s: %s", n["broj"], greska)
        retci = [
            t["greska_uvod"],
            f"{greska.kod}: {greska.poruka}",
            t["kodovi"].get(greska.kod, ""),
        ]
        return _boxnow_greska(okolina, drzava, retci, 502)
    except (httpx.HTTPError, ValueError, KeyError) as greska:
        log.warning("BOX NOW za %s se ne javlja ispravno: %s", n["broj"], greska)
        return _boxnow_greska(okolina, drzava, [t["nedostupan"]], 502)
    odgovor = Response(pdf, mimetype="application/pdf")
    odgovor.headers["Content-Disposition"] = f'inline; filename="boxnow-{n["broj"]}.pdf"'
    return odgovor


def _rute(app: Flask, okolina: Okolina) -> None:
    @app.get("/zdravlje")
    def zdravlje() -> Response:
        odgovor = Response("ok", mimetype="text/plain")
        odgovor.headers["Access-Control-Allow-Origin"] = "*"
        odgovor.headers["Cache-Control"] = "no-store"
        return odgovor

    @app.post("/narudzba")
    def narudzba() -> Response:
        return Narudzba(okolina, _veza(okolina), request).obradi()

    @app.get("/hvala/<broj>/<token>")
    def stranica_hvala(broj: str, token: str) -> Response:
        return hvala(okolina, broj, token)

    @app.get("/hub3/<broj>/<token>.png")
    def hub3_png(broj: str, token: str) -> Response:
        return barkod(okolina, broj, token)

    @app.route("/boxnow/<broj>/<potpis>", methods=["GET", "POST"])
    def boxnow(broj: str, potpis: str) -> Response:
        return naljepnica(okolina, broj, potpis)

    @app.post("/odustanak")
    def stranica_odustanka() -> Response:
        return odustanak.obradi(okolina, _veza(okolina), request)


def _greske(app: Flask, okolina: Okolina) -> None:
    t = okolina.iscrtavac.jezik(okolina.drzave[0])["greske"]

    @app.errorhandler(404)
    @app.errorhandler(405)
    def nije_nadjeno(_greska: Exception) -> Response:
        return _nije_nadjeno(okolina)

    @app.errorhandler(413)
    def prevelik(_greska: Exception) -> Response:
        return poruka(okolina, okolina.drzave[0], (t["odbijeno"], []), 413)


def stvori(okolina: Okolina | None = None) -> Flask:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    okolina = okolina or iz_postavki()
    with closing(baza.povezi(okolina.baza)) as veza:
        baza.provjeri_verziju(veza)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = NAJVECI_ZAHTJEV
    _rute(app, okolina)
    _greske(app, okolina)

    @app.teardown_appcontext
    def zatvori(_greska: BaseException | None) -> None:
        veza = g.pop("veza", None)
        if veza is not None:
            veza.close()

    @app.after_request
    def zaglavlja(odgovor: Response) -> Response:
        # Token zahvale je u adresi, pa ne smije otići dalje kroz Referer.
        odgovor.headers["Referrer-Policy"] = "no-referrer"
        odgovor.headers["X-Content-Type-Options"] = "nosniff"
        odgovor.headers["X-Robots-Tag"] = "noindex"
        return odgovor

    return app
