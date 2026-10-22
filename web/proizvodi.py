"""Proizvodi iz CMS-a (sadrzaj/proizvodi/*.json) za jezik jedne države."""

import json
import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

log = logging.getLogger(__name__)

NA_KRAJ = 10**9


class NeispravanProizvod(Exception):
    pass


@dataclass(frozen=True)
class Pakiranje:
    id: str
    oznaka: str
    cijena_c: int
    tezina_g: float | None


@dataclass(frozen=True)
class Proizvod:
    slug: str
    naziv: str
    kratki_opis: str
    opis: str
    kategorija: str
    dostupno: bool
    redoslijed: int
    slike: tuple[str, ...]
    pakiranja: tuple[Pakiranje, ...]
    cbg: str
    thc: str
    sarza: str
    analiza: str


def ucitaj_sirove(mapa: Path) -> list[tuple[str, dict]]:
    sirovi = []
    for put in sorted(mapa.glob("*.json")):
        # Frend sprema izravno u main; pokvarena datoteka ne smije srušiti gradnju (W15).
        try:
            podaci = json.loads(put.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as greska:
            log.warning("proizvod %s preskočen: datoteka nije ispravan JSON (%s)", put.stem, greska)
            continue
        if isinstance(podaci, dict):
            sirovi.append((put.stem, podaci))
        else:
            log.warning("proizvod %s preskočen: očekivan JSON objekt", put.stem)
    return sirovi


def u_cente(vrijednost: object) -> int:
    if isinstance(vrijednost, bool) or vrijednost in (None, ""):
        raise NeispravanProizvod("pakiranje nema cijenu")
    try:
        broj = Decimal(str(vrijednost).replace(",", "."))
    except InvalidOperation as greska:
        raise NeispravanProizvod(f"cijena „{vrijednost}” nije broj") from greska
    if not broj.is_finite() or broj < 0:
        raise NeispravanProizvod(f"cijena {vrijednost} nije dopuštena")
    return int((broj * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _tezina(vrijednost: object) -> float | None:
    try:
        tezina = float(str(vrijednost).replace(",", "."))
    except ValueError:
        return None
    return tezina if tezina > 0 else None


def _pakiranja(slug: str, popis: object) -> tuple[Pakiranje, ...]:
    if not isinstance(popis, list) or not popis:
        raise NeispravanProizvod("nema nijedno pakiranje")
    pakiranja = []
    for redni, stavka in enumerate(popis, start=1):
        if not isinstance(stavka, dict) or not str(stavka.get("oznaka") or "").strip():
            raise NeispravanProizvod(f"pakiranje {redni} nema oznaku")
        pakiranja.append(
            Pakiranje(
                id=f"{slug}:{redni}",
                oznaka=str(stavka["oznaka"]).strip(),
                cijena_c=u_cente(stavka.get("cijena")),
                tezina_g=_tezina(stavka.get("tezina_g")),
            )
        )
    return tuple(pakiranja)


def _redoslijed(vrijednost: object) -> int:
    try:
        return int(float(str(vrijednost)))
    except ValueError:
        return NA_KRAJ


def _slike(vrijednost: object) -> tuple[str, ...]:
    if isinstance(vrijednost, str):
        vrijednost = [vrijednost]
    if not isinstance(vrijednost, list):
        return ()
    return tuple(slika for slika in vrijednost if isinstance(slika, str) and slika.strip())


def _tekst(polja: dict, kljuc: str) -> str:
    vrijednost = polja.get(kljuc)
    return str(vrijednost).strip() if vrijednost not in (None, False) else ""


def proizvod(slug: str, sirovi: dict, jezik: str, kontekst: dict) -> Proizvod | None:
    """Proizvod na jeziku države, None kad prijevoda nema.

    `kontekst` nosi zadani jezik CMS-a i dopuštene kategorije. Polja koja se ne prevode
    uzimaju se iz zadanog jezika, jer ih CMS tamo uvijek ima.
    """
    lokalno = sirovi.get(jezik)
    if not isinstance(lokalno, dict) or not _tekst(lokalno, "naziv"):
        if jezik == kontekst["zadani_jezik"]:
            raise NeispravanProizvod("nema naziv")
        return None
    zadano = sirovi.get(kontekst["zadani_jezik"])
    zajednicko = {**lokalno, **zadano} if isinstance(zadano, dict) else lokalno
    kategorija = _tekst(zajednicko, "kategorija")
    if kategorija not in kontekst["kategorije"]:
        raise NeispravanProizvod(f"nepoznata kategorija „{kategorija}”")
    return Proizvod(
        slug=slug,
        naziv=_tekst(lokalno, "naziv"),
        kratki_opis=_tekst(lokalno, "kratki_opis"),
        opis=_tekst(lokalno, "opis"),
        kategorija=kategorija,
        dostupno=zajednicko.get("dostupno", True) is not False,
        redoslijed=_redoslijed(zajednicko.get("redoslijed")),
        slike=_slike(zajednicko.get("slike")),
        pakiranja=_pakiranja(slug, zajednicko.get("pakiranja")),
        cbg=_tekst(zajednicko, "cbg"),
        thc=_tekst(zajednicko, "thc"),
        sarza=_tekst(zajednicko, "sarza"),
        analiza=_tekst(zajednicko, "analiza"),
    )


def za_jezik(sirovi: list[tuple[str, dict]], jezik: str, kontekst: dict) -> list[Proizvod]:
    """Dostupni proizvodi s prijevodom, po redoslijedu; neispravni se preskaču uz upozorenje."""
    proizvodi = []
    for slug, podaci in sirovi:
        try:
            nadjen = proizvod(slug, podaci, jezik, kontekst)
        except NeispravanProizvod as greska:
            log.warning("proizvod %s preskočen: %s", slug, greska)
            continue
        if nadjen is None:
            log.info("proizvod %s nema prijevod na %s, ne prikazuje se", slug, jezik)
        elif nadjen.dostupno:
            proizvodi.append(nadjen)
    return sorted(proizvodi, key=lambda p: (p.redoslijed, p.naziv.casefold()))
