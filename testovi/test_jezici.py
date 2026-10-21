import tomllib

import pytest

from web.postavke import KORIJEN, ucitaj_drzave

JEZICI = sorted((KORIJEN / "jezici").glob("*.toml"))


def _kljucevi(podaci: dict, prefiks: str = "") -> set[str]:
    kljucevi = set()
    for kljuc, vrijednost in podaci.items():
        put = f"{prefiks}{kljuc}"
        kljucevi |= _kljucevi(vrijednost, f"{put}.") if isinstance(vrijednost, dict) else {put}
    return kljucevi


def _ucitaj(put) -> dict:
    with put.open("rb") as datoteka:
        return tomllib.load(datoteka)


HR = _kljucevi(_ucitaj(KORIJEN / "jezici" / "hr.toml"))


@pytest.mark.parametrize("put", JEZICI, ids=lambda p: p.stem)
def test_svaki_kljuc_postoji_u_svakom_jeziku(put):
    assert HR - _kljucevi(_ucitaj(put)) == set()


def test_svaka_drzava_ima_svoj_jezik_i_tekstove_za_dostave_i_placanja():
    for drzava in ucitaj_drzave():
        jezik = _ucitaj(KORIJEN / "jezici" / f"{drzava['jezik']}.toml")
        for dostava in drzava["dostave"]:
            assert dostava in jezik["dostave"]
            assert dostava in drzava["dostava"]
        for placanje in drzava["placanja"]:
            assert placanje in jezik["placanja"]


def test_kategorije_iz_postavki_imaju_tekstove_i_url():
    kategorije = _ucitaj(KORIJEN / "postavke.toml")["trgovina"]["kategorije"]
    for put in JEZICI:
        jezik = _ucitaj(put)
        for kategorija in kategorije:
            assert kategorija in jezik["kategorije"] and kategorija in jezik["url"]
