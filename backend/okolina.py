"""Sve što aplikacija treba, složeno na jednom mjestu; testovi podmeću svoje dijelove."""

from dataclasses import dataclass
from pathlib import Path

from backend import postavke as tajne_i_putanje
from backend.boxnow import Klijent, potpis
from backend.iscrtavanje import Iscrtavac
from backend.katalog import Katalog
from backend.mailovi import Slanje, posta_iz_postavki
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_postavke


@dataclass
class Okolina:
    postavke: dict
    drzave: list[dict]
    baza: Path
    katalog: Katalog
    iscrtavac: Iscrtavac
    slanje: Slanje
    tajna_linkova: str
    boxnow: Klijent | None


def link_boxnow(postavke: dict, tajna: str):
    api = postavke["sajt"]["api"]
    return lambda broj: f"{api}/boxnow/{broj}/{potpis(broj, tajna)}"


def iz_postavki(korijen: Path = KORIJEN) -> Okolina:
    """Prava okolina sa servera; tajna koja fali javlja se odmah pri pokretanju."""
    postavke = ucitaj_postavke(korijen)
    drzave = ucitaj_drzave(korijen)
    tajne = tajne_i_putanje.tajne(tajne_i_putanje.TAJNE)
    # BOX NOW pristupni podaci stižu tek u W4; do tada link u mailu javlja da ih nema.
    boxnow = tajne_i_putanje.citaj(tajne_i_putanje.TAJNE_BOXNOW)
    klijent = (
        Klijent(
            boxnow["BOXNOW_API_URL"], (boxnow["BOXNOW_CLIENT_ID"], boxnow["BOXNOW_CLIENT_SECRET"])
        )
        if all(boxnow.values())
        else None
    )
    iscrtavac = Iscrtavac(korijen, postavke, drzave)
    slanje = Slanje(
        postavke,
        iscrtavac,
        posta_iz_postavki(postavke, tajne["SMTP_LOZINKA"]),
        link_boxnow(postavke, tajne["TAJNA_LINKOVA"]),
    )
    return Okolina(
        postavke=postavke,
        drzave=drzave,
        baza=tajne_i_putanje.putanja_baze(),
        katalog=Katalog(postavke["sajt"]["adresa"], tajne_i_putanje.mapa_cachea()),
        iscrtavac=iscrtavac,
        slanje=slanje,
        tajna_linkova=tajne["TAJNA_LINKOVA"],
        boxnow=klijent,
    )
