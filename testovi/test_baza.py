from backend import baza


def _narudzba(**izmjene) -> dict:
    podaci = {
        "drzava": "hr",
        "ime": "Ana",
        "email": "ana@example.com",
        "telefon": "+385911111111",
        "dostava": "gls",
        "placanje": "uplata",
        "stavke": "[]",
        "meduzbroj_c": 100,
        "dostava_c": 0,
        "naknada_c": 0,
        "ukupno_c": 100,
        "pdv_c": 20,
        "token": "t",
        "ip": "1.1.1.1",
    }
    podaci.update(izmjene)
    return podaci


def _veza(tmp_path):
    veza = baza.povezi(tmp_path / "t.db")
    baza.migriraj(veza)
    return veza


def test_migracije_su_idempotentne(tmp_path):
    veza = _veza(tmp_path)
    assert baza.migriraj(veza) == []
    baza.provjeri_verziju(veza)


def test_broj_narudzbe_raste_i_kreće_ispočetka_u_novoj_godini(tmp_path):
    veza = _veza(tmp_path)
    assert baza.upisi_narudzbu(veza, _narudzba(), 2026) == "2026-0001"
    assert baza.upisi_narudzbu(veza, _narudzba(), 2026) == "2026-0002"
    assert baza.upisi_narudzbu(veza, _narudzba(), 2027) == "2027-0001"
    assert baza.upisi_narudzbu(veza, _narudzba(), 2026) == "2026-0003"


def test_broj_iznad_9999_ostaje_jedinstven(tmp_path):
    veza = _veza(tmp_path)
    with veza:
        veza.execute(
            "INSERT INTO narudzbe (broj, drzava, ime, email, telefon, dostava, placanje, stavke, "
            "meduzbroj_c, dostava_c, naknada_c, ukupno_c, pdv_c, token) "
            "VALUES ('2026-9999', 'hr', 'a', 'b', 'c', 'gls', 'uplata', '[]', 0, 0, 0, 0, 0, 't')"
        )
    assert baza.upisi_narudzbu(veza, _narudzba(), 2026) == "2026-10000"


def test_neposlani_cekaju_dvije_minute(tmp_path):
    veza = _veza(tmp_path)
    broj = baza.upisi_narudzbu(veza, _narudzba(), 2026)
    assert baza.neposlani(veza, "narudzbe") == []
    with veza:
        veza.execute("UPDATE narudzbe SET stvoreno = datetime('now', '-5 minutes')")
    assert [red["broj"] for red in baza.neposlani(veza, "narudzbe")] == [broj]
    n = baza.narudzba(veza, broj)
    baza.oznaci_mail(veza, "narudzbe", n["id"], "mail_trgovini")
    baza.oznaci_mail(veza, "narudzbe", n["id"], "mail_kupcu")
    assert baza.neposlani(veza, "narudzbe") == []


def test_zahtjevi_s_ip_u_zadnjem_satu(tmp_path):
    veza = _veza(tmp_path)
    baza.upisi_narudzbu(veza, _narudzba(ip="2.2.2.2"), 2026)
    baza.upisi_narudzbu(veza, _narudzba(ip="2.2.2.2"), 2026)
    assert baza.zahtjeva_s_ip(veza, "narudzbe", "2.2.2.2") == 2
    with veza:
        veza.execute("UPDATE narudzbe SET stvoreno = datetime('now', '-2 hours')")
    assert baza.zahtjeva_s_ip(veza, "narudzbe", "2.2.2.2") == 0
