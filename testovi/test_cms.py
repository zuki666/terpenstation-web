"""Zbirke Tekstovi i Stranice (static/admin/tekstovi.toml) odgovaraju jeziku i datotekama.

Polje s tipfelerom CMS bi pokazao i spremio, a gradnja bi tekst preskočila, pa izmjena ne bi
stigla na sajt.
"""

import json
import re
import tomllib

from web.postavke import KORIJEN, ucitaj_postavke, ucitaj_toml

CONFIG = tomllib.loads((KORIJEN / "static" / "admin" / "tekstovi.toml").read_text("utf-8"))
ZBIRKE = {zbirka["name"]: zbirka for zbirka in CONFIG["collections"]}
HR = ucitaj_toml(KORIJEN / "jezici" / "hr.toml")
TEKST = {"string", "text"}
# Odjeljci koje iscrtava samo gradnja, ili server samo u zaglavlju i podnožju; blagajna, zahvala,
# mailovi i greške idu i kroz server, pa ostaju u jezici/ (W42).
ODJELJCI_CMS_A = {
    "naslovna",
    "kategorije",
    "kategorije_naslov",
    "kategorije_opis",
    "dnevnik",
    "faze",
    "proizvod",
    "kosarica",
    "izbornik",
    "podnozje",
}


def _polja(polja: list[dict], jezik: object, put: str = ""):
    """(put, polje, vrijednost iz jezika) za svako polje, i ugniježđeno."""
    for polje in polja:
        mjesto = f"{put}{polje['name']}"
        vrijednost = jezik.get(polje["name"]) if isinstance(jezik, dict) else None
        yield mjesto, polje, vrijednost
        if polje["widget"] == "object":
            yield from _polja(polje["fields"], vrijednost, f"{mjesto}.")
        elif polje["widget"] == "list" and isinstance(vrijednost, list) and vrijednost:
            yield from _polja(polje["fields"], vrijednost[0], f"{mjesto}.0.")


def _kljucevi(podaci: object, put: str = "") -> set[str]:
    """Putovi ključeva u datoteci; popis se gleda po prvom retku, kao u `_polja`."""
    kljucevi = set()
    if isinstance(podaci, dict):
        for kljuc, vrijednost in podaci.items():
            kljucevi |= {f"{put}{kljuc}"} | _kljucevi(vrijednost, f"{put}{kljuc}.")
    elif isinstance(podaci, list) and podaci:
        kljucevi |= _kljucevi(podaci[0], f"{put}0.")
    return kljucevi


def test_svako_polje_postoji_u_jeziku_istog_oblika():
    for datoteka in ZBIRKE["tekstovi"]["files"]:
        for polje in datoteka["fields"]:
            assert polje["widget"] == "object" and polje["name"] in ODJELJCI_CMS_A
        for put, polje, vrijednost in _polja(datoteka["fields"], HR):
            assert polje.get("i18n") is True, put
            if polje["widget"] == "object":
                assert isinstance(vrijednost, dict), put
            elif polje["widget"] == "list":
                assert isinstance(vrijednost, list) and isinstance(vrijednost[0], dict), put
            else:
                assert polje["widget"] in TEKST and isinstance(vrijednost, str), put


def test_tekst_s_poljem_u_zagradama_ima_pattern():
    for datoteka in ZBIRKE["tekstovi"]["files"]:
        for put, polje, vrijednost in _polja(datoteka["fields"], HR):
            if polje["widget"] not in TEKST:
                continue
            zagrade = re.findall(r"\{\w+\}", vrijednost)
            if not zagrade:
                assert "pattern" not in polje, put
                continue
            uzorak = re.compile(polje["pattern"][0])
            assert uzorak.search(vrijednost), put
            assert not uzorak.search(vrijednost.replace(zagrade[0], "")), put


def test_datoteke_tekstova_imaju_sva_polja_iz_cms_a():
    """CMS pokazuje ono što je u datoteci; polje koje u njoj fali stoji prazno i ne da spremiti."""
    for datoteka in ZBIRKE["tekstovi"]["files"]:
        assert datoteka["i18n"] is True
        assert datoteka["file"] == f"sadrzaj/tekstovi/{{{{locale}}}}/{datoteka['name']}.json"
        put = KORIJEN / datoteka["file"].replace("{{locale}}", "hr")
        podaci = json.loads(put.read_text(encoding="utf-8"))
        assert _kljucevi(podaci) == {mjesto for mjesto, _, _ in _polja(datoteka["fields"], podaci)}


def test_stranice_iz_cms_a_su_sve_stranice_trgovine():
    kljucevi = ucitaj_postavke()["trgovina"]["pravne_stranice"] + ["odustanak"]
    datoteke = {datoteka["name"]: datoteka for datoteka in ZBIRKE["stranice"]["files"]}
    assert list(datoteke) == kljucevi
    assert "i18n" not in ZBIRKE["stranice"]
    for kljuc, datoteka in datoteke.items():
        assert datoteka["file"] == f"sadrzaj/stranice/hr/{kljuc}.json"
        podaci = json.loads((KORIJEN / datoteka["file"]).read_text(encoding="utf-8"))
        assert set(podaci) == {polje["name"] for polje in datoteka["fields"]}
    assert [polje["name"] for polje in datoteke["odustanak"]["fields"]] == ["tekst"]
