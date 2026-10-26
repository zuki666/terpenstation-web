"""Dnevnik uzgoja iz CMS-a (sadrzaj/dnevnik/*.json) za jezik jedne države."""

import logging
from dataclasses import dataclass
from datetime import date

from web.proizvodi import popis_slika, tekst_polja

log = logging.getLogger(__name__)

# Oblik uz broj gleda zadnju znamenku, osim za 11–14: 1 zapis, 3 fotke, 5 fotki, 21 zapis.
DVA_DO_CETIRI = (2, 3, 4)
JEDANAEST_DO_CETRNAEST = range(11, 15)


class NeispravanZapis(Exception):
    pass


@dataclass(frozen=True)
class Zapis:
    slug: str
    naslov: str
    tekst: str
    datum: date
    slike: tuple[str, ...]
    video: str
    trajanje_s: int | None
    video_na_instagramu: bool
    faza: str
    proizvod: str
    instagram: str


def _datum(vrijednost: object) -> date:
    # CMS sprema samo datum, a uvoz s Instagrama može dodati i vrijeme iza njega.
    try:
        return date.fromisoformat(str(vrijednost)[:10])
    except ValueError as greska:
        raise NeispravanZapis(f"datum „{vrijednost}” nije ispravan") from greska


def _trajanje(vrijednost: object) -> int | None:
    try:
        sekundi = int(float(str(vrijednost)))
    except ValueError:
        return None
    return sekundi if sekundi > 0 else None


def _instagram(link: str) -> str:
    # Link ide u href, pa iz obrasca prolazi samo https, a ne javascript: ili slično.
    return link if link.startswith("https://") else ""


def _faza(slug: str, faza: str, faze: list[str]) -> str:
    if faza and faza not in faze:
        log.warning("zapis %s: nepoznata faza „%s”, prikazuje se bez faze", slug, faza)
        return ""
    return faza


def zapis(slug: str, sirovi: dict, jezik: str, kontekst: dict) -> Zapis | None:
    """Zapis na jeziku države; None kad prijevoda nema ili zapis nije objavljen.

    `kontekst` nosi zadani jezik CMS-a i dopuštene faze. Polja koja se ne prevode uzimaju
    se iz zadanog jezika, kao kod proizvoda.
    """
    lokalno = sirovi.get(jezik)
    if not isinstance(lokalno, dict) or not tekst_polja(lokalno, "naslov"):
        if jezik == kontekst["zadani_jezik"]:
            raise NeispravanZapis("nema naslov")
        return None
    zadano = sirovi.get(kontekst["zadani_jezik"])
    zajednicko = {**lokalno, **zadano} if isinstance(zadano, dict) else lokalno
    if zajednicko.get("objavljeno", True) is False:
        return None
    return Zapis(
        slug=slug,
        naslov=tekst_polja(lokalno, "naslov"),
        tekst=tekst_polja(lokalno, "tekst"),
        datum=_datum(zajednicko.get("datum")),
        slike=popis_slika(zajednicko.get("slike")),
        video=tekst_polja(zajednicko, "video"),
        trajanje_s=_trajanje(zajednicko.get("trajanje_s")),
        video_na_instagramu=zajednicko.get("video_na_instagramu") is True,
        faza=_faza(slug, tekst_polja(zajednicko, "faza"), kontekst["faze"]),
        proizvod=tekst_polja(zajednicko, "proizvod"),
        instagram=_instagram(tekst_polja(zajednicko, "instagram")),
    )


def za_jezik(sirovi: list[tuple[str, dict]], jezik: str, kontekst: dict) -> list[Zapis]:
    """Objavljeni zapisi s prijevodom, od najnovijeg; neispravni se preskaču uz upozorenje (W15)."""
    zapisi = []
    for slug, podaci in sirovi:
        try:
            nadjen = zapis(slug, podaci, jezik, kontekst)
        except NeispravanZapis as greska:
            log.warning("zapis %s preskočen: %s", slug, greska)
            continue
        if nadjen is not None:
            zapisi.append(nadjen)
    return sorted(zapisi, key=lambda z: (z.datum, z.slug), reverse=True)


def mnozina(broj: int, oblici: list[str]) -> str:
    """`oblici` su za jedan, za dva do četiri i za ostalo, s {broj} u tekstu."""
    if broj % 100 in JEDANAEST_DO_CETRNAEST:
        oblik = oblici[2]
    elif broj % 10 == 1:
        oblik = oblici[0]
    elif broj % 10 in DVA_DO_CETIRI:
        oblik = oblici[1]
    else:
        oblik = oblici[2]
    return oblik.format(broj=broj)
