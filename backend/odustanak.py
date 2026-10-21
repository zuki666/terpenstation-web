"""POST /odustanak: zahtjev za odustanak od ugovora, mail trgovini i potvrda kupcu."""

import logging
import re
import sqlite3

from flask import Request, Response

from backend import baza
from backend.narudzba import ip_klijenta, poruka
from backend.okolina import Okolina
from backend.provjera import EMAIL
from web.postavke import drzava_po_kodu

log = logging.getLogger(__name__)

BROJ = re.compile(r"^\d{4}-\d{4,6}$")
DULJINE = {"broj": 20, "email": 254, "ime": 100, "poruka": 2000}


def _greske(v: dict, jezik: dict) -> list[str]:
    t = jezik["greske"]
    greske = []
    if not BROJ.match(v["broj"]):
        greske.append(t["broj_narudzbe"])
    if not EMAIL.match(v["email"]):
        greske.append(t["email"])
    if not v["ime"]:
        greske.append(f"{jezik['odustanak']['ime']}: {t['obavezno']}")
    if any(len(v[polje]) > najvise for polje, najvise in DULJINE.items()):
        greske.append(t["predugo"])
    return greske


def obradi(okolina: Okolina, veza: sqlite3.Connection, zahtjev: Request) -> Response:
    v = {polje: (zahtjev.form.get(polje) or "").strip() for polje in (*DULJINE, "web", "drzava")}
    drzava = drzava_po_kodu(okolina.drzave, v["drzava"]) or okolina.drzave[0]
    t = okolina.iscrtavac.jezik(drzava)
    ip = ip_klijenta(zahtjev)
    if v["web"]:
        log.warning("odustanak odbijen: popunjeno polje-mamac (%s)", ip)
        return poruka(okolina, drzava, (t["greske"]["odbijeno"], []), 400)
    if (
        baza.zahtjeva_s_ip(veza, "odustanci", ip)
        >= okolina.postavke["zastita"]["narudzbi_po_ip_na_sat"]
    ):
        return poruka(okolina, drzava, (t["greske"]["previse"], [drzava["firma"]["email"]]), 429)
    greske = _greske(v, t)
    if greske:
        return poruka(okolina, drzava, (t["odustanak"]["naslov"], greske), 422)
    id_ = baza.upisi_odustanak(
        veza, {**v, "poruka": v["poruka"] or None, "drzava": drzava["kod"], "ip": ip}
    )
    zapis = baza.odustanak(veza, id_)
    log.info("odustanak %d za narudžbu %s", id_, zapis["broj"])
    okolina.slanje.posalji_odustanak(veza, zapis, drzava)
    tekst = t["odustanak"]["primljeno"].format(
        broj=zapis["broj"],
        vrijeme=okolina.iscrtavac.vrijeme(zapis["stvoreno"], drzava),
        email=zapis["email"],
    )
    return poruka(okolina, drzava, (t["odustanak"]["primljeno_naslov"], [tekst]), 200)
