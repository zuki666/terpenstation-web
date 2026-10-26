"""Stranice dnevnika uzgoja: popis po stranicama, popis jedne sorte i stranica zapisa.

Prikaz zapisa (datumi, slike, video, sorta) složi se jednom po državi, a isti dict koriste
popis, zapis, stranica proizvoda i naslovna.
"""

import logging
import re
from dataclasses import dataclass
from html import unescape

from web import dnevnik, strukturirani
from web.dnevnik import Zapis, mnozina
from web.predlosci import put_stranice
from web.slike import Slike
from web.stranica import Stranica
from web.stranice import u_html

log = logging.getLogger(__name__)

# Znakova teksta na popisu i u opisu za Google; dulje se reže na granici riječi.
KRATKO = 140


@dataclass
class Okvir:
    """Ono što stranice dnevnika jedne države trebaju od gradnje."""

    drzava: dict
    jezik: dict
    postavke: dict
    slike: Slike
    adresa: str


def _kratko(tekst_html: str) -> str:
    prvi = tekst_html.split("</p>", 1)[0]
    tekst = " ".join(unescape(re.sub(r"<[^>]+>", " ", prvi)).split())
    if len(tekst) <= KRATKO:
        return tekst
    return tekst[:KRATKO].rsplit(" ", 1)[0] + "…"


def _video(z: Zapis, slike: Slike) -> str:
    if z.video and not (slike.static / z.video.lstrip("/")).is_file():
        log.warning("zapis %s: video %s ne postoji, prikazuje se bez videa", z.slug, z.video)
        return ""
    return z.video


def _datumi(z: Zapis, d: dict) -> dict:
    dan, mjesec, godina = z.datum.day, z.datum.month, z.datum.year
    return {
        "datum_iso": z.datum.isoformat(),
        "datum_kratko": d["datum_kratko"].format(dan=dan, mjesec=mjesec),
        "datum_dugo": d["datum"].format(dan=dan, mjesec=mjesec, godina=godina),
        "mjesec": d["mjesec_godina"].format(mjesec=d["mjeseci"][mjesec - 1], godina=godina),
    }


def _prikaz(z: Zapis, proizvodi: dict, okvir: Okvir) -> dict:
    jezik = okvir.jezik
    slike = [s for s in (okvir.slike.obradi(put) for put in z.slike) if s]
    prva = next((put for put in z.slike if okvir.slike.obradi(put)), "")
    tekst_html = u_html(z.tekst) if z.tekst else ""
    return {
        "slug": z.slug,
        "naslov": z.naslov,
        "tekst_html": tekst_html,
        "kratko": _kratko(tekst_html),
        **_datumi(z, jezik["dnevnik"]),
        "faza": z.faza,
        "naziv_faze": jezik["faze"][z.faza] if z.faza else "",
        "slike": slike,
        "slika": slike[0] if slike else None,
        "pregled": okvir.slike.pregled(prva) if prva else "",
        "video": _video(z, okvir.slike),
        "trajanje": f"{z.trajanje_s // 60}:{z.trajanje_s % 60:02d}" if z.trajanje_s else "",
        "video_na_instagramu": z.video_na_instagramu,
        "instagram": z.instagram,
        "broj_fotki": mnozina(len(slike), jezik["dnevnik"]["fotke"]) if len(slike) > 1 else "",
        "url": put_stranice(okvir.drzava, jezik, "dnevnik", z.slug),
        "proizvod": proizvodi.get(z.proizvod),
    }


def ucitaj(sirovi: list[tuple[str, dict]], proizvodi: list[dict], okvir: Okvir) -> list[dict]:
    """Objavljeni zapisi države, od najnovijeg, spremni za predloške.

    Zapis je vezan uz sortu samo dok je proizvod u ponudi; inače ostaje bez veze.
    """
    kontekst = {
        "zadani_jezik": okvir.postavke["trgovina"]["zadani_jezik"],
        "faze": okvir.postavke["dnevnik"]["faze"],
    }
    po_slugu = {p["slug"]: p for p in proizvodi}
    zapisi = dnevnik.za_jezik(sirovi, okvir.drzava["jezik"], kontekst)
    return [_prikaz(z, po_slugu, okvir) for z in zapisi]


def put_dnevnika(zapisi: list[dict], okvir: Okvir) -> str:
    """Dnevnik bez nijednog zapisa se ne gradi i nema ga u izborniku, kao prazna kategorija."""
    return put_stranice(okvir.drzava, okvir.jezik, "dnevnik") if zapisi else ""


def po_sorti(zapisi: list[dict]) -> dict[str, list[dict]]:
    """Zapisi po slugu proizvoda, od najnovijeg; zapis bez sorte nije ni u jednoj."""
    sorte: dict[str, list[dict]] = {}
    for z in zapisi:
        if z["proizvod"]:
            sorte.setdefault(z["proizvod"]["slug"], []).append(z)
    return sorte


def _stavke(zapisi: list[dict]) -> list[dict]:
    """Zapisi popisa s nazivom mjeseca iznad prvog zapisa svakog mjeseca."""
    stavke, prethodni = [], ""
    for z in zapisi:
        stavke.append({"z": z, "mjesec": z["mjesec"] if z["mjesec"] != prethodni else ""})
        prethodni = z["mjesec"]
    return stavke


def _gumbi(sorte: dict[str, list[dict]], okvir: Okvir) -> list[dict]:
    """Tipke iznad popisa: svi zapisi, pa jedna po sorti; bez sorti ih nema."""
    if not sorte:
        return []
    put = put_stranice(okvir.drzava, okvir.jezik, "dnevnik")
    svi = {"kljuc": "", "naziv": okvir.jezik["dnevnik"]["svi"], "url": put}
    return [svi] + [
        {"kljuc": slug, "naziv": zapisi[0]["proizvod"]["naziv"], "url": f"{put}{slug}/"}
        for slug, zapisi in sorte.items()
    ]


def _instagram(postavke: dict) -> dict | None:
    ime = postavke["dnevnik"]["instagram"]
    return {"url": f"https://www.instagram.com/{ime}/", "ime": f"@{ime}"} if ime else None


def _zaglavlje_popisa(zapisi: list[dict], sorta: dict | None, okvir: Okvir) -> dict:
    """Naslov, opis i mrvice popisa svih zapisa ili jedne sorte."""
    d = okvir.jezik["dnevnik"]
    koraci = [(d["naslov"], put_stranice(okvir.drzava, okvir.jezik, "dnevnik"))]
    if sorta:
        koraci.append((sorta["naziv"], f"{koraci[0][1]}{sorta['slug']}/"))
    return {
        "naslov": d["sorta_naslov"].format(sorta=sorta["naziv"]) if sorta else d["naslov_stranice"],
        "opis": d["sorta_uvod"].format(sorta=sorta["naziv"]) if sorta else d["opis"],
        "mrvice": strukturirani.mrvice(okvir.drzava, okvir.jezik, okvir.adresa, koraci),
        "put": koraci[-1][1],
    }


def _popis(
    zapisi: list[dict], sorta: dict | None, gumbi: list[dict], okvir: Okvir
) -> list[Stranica]:
    """Popis po `zapisa_po_stranici`: prva stranica na osnovnom putu, ostale na /2/, /3/…"""
    d, naziv = okvir.jezik["dnevnik"], okvir.jezik["opcenito"]["naziv_sajta"]
    zaglavlje = _zaglavlje_popisa(zapisi, sorta, okvir)
    po_stranici = okvir.postavke["dnevnik"]["zapisa_po_stranici"]
    dijelovi = [zapisi[i : i + po_stranici] for i in range(0, len(zapisi), po_stranici)]
    putevi = [zaglavlje["put"]] + [f"{zaglavlje['put']}{n}/" for n in range(2, len(dijelovi) + 1)]
    podaci = {
        "sorta": sorta,
        "gumbi": gumbi,
        "ukupno": mnozina(len(zapisi), d["zapisi"]),
        "zadnji": zapisi[0]["datum_kratko"],
        "instagram": _instagram(okvir.postavke),
    }
    popis = []
    for redni, dio in enumerate(dijelovi):
        stranica = f" · {d['stranica'].format(broj=redni + 1)}" if redni else ""
        popis.append(
            Stranica(
                ("dnevnik", f"{sorta['slug'] if sorta else ''}:{redni + 1}"),
                putevi[redni],
                "dnevnik.html",
                f"{zaglavlje['naslov']}{stranica} · {naziv}",
                zaglavlje["opis"],
                {
                    **podaci,
                    "stavke": _stavke(dio),
                    "noviji": putevi[redni - 1] if redni else "",
                    "stariji": putevi[redni + 1] if redni + 1 < len(putevi) else "",
                },
                og_slika=next((z["pregled"] for z in dio if z["pregled"]), ""),
                aktivna="dnevnik",
                json_ld=[zaglavlje["mrvice"]],
            )
        )
    return popis


def _stranica_zapisa(zapisi: list[dict], redni: int, ukupno: str, okvir: Okvir) -> Stranica:
    z, jezik = zapisi[redni], okvir.jezik
    d, naziv = jezik["dnevnik"], jezik["opcenito"]["naziv_sajta"]
    koraci = [(d["naslov"], put_stranice(okvir.drzava, jezik, "dnevnik")), (z["naslov"], z["url"])]
    return Stranica(
        ("zapis", z["slug"]),
        z["url"],
        "zapis.html",
        f"{z['naslov']} · {d['naslov']} · {naziv}",
        z["kratko"] or d["opis"],
        {
            "z": z,
            "noviji": zapisi[redni - 1] if redni else None,
            "stariji": zapisi[redni + 1] if redni + 1 < len(zapisi) else None,
            "ukupno": ukupno,
        },
        og_slika=z["pregled"],
        aktivna="dnevnik",
        json_ld=[
            strukturirani.zapis(z, okvir.drzava, okvir.adresa, naziv),
            strukturirani.mrvice(okvir.drzava, jezik, okvir.adresa, koraci),
        ],
    )


def stranice(zapisi: list[dict], okvir: Okvir) -> list[Stranica]:
    """Popis svih zapisa, popis svake sorte i stranica svakog zapisa; bez zapisa ništa."""
    if not zapisi:
        return []
    sorte = po_sorti(zapisi)
    gumbi = _gumbi(sorte, okvir)
    popis = _popis(zapisi, None, gumbi, okvir)
    for zapisi_sorte in sorte.values():
        popis += _popis(zapisi_sorte, zapisi_sorte[0]["proizvod"], gumbi, okvir)
    ukupno = mnozina(len(zapisi), okvir.jezik["dnevnik"]["zapisi"])
    return popis + [_stranica_zapisa(zapisi, redni, ukupno, okvir) for redni in range(len(zapisi))]
