"""Pravne stranice iz sadrzaj/stranice/<država>/<ključ>.md i Markdown u HTML."""

import re
from pathlib import Path

import markdown

from web.predlosci import put_stranice


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
    stranice = {}
    for put in sorted(mapa.glob("*.md")):
        tekst = put.read_text(encoding="utf-8")
        naslov = next(
            (redak[2:].strip() for redak in tekst.splitlines() if redak.startswith("# ")),
            put.stem,
        )
        stranice[put.stem] = {"naslov": naslov, "html": u_html(tekst), "opis": _opis(tekst)}
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
