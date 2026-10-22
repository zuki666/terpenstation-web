"""Čitanje postavki: zajedničke, države i jezici. Iste koriste gradnja i backend."""

import os
import tomllib
from pathlib import Path

KORIJEN = Path(__file__).resolve().parent.parent


class PostavkeGreska(Exception):
    pass


def ucitaj_toml(putanja: Path) -> dict:
    if not putanja.exists():
        raise PostavkeGreska(f"nema datoteke {putanja}")
    # Datoteke se uređuju ručno, pa greška mora reći red, a ne pokazati traceback.
    try:
        with putanja.open("rb") as datoteka:
            return tomllib.load(datoteka)
    except tomllib.TOMLDecodeError as greska:
        raise PostavkeGreska(f"{putanja}: {greska}") from greska


def ucitaj_postavke(korijen: Path = KORIJEN) -> dict:
    postavke = ucitaj_toml(korijen / "postavke.toml")
    # Lokalni pregled i testovi pokazuju gradnju i backend jedno na drugo bez izmjene datoteke.
    postavke["sajt"]["adresa"] = os.environ.get("SAJT_ADRESA") or postavke["sajt"]["adresa"]
    postavke["sajt"]["api"] = os.environ.get("SAJT_API") or postavke["sajt"]["api"]
    return postavke


def ucitaj_drzave(korijen: Path = KORIJEN) -> list[dict]:
    drzave = [ucitaj_toml(put) for put in sorted((korijen / "drzave").glob("*.toml"))]
    if not drzave:
        raise PostavkeGreska("u drzave/ nema nijedne države")
    # Država na korijenu ide prva: njezin je izbornik država i zadani 404.
    return sorted(drzave, key=lambda drzava: (drzava["put"] != "/", drzava["kod"]))


def ucitaj_jezik(kod: str, korijen: Path = KORIJEN) -> dict:
    return ucitaj_toml(korijen / "jezici" / f"{kod}.toml")


def drzava_po_kodu(drzave: list[dict], kod: str) -> dict | None:
    return next((drzava for drzava in drzave if drzava["kod"] == kod), None)
