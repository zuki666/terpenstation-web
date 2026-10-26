import copy
import json

import pytest
from conftest import drzave_s_oba_placanja, katalog_probni, obrazac

from backend.provjera import ispravan_oib, medjunarodni, provjeri, vrijednosti
from web.postavke import ucitaj_jezik

HR = drzave_s_oba_placanja()[0]
JEZIK = ucitaj_jezik("hr")
G = JEZIK["greske"]


def provjera(drzava: dict = HR, **izmjene: str):
    return provjeri(vrijednosti(obrazac(**izmjene)), drzava, JEZIK, katalog_probni())


def test_ispravna_narudzba_nema_gresaka():
    p = provjera()
    assert p.greske == {}
    assert p.podaci["telefon"] == "+385912345678"
    assert p.stavke == [
        {
            "id": "gelonade:2",
            "naziv": "Gelonade",
            "oznaka": "3 g",
            "cijena_c": 2700,
            "kolicina": 2,
            "tezina_g": 3,
        }
    ]


@pytest.mark.parametrize(
    ("ulaz", "izlaz"),
    [
        ("091 234 5678", "+385912345678"),
        ("091/234-5678", "+385912345678"),
        ("0038641234567", "+38641234567"),
        ("+386 41 234 567", "+38641234567"),
        ("385912345678", "+385912345678"),
        ("912345678", "+385912345678"),
    ],
)
def test_telefon_u_medjunarodni_oblik(ulaz, izlaz):
    assert medjunarodni(ulaz, "385") == izlaz


@pytest.mark.parametrize("polje", ["ime", "email", "telefon"])
def test_obavezna_polja(polje):
    assert provjera(**{polje: ""}).greske[polje] == G["obavezno"]


def test_neispravan_email_i_telefon():
    greske = provjera(email="ivana@", telefon="12").greske
    assert greske["email"] == G["email"]
    assert greske["telefon"] == G["telefon"]


def test_oib():
    assert ispravan_oib("29737469043")
    assert not ispravan_oib("29737469044")
    assert not ispravan_oib("2973746904")
    assert provjera(oib="12345678901").greske["oib"] == G["oib"]
    assert "oib" not in provjera(oib="").greske
    assert "oib" not in provjera(oib="29737469043").greske


def test_boxnow_trazi_paketomat():
    assert provjera(dostava="boxnow").greske["paketomat_id"] == G["paketomat"]
    assert provjera(dostava="boxnow", paketomat_id="12345").greske == {}


def test_gls_trazi_adresu():
    greske = provjera(ulica="", postanski_broj="", mjesto="").greske
    assert set(greske) == {"ulica", "postanski_broj", "mjesto"}
    assert provjera(postanski_broj="#!").greske["postanski_broj"] == G["postanski_broj"]


def test_dostava_i_placanje_moraju_biti_dopusteni():
    assert provjera(dostava="dhl").greske["dostava"] == G["dostava"]
    assert provjera(placanje="kartica").greske["placanje"] == G["placanje"]


def test_pouzece_samo_uz_dostavu_koja_ga_dopusta():
    drzava = copy.deepcopy(HR)
    drzava["dostava"]["boxnow"]["pouzece"] = False
    greske = provjera(drzava, dostava="boxnow", paketomat_id="1", placanje="pouzece").greske
    assert greske["placanje"] == G["pouzece"]
    assert provjera(drzava, placanje="pouzece").greske == {}


@pytest.mark.parametrize("kvacica", ["punoljetan", "uvjeti"])
def test_obje_kvacice(kvacica):
    assert provjera(**{kvacica: ""}).greske[kvacica] == G[kvacica]


def test_predug_tekst():
    assert provjera(napomena="x" * 1001).greske["napomena"] == G["predugo"]


@pytest.mark.parametrize(
    "stavke",
    [
        "nije json",
        "[]",
        json.dumps({"id": "gelonade:1"}),
        json.dumps([{"id": "gelonade:1", "kolicina": 0}]),
        json.dumps([{"id": "gelonade:1", "kolicina": 21}]),
        json.dumps([{"id": "gelonade:1", "kolicina": True}]),
        json.dumps([{"id": "gelonade:1", "kolicina": "2"}]),
        json.dumps([{"id": "gelonade:1", "kolicina": 1}, {"id": "gelonade:1", "kolicina": 1}]),
        json.dumps([{"id": f"x:{i}", "kolicina": 1} for i in range(31)]),
    ],
)
def test_neispravna_kosarica(stavke):
    p = provjera(stavke=stavke)
    assert p.greske["opcenito"] == G["kosarica"]
    assert p.stavke == []


def test_proizvod_koji_vise_nije_u_ponudi():
    p = provjera(stavke=json.dumps([{"id": "gelonade:9", "kolicina": 1}]))
    assert p.greske["opcenito"] == G["nedostupno"].format(naziv="Gelonade")
    p = provjera(stavke=json.dumps([{"id": "nestalo:1", "kolicina": 1}]))
    assert p.greske["opcenito"] == G["nedostupno"].format(naziv="nestalo")


def test_cijena_dolazi_iz_kataloga_a_ne_iz_obrasca():
    stavke = json.dumps([{"id": "gelonade:1", "kolicina": 3, "cijena_c": 1}])
    assert provjera(stavke=stavke).stavke[0]["cijena_c"] == 990
