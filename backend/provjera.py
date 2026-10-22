"""Provjera obrasca blagajne; cijene stavki dolaze iz kataloga, nikad iz preglednika (W14)."""

import json
import re
from dataclasses import dataclass, field

MAKS_KOLICINA = 20
MAKS_STAVKI = 30

POLJA = (
    "ime",
    "email",
    "telefon",
    "dostava",
    "paketomat_id",
    "paketomat_adresa",
    "ulica",
    "postanski_broj",
    "mjesto",
    "placanje",
    "tvrtka",
    "oib",
    "napomena",
    "punoljetan",
    "uvjeti",
    "stavke",
    "verzija",
    "ukupno_c",
    "sekundi",
    "web",
    "drzava",
)
DULJINE = {
    "ime": 100,
    "email": 254,
    "telefon": 30,
    "paketomat_id": 20,
    "paketomat_adresa": 200,
    "ulica": 100,
    "postanski_broj": 10,
    "mjesto": 60,
    "tvrtka": 100,
    "napomena": 1000,
}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TELEFON = re.compile(r"^\+[1-9]\d{7,14}$")
POSTANSKI = re.compile(r"^[0-9A-Za-z][0-9A-Za-z -]{2,9}$")


@dataclass
class Provjera:
    podaci: dict
    stavke: list[dict] = field(default_factory=list)
    greske: dict[str, str] = field(default_factory=dict)


def vrijednosti(obrazac: object) -> dict[str, str]:
    return {polje: (obrazac.get(polje) or "").strip() for polje in POLJA}


def medjunarodni(telefon: str, pozivni: str) -> str:
    """09x… → +3859x…: BOX NOW traži broj u međunarodnom obliku (P405)."""
    broj = re.sub(r"[\s\-/().]", "", telefon)
    if broj.startswith("+"):
        return broj
    if broj.startswith("00"):
        return "+" + broj[2:]
    if broj.startswith("0"):
        return f"+{pozivni}{broj[1:]}"
    if broj.isdigit():
        return "+" + (broj if broj.startswith(pozivni) else pozivni + broj)
    return broj


def ispravan_oib(oib: str) -> bool:
    """Kontrolna znamenka po ISO 7064, MOD 11,10."""
    if not re.fullmatch(r"\d{11}", oib):
        return False
    ostatak = 10
    for znamenka in oib[:10]:
        ostatak = (ostatak + int(znamenka)) % 10 or 10
        ostatak = (ostatak * 2) % 11
    return (11 - ostatak) % 10 == int(oib[10])


def _duljine(v: dict, t: dict) -> dict[str, str]:
    return {polje: t["predugo"] for polje, najvise in DULJINE.items() if len(v[polje]) > najvise}


def _kontakt(v: dict, t: dict) -> dict[str, str]:
    greske = {}
    if not v["ime"]:
        greske["ime"] = t["obavezno"]
    if not EMAIL.match(v["email"]):
        greske["email"] = t["email"] if v["email"] else t["obavezno"]
    if not TELEFON.match(v["telefon"]):
        greske["telefon"] = t["telefon"] if v["telefon"] else t["obavezno"]
    if v["oib"] and not ispravan_oib(v["oib"]):
        greske["oib"] = t["oib"]
    return greske


def _dostava(v: dict, drzava: dict, t: dict) -> dict[str, str]:
    if v["dostava"] not in drzava["dostave"]:
        return {"dostava": t["dostava"]}
    if v["dostava"] == "boxnow":
        return {} if v["paketomat_id"] else {"paketomat_id": t["paketomat"]}
    greske = {
        polje: t["obavezno"] for polje in ("ulica", "postanski_broj", "mjesto") if not v[polje]
    }
    if v["postanski_broj"] and not POSTANSKI.match(v["postanski_broj"]):
        greske["postanski_broj"] = t["postanski_broj"]
    return greske


def _placanje(v: dict, drzava: dict, t: dict) -> dict[str, str]:
    if v["placanje"] not in drzava["placanja"]:
        return {"placanje": t["placanje"]}
    dostava = drzava["dostava"].get(v["dostava"], {})
    if (
        v["placanje"] == "pouzece"
        and v["dostava"] in drzava["dostave"]
        and not dostava.get("pouzece")
    ):
        return {"placanje": t["pouzece"]}
    return {}


def _kvacice(v: dict, t: dict) -> dict[str, str]:
    return {polje: t[polje] for polje in ("punoljetan", "uvjeti") if not v[polje]}


def _ispravna_stavka(stavka: object) -> bool:
    if not isinstance(stavka, dict) or not isinstance(stavka.get("id"), str):
        return False
    kolicina = stavka.get("kolicina")
    return type(kolicina) is int and 1 <= kolicina <= MAKS_KOLICINA


def stavke_iz_kataloga(tekst: str, katalog: dict, t: dict) -> tuple[list[dict], str]:
    """Stavke s cijenama iz kataloga i poruka greške ("" kad je sve u redu)."""
    try:
        popis = json.loads(tekst)
    except ValueError:
        return [], t["kosarica"]
    if not isinstance(popis, list) or not 1 <= len(popis) <= MAKS_STAVKI:
        return [], t["kosarica"]
    if not all(_ispravna_stavka(s) for s in popis) or len({s["id"] for s in popis}) != len(popis):
        return [], t["kosarica"]
    pakiranja = {pak["id"]: (p, pak) for p in katalog["proizvodi"] for pak in p["pakiranja"]}
    proizvodi = {p["id"]: p for p in katalog["proizvodi"]}
    stavke = []
    for stavka in popis:
        if stavka["id"] not in pakiranja:
            slug = stavka["id"].split(":", 1)[0]
            naziv = proizvodi[slug]["naziv"] if slug in proizvodi else slug
            return [], t["nedostupno"].format(naziv=naziv)
        proizvod, pakiranje = pakiranja[stavka["id"]]
        stavke.append(
            {
                "id": stavka["id"],
                "naziv": proizvod["naziv"],
                "oznaka": pakiranje["oznaka"],
                "cijena_c": pakiranje["cijena_c"],
                "kolicina": stavka["kolicina"],
                "tezina_g": pakiranje.get("tezina_g"),
            }
        )
    return stavke, ""


def provjeri(v: dict, drzava: dict, jezik: dict, katalog: dict) -> Provjera:
    t = jezik["greske"]
    podaci = {
        **v,
        "telefon": medjunarodni(v["telefon"], drzava["pozivni_broj"]) if v["telefon"] else "",
    }
    greske = {
        **_kontakt(podaci, t),
        **_dostava(podaci, drzava, t),
        **_placanje(podaci, drzava, t),
        **_kvacice(podaci, t),
        **_duljine(podaci, t),
    }
    stavke, greska_stavki = stavke_iz_kataloga(v["stavke"], katalog, t)
    if greska_stavki:
        greske["opcenito"] = greska_stavki
    return Provjera(podaci, stavke, greske)
