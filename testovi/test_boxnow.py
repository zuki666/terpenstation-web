import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from conftest import TAJNA, obrazac

from backend import baza
from backend.boxnow import BoxNowGreska, Klijent, potpis, tijelo_zahtjeva

BOXNOW = {
    "skladiste": "2",
    "posiljatelj_ime": "Terpen Station",
    "posiljatelj_email": "narudzbe@terpenstation.com",
    "posiljatelj_telefon": "+385923728991",
}
NARUDZBA = {
    "broj": "2026-0012",
    "ukupno_c": 3480,
    "placanje": "pouzece",
    "telefon": "+385912345678",
    "email": "ana@example.com",
    "ime": "Ana Anić",
    "paketomat_id": "4321",
    "stavke": [{"tezina_g": 3, "kolicina": 2}, {"tezina_g": 1, "kolicina": 1}],
}


def test_tijelo_za_pouzece():
    tijelo = tijelo_zahtjeva(NARUDZBA, BOXNOW, 1)
    assert tijelo["orderNumber"] == "2026-0012"
    assert tijelo["paymentMode"] == "cod"
    assert tijelo["invoiceValue"] == "34.80"
    assert tijelo["amountToBeCollected"] == "34.80"
    assert tijelo["allowReturn"] is True
    assert tijelo["origin"]["locationId"] == "2"
    assert tijelo["destination"] == {
        "contactNumber": "+385912345678",
        "contactEmail": "ana@example.com",
        "contactName": "Ana Anić",
        "locationId": "4321",
    }
    assert tijelo["items"][0]["weight"] == 0.007
    assert tijelo["items"][0]["compartmentSize"] == 1


def test_tijelo_za_uplatu_i_nepoznatu_tezinu():
    n = {
        **NARUDZBA,
        "placanje": "uplata",
        "ukupno_c": 905,
        "stavke": [{"tezina_g": None, "kolicina": 1}],
    }
    tijelo = tijelo_zahtjeva(n, BOXNOW, 2)
    assert tijelo["paymentMode"] == "prepaid"
    assert tijelo["amountToBeCollected"] == "0.00"
    assert tijelo["invoiceValue"] == "9.05"
    assert tijelo["items"][0]["weight"] == 0


def test_token_se_cuva_do_isteka():
    zahtjevi = []

    def odgovor(zahtjev):
        zahtjevi.append(zahtjev.url.path)
        if zahtjev.url.path.endswith("auth-sessions"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(200, content=b"%PDF")

    klijent = Klijent("https://x", ("a", "b"), httpx.Client(transport=httpx.MockTransport(odgovor)))
    klijent.naljepnica("1")
    klijent.naljepnica("1")
    assert zahtjevi.count("/api/v1/auth-sessions") == 1


def test_greska_boxnowa_nosi_kod():
    def odgovor(zahtjev):
        if zahtjev.url.path.endswith("auth-sessions"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(400, json={"code": "P411", "message": "not eligible for COD"})

    klijent = Klijent("https://x", ("a", "b"), httpx.Client(transport=httpx.MockTransport(odgovor)))
    with pytest.raises(BoxNowGreska) as greska:
        klijent.posiljka(tijelo_zahtjeva(NARUDZBA, BOXNOW, 1))
    assert greska.value.kod == "P411"


def _boxnow_narudzba(klijent) -> str:
    odgovor = klijent.post(
        "/narudzba",
        data=obrazac(
            dostava="boxnow",
            paketomat_id="4321",
            placanje="pouzece",
            ukupno_c=str(5400 + 350 + 150),
        ),
        headers={"CF-Connecting-IP": "5.5.5.5"},
    )
    return parse_qs(urlparse(odgovor.headers["Location"]).query)["n"][0]


def test_link_iz_maila_trazi_klik_i_vraca_istu_naljepnicu(klijent, okolina):
    broj = _boxnow_narudzba(klijent)
    link = f"/boxnow/{broj}/{potpis(broj, TAJNA)}"
    zahtjevi = okolina.boxnow.zahtjevi

    prvi = klijent.get(link)
    assert prvi.status_code == 200 and "<form" in prvi.text
    assert zahtjevi == []

    pdf = klijent.post(link)
    assert pdf.status_code == 200 and pdf.mimetype == "application/pdf"
    poslano = [z for z in zahtjevi if z.url.path == "/api/v1/delivery-requests"]
    assert len(poslano) == 1
    assert json.loads(poslano[0].content)["paymentMode"] == "cod"
    with baza.povezi(okolina.baza) as veza:
        assert baza.narudzba(veza, broj)["boxnow_paket"] == "1234567890"

    ponovno = klijent.get(link)
    assert ponovno.data == b"%PDF-naljepnica"
    assert len([z for z in zahtjevi if z.url.path == "/api/v1/delivery-requests"]) == 1


def test_pogresan_potpis(klijent):
    broj = _boxnow_narudzba(klijent)
    assert klijent.get(f"/boxnow/{broj}/{'0' * 32}").status_code == 404


def test_bez_pristupnih_podataka(klijent, okolina):
    broj = _boxnow_narudzba(klijent)
    okolina.boxnow = None
    assert klijent.get(f"/boxnow/{broj}/{potpis(broj, TAJNA)}").status_code == 503
