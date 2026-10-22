import json
from urllib.parse import parse_qs, urlparse

from conftest import obrazac

from backend import baza


def _naruci(klijent, ip: str = "1.2.3.4", **izmjene):
    return klijent.post("/narudzba", data=obrazac(**izmjene), headers={"CF-Connecting-IP": ip})


def test_zdravlje_dopusta_provjeru_sa_sajta(klijent):
    odgovor = klijent.get("/zdravlje")
    assert odgovor.status_code == 200
    assert odgovor.headers["Access-Control-Allow-Origin"] == "*"


def test_narudzba_od_obrasca_do_zahvale(klijent, okolina):
    odgovor = _naruci(klijent)
    assert odgovor.status_code == 303
    adresa = urlparse(odgovor.headers["Location"])
    assert f"{adresa.scheme}://{adresa.netloc}{adresa.path}" == "https://terpenstation.com/hvala/"
    upit = parse_qs(adresa.query)
    broj, token = upit["n"][0], upit["t"][0]
    assert broj.endswith("-0001")

    with baza.povezi(okolina.baza) as veza:
        n = baza.narudzba(veza, broj)
    assert n["ukupno_c"] == 5890 and n["telefon"] == "+385912345678"
    assert n["stavke"][0]["naziv"] == "Gelonade"
    assert n["mail_trgovini"] and n["mail_kupcu"]

    trgovini, kupcu = okolina.slanje.posta.poslano
    assert trgovini["To"] == okolina.postavke["mail"]["trgovina"]
    assert trgovini["Reply-To"] == "ivana@example.com"
    assert broj in trgovini["Subject"] and "58,90" in trgovini["Subject"]
    assert "Za MyGLS" in trgovini.get_content()
    assert kupcu["To"] == "ivana@example.com"
    assert any(dio.get_content_type() == "image/png" for dio in kupcu.walk())
    assert "OVO NIJE FISKALIZIRANI RAČUN" in kupcu.get_body(("plain",)).get_content()

    hvala = klijent.get(f"/hvala/{broj}/{token}")
    assert hvala.status_code == 200
    assert broj in hvala.text and "HR12 1001 0051 8630 0016 0" in hvala.text
    assert hvala.headers["Referrer-Policy"] == "no-referrer"
    barkod = klijent.get(f"/hub3/{broj}/{token}.png")
    assert barkod.status_code == 200 and barkod.data.startswith(b"\x89PNG")
    assert klijent.get(f"/hvala/{broj}/pogresan-token-1234").status_code == 404


def test_pouzece_nema_barkod(klijent, okolina):
    odgovor = _naruci(
        klijent,
        dostava="boxnow",
        paketomat_id="12345",
        placanje="pouzece",
        ukupno_c=str(5400 + 350 + 150),
    )
    assert odgovor.status_code == 303
    kupcu = okolina.slanje.posta.poslano[1]
    assert not any(dio.get_content_type() == "image/png" for dio in kupcu.walk())
    trgovini = okolina.slanje.posta.poslano[0].get_content()
    assert "https://api.terpenstation.com/boxnow/" in trgovini


def test_greska_vraca_blagajnu_s_upisanim(klijent, okolina):
    odgovor = _naruci(klijent, email="nije-email", ime="Marko Marić")
    assert odgovor.status_code == 422
    assert 'value="Marko Marić"' in odgovor.text
    assert 'aria-invalid="true"' in odgovor.text
    podaci = odgovor.text.split('id="ts-blagajna" type="application/json">')[1].split("</script>")[
        0
    ]
    assert json.loads(podaci)["stavke"][0]["naziv"] == "Gelonade"
    assert okolina.slanje.posta.poslano == []


def test_promijenjena_cijena_trazi_potvrdu(klijent, okolina):
    odgovor = _naruci(klijent, ukupno_c="1000")
    assert odgovor.status_code == 409
    assert (
        okolina.iscrtavac.jezik(okolina.drzave[0])["blagajna"]["cijene_promijenjene"]
        in odgovor.text
    )
    with baza.povezi(okolina.baza) as veza:
        assert veza.execute("SELECT COUNT(*) FROM narudzbe").fetchone()[0] == 0


def test_polje_mamac(klijent, okolina):
    assert _naruci(klijent, web="http://spam").status_code == 400
    assert okolina.slanje.posta.poslano == []


def test_prebrzo_poslan_obrazac(klijent):
    odgovor = _naruci(klijent, sekundi="1")
    assert odgovor.status_code == 422
    assert _naruci(klijent, sekundi="").status_code == 422


def test_najvise_pet_narudzbi_po_ip_na_sat(klijent):
    for _ in range(5):
        assert _naruci(klijent, ip="9.9.9.9").status_code == 303
    assert _naruci(klijent, ip="9.9.9.9").status_code == 429
    assert _naruci(klijent, ip="8.8.8.8").status_code == 303


def test_prevelik_zahtjev(klijent):
    odgovor = klijent.post("/narudzba", data=obrazac(napomena="x" * 40_000))
    assert odgovor.status_code == 413


def test_pad_maila_ne_gubi_narudzbu(klijent, okolina):
    okolina.slanje.posta.pokvarena = True
    odgovor = _naruci(klijent)
    assert odgovor.status_code == 303
    with baza.povezi(okolina.baza) as veza:
        n = veza.execute("SELECT mail_trgovini, mail_kupcu FROM narudzbe").fetchone()
    assert n["mail_trgovini"] is None and n["mail_kupcu"] is None


def test_odustanak(klijent, okolina):
    _naruci(klijent)
    okolina.slanje.posta.poslano.clear()
    podaci = {
        "broj": "2026-0001",
        "email": "IVANA@example.com",
        "ime": "Ivana",
        "drzava": "hr",
        "poruka": "Predomislila sam se.",
        "web": "",
    }
    odgovor = klijent.post("/odustanak", data=podaci)
    assert odgovor.status_code == 200
    assert "2026-0001" in odgovor.text
    trgovini, kupcu = okolina.slanje.posta.poslano
    assert "nije pronađena" not in trgovini.get_content()
    assert kupcu["To"] == "IVANA@example.com"
    assert "2026-0001" in kupcu.get_content()


def test_odustanak_s_greskom(klijent, okolina):
    odgovor = klijent.post(
        "/odustanak", data={"broj": "12", "email": "x", "ime": "", "drzava": "hr"}
    )
    assert odgovor.status_code == 422
    assert okolina.slanje.posta.poslano == []


def test_nepoznata_adresa(klijent):
    odgovor = klijent.get("/nema")
    assert odgovor.status_code == 404
    assert odgovor.headers["X-Robots-Tag"] == "noindex"
