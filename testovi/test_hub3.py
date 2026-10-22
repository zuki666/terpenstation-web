import io

import pytest

from backend import hub3

PRIMATELJ = {
    "naziv": "Proper Stuff",
    "ulica": "Martićeva ulica 67",
    "mjesto": "10000 Zagreb",
    "iban": "HR12 1001 0051 8630 0016 0",
    "model": "HR00",
    "sifra_namjene": "OTHR",
}
NARUDZBA = {
    "broj": "2026-0012",
    "ime": "Željko Seneković",
    "dostava": "gls",
    "ulica": "Ivanečka ulica 125",
    "postanski_broj": "42000",
    "mjesto": "Varaždin",
    "ukupno_c": 3480,
}


def test_redoslijed_polja_i_lf_iza_svakog():
    niz = hub3.niz(NARUDZBA, PRIMATELJ, "Narudžba 2026-0012")
    assert niz.endswith("\n")
    assert niz.split("\n")[:-1] == [
        "HRVHUB30",
        "EUR",
        "000000000003480",
        "Željko Seneković",
        "Ivanečka ulica 125",
        "42000 Varaždin",
        "Proper Stuff",
        "Martićeva ulica 67",
        "10000 Zagreb",
        "HR1210010051863000160",
        "HR00",
        "2026-0012",
        "OTHR",
        "Narudžba 2026-0012",
    ]


def test_boxnow_nema_adresu_platitelja():
    polja = hub3.niz({**NARUDZBA, "dostava": "boxnow"}, PRIMATELJ, "x").split("\n")
    assert polja[4] == "" and polja[5] == ""


def test_iznos_s_vodecim_nulama():
    polja = hub3.niz({**NARUDZBA, "ukupno_c": 123455}, PRIMATELJ, "x").split("\n")
    assert polja[2] == "000000000123455"
    assert len(polja[2]) == 15


def test_skracivanje_broji_hrvatska_slova_kao_jedan_znak():
    assert hub3.ocisti("Č" * 40, 30) == "Č" * 30
    ime = hub3.niz({**NARUDZBA, "ime": "Đurđa Žganjer-Čičak Šimunović Ćosić"}, PRIMATELJ, "x")
    assert len(ime.split("\n")[3]) <= 30


def test_nedopusteni_znakovi_i_strana_slova():
    assert hub3.ocisti("Müller & Søn <b>!", 30) == "Muller Sn b"
    assert hub3.ocisti("Ana\nPerić; #12", 30) == "Ana Perić 12"
    assert hub3.ocisti("a,b.c:d-e+f?g'h/i(j)", 30) == "a,b.c:d-e+f?g'h/i(j)"


def test_barkod_se_cita_kao_isti_niz():
    zxingcpp = pytest.importorskip("zxingcpp")
    from PIL import Image

    niz = hub3.niz(NARUDZBA, PRIMATELJ, "Narudžba 2026-0012")
    procitano = zxingcpp.read_barcodes(Image.open(io.BytesIO(hub3.png(niz))))
    assert procitano[0].text == niz


def test_binarni_nacin():
    from pdf417gen.compaction import BYTE_LATCH, BYTE_LATCH_ALT, TEXT_LATCH

    rijeci = hub3.kodne_rijeci(hub3.niz(NARUDZBA, PRIMATELJ, "Narudžba 2026-0012").encode())
    opisnik = rijeci[0]
    assert rijeci[1] in (BYTE_LATCH, BYTE_LATCH_ALT)
    podaci = rijeci[2:opisnik]
    while podaci and podaci[-1] == TEXT_LATCH:
        podaci.pop()  # dopuna do punog retka, nije način kodiranja
    assert all(rijec < TEXT_LATCH for rijec in podaci)
