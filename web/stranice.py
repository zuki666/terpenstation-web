"""Pravne stranice iz CMS-a (sadrzaj/stranice/<država>/<ključ>.json) i Markdown u HTML."""

import re
from pathlib import Path

import markdown

from web.predlosci import put_stranice
from web.proizvodi import tekst_polja, ucitaj_sirove


def u_html(tekst: str) -> str:
    return markdown.markdown(tekst, extensions=["extra", "sane_lists"], output_format="html")


def _opis(tekst: str) -> str:
    """Prvi obični odlomak bez Markdown oznaka, za meta opis."""
    for odlomak in re.split(r"\n\s*\n", tekst):
        cist = odlomak.strip()
        if cist and not cist.startswith(("#", ">", "-", "*", "|")):
            bez_oznaka = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cist)
            bez_oznaka = re.sub(r"[*_`]", "", bez_oznaka).replace("\n", " ")
            return bez_oznaka[:160]
    return ""


def ucitaj(mapa: Path) -> dict[str, dict]:
    """Naslov, tekst u HTML-u i opis za Google; naslov ide u <h1> preko predloška."""
    stranice = {}
    for kljuc, podaci in ucitaj_sirove(mapa, "tekst stranice"):
        tekst = tekst_polja(podaci, "tekst")
        stranice[kljuc] = {
            "naslov": tekst_polja(podaci, "naslov") or kljuc,
            "html": u_html(tekst),
            "opis": _opis(tekst),
        }
    return stranice


def pravne_veze(drzava: dict, jezik: dict, kljucevi: list[str], stranice: dict) -> list[dict]:
    return [
        {
            "kljuc": kljuc,
            "naziv": stranice[kljuc]["naslov"],
            "url": put_stranice(drzava, jezik, kljuc),
        }
        for kljuc in kljucevi
        if kljuc in stranice
    ]
