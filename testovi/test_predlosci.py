"""Predlošci backenda iscrtavaju se za svaku državu; stranice sajta pokriva test gradnje."""

import json

import pytest
from conftest import katalog_probni

from backend.iscrtavanje import Iscrtavac
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_postavke
from web.predlosci import iznos, podaci_blagajne

POSTAVKE = ucitaj_postavke()
DRZAVE = ucitaj_drzave()
ISCRTAVAC = Iscrtavac(KORIJEN, POSTAVKE, DRZAVE)


def _narudzba(drzava: dict, placanje: str) -> dict:
    return {
        "id": 1,
        "broj": "2026-0012",
        "drzava": drzava["kod"],
        "stvoreno": "2026-10-21 10:00:00",
        "ime": "Ana Anić",
        "email": "ana@example.com",
        "telefon": "+385911111111",
        "dostava": "gls",
        "paketomat_id": None,
        "paketomat_adresa": None,
        "ulica": "Ilica 1",
        "postanski_broj": "10000",
        "mjesto": "Zagreb",
        "placanje": placanje,
        "stavke": [
            {
                "id": "g:1",
                "naziv": "Gelonade",
                "oznaka": "1 g",
                "cijena_c": 990,
                "kolicina": 2,
                "tezina_g": 1,
            }
        ],
        "meduzbroj_c": 1980,
        "dostava_c": 490,
        "naknada_c": 0,
        "ukupno_c": 2470,
        "pdv_c": 494,
        "tvrtka": "Firma d.o.o.",
        "oib": "29737469043",
        "napomena": "Zvoniti dvaput",
        "token": "t" * 22,
        "mail_trgovini": None,
        "mail_kupcu": None,
    }


@pytest.mark.parametrize("drzava", DRZAVE, ids=lambda d: d["kod"])
@pytest.mark.parametrize("placanje", ["uplata", "pouzece"])
def test_stranice_i_mailovi_backenda(drzava, placanje):
    n = _narudzba(drzava, placanje)
    uplata = ISCRTAVAC.uplata(n, drzava)
    zajednicko = {"n": n, "uplata": uplata, "dostava": ISCRTAVAC.opis_dostave(n, drzava)}
    hvala = ISCRTAVAC.stranica(
        "hvala.html", drzava, katalog_probni(), {"naslov": "x", **zajednicko}
    )
    assert "2026-0012" in hvala and "/css/stil.abc.css" in hvala
    assert ("hub3" in hvala) == (placanje == "uplata")
    tekst = ISCRTAVAC.tekst("mail/kupcu.txt", drzava, zajednicko)
    html = ISCRTAVAC.tekst(
        "mail/kupcu.html", drzava, {**zajednicko, "predmet": "p", "cid_barkoda": "c"}
    )
    assert "Gelonade" in tekst and "Gelonade" in html
    trgovini = ISCRTAVAC.tekst(
        "mail/trgovini.txt", drzava, {"n": n, "boxnow_link": "", "vrijeme": "x"}
    )
    assert "Firma d.o.o." in trgovini and "Zvoniti dvaput" in trgovini
    assert uplata["rok"] == "26. 10. 2026."


@pytest.mark.parametrize("drzava", DRZAVE, ids=lambda d: d["kod"])
def test_blagajna_i_poruka_iz_backenda(drzava):
    blagajna = ISCRTAVAC.stranica(
        "blagajna.html",
        drzava,
        None,
        {
            "naslov": "Blagajna",
            "v": {"ime": "<b>Ana</b>"},
            "greske": {"ime": "Greška"},
            "obavijest": None,
            "boxnow": POSTAVKE["boxnow"],
            "blagajna_js": podaci_blagajne(drzava, POSTAVKE, []),
        },
    )
    assert "&lt;b&gt;Ana&lt;/b&gt;" in blagajna
    assert f'action="{POSTAVKE["sajt"]["api"]}/narudzba"' in blagajna
    podaci = blagajna.split('id="ts-blagajna" type="application/json">')[1].split("</script>")[0]
    assert json.loads(podaci)["stavke"] == []
    poruka = ISCRTAVAC.stranica(
        "poruka.html",
        drzava,
        None,
        {
            "naslov": "N",
            "retci": ["a"],
            "obrazac": {"akcija": "/x", "gumb": "G"},
        },
    )
    assert 'action="/x"' in poruka


def test_oblik_iznosa():
    oblik = {"decimalni_znak": ",", "razdjelnik_tisuca": ".", "uzorak_iznosa": "{iznos} {simbol}"}
    assert iznos(990, oblik, "EUR") == "9,90 €"
    assert iznos(123456789, oblik, "EUR") == "1.234.567,89 €"
    assert iznos(5, oblik, "CHF") == "0,05 CHF"
