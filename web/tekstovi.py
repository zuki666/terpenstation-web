"""Tekstovi iz CMS-a (sadrzaj/tekstovi/<jezik>/*.json) preko jezici/<jezik>.toml.

Svaka datoteka iz CMS-a je dio stabla jezika: odjeljak, ključ i tekst, kao u TOML-u. Gradnja i
backend čitaju jezik kroz ovo, pa obje strane pokazuju isti tekst.
"""

import logging
import string
from pathlib import Path

from web.proizvodi import ucitaj_sirove

log = logging.getLogger(__name__)

_OBLIK = string.Formatter()


def _polja(tekst: str) -> set[str] | None:
    """Imena {polja} koja kod puni u tekst; None kad vitičaste zagrade nisu u paru."""
    try:
        return {ime for _, ime, _, _ in _OBLIK.parse(tekst) if ime is not None}
    except ValueError:
        return None


def _tekst(novi: object, stari: str, put: str) -> str:
    # Prazno je u CMS-u „nije upisano” (npr. rok slanja), pa vrijedi tekst iz jezici/.
    if novi is None or (isinstance(novi, str) and not novi.strip()):
        return stari
    if not isinstance(novi, str):
        log.warning("tekst %s nije tekst; ostaje onaj iz jezici/", put)
        return stari
    # Kod u tekst upisuje {iznos}, {sorta}…; tekst bez njih ili s nepoznatim srušio bi gradnju
    # ili maknuo broj sa stranice.
    if _polja(novi) != _polja(stari):
        log.warning("tekst %s ne smije mijenjati {…} iz jezici/; ostaje onaj iz jezici/", put)
        return stari
    return novi.strip()


def _popis(novi: object, stari: list[dict], put: str) -> list[dict]:
    """Popis redaka (vozni red na naslovnoj): cijeli iz CMS-a, ili cijeli iz jezici/."""
    kljucevi = list(stari[0])
    ispravan = (
        isinstance(novi, list)
        and bool(novi)
        and all(
            isinstance(redak, dict)
            and all(isinstance(redak.get(k), str) and redak[k].strip() for k in kljucevi)
            for redak in novi
        )
    )
    if not ispravan:
        log.warning("popis %s nije ispravan; ostaje onaj iz jezici/", put)
        return stari
    return [{k: redak[k].strip() for k in kljucevi} for redak in novi]


def _popis_redaka(vrijednost: object) -> bool:
    return (
        isinstance(vrijednost, list)
        and bool(vrijednost)
        and all(isinstance(redak, dict) for redak in vrijednost)
    )


def prekrij(osnova: dict, novo: dict, put: str = "") -> dict:
    """Kopija `osnova` s ispravnim tekstovima iz `novo`.

    Ključ koji ne postoji u jezici/ ne dodaje se: predlošci ga ne traže, a obično je tipfeler.
    """
    spojeno = dict(osnova)
    for kljuc, vrijednost in novo.items():
        mjesto = f"{put}{kljuc}"
        stari = osnova.get(kljuc)
        if isinstance(stari, dict) and isinstance(vrijednost, dict):
            spojeno[kljuc] = prekrij(stari, vrijednost, f"{mjesto}.")
        elif isinstance(stari, str):
            spojeno[kljuc] = _tekst(vrijednost, stari, mjesto)
        elif _popis_redaka(stari):
            spojeno[kljuc] = _popis(vrijednost, stari, mjesto)
        else:
            log.warning("tekst %s ne postoji u jeziku kao takav; preskače se", mjesto)
    return spojeno


def ucitaj(jezik: dict, mapa: Path) -> dict:
    """Jezik s tekstovima iz svih datoteka u `mapa`; bez mape ostaje kakav jest."""
    for _, dio in ucitaj_sirove(mapa, "tekst"):
        jezik = prekrij(jezik, dio)
    return jezik
