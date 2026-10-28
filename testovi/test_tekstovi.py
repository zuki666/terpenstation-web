"""Tekstovi i stranice iz CMS-a: prednost pred jezici/, zamjena kad nisu ispravni (W42)."""

import json
from pathlib import Path

from conftest import katalog_probni

from backend.iscrtavanje import Iscrtavac
from web.gradnja import gradi
from web.postavke import ucitaj_drzave, ucitaj_jezik, ucitaj_postavke
from web.tekstovi import prekrij

OSNOVA = {
    "naslovna": {
        "uvod": "Uzgajamo ga sami.",
        "cinjenice": [{"oznaka": "Analiza", "tekst": "Svaka šarža"}],
    },
    "dnevnik": {"sorta_uvod": "Snimke sorte {sorta}."},
    "proizvod": {"rok_slanja": ""},
}


def _upisi(korijen: Path, put: str, podaci: dict | str) -> None:
    datoteka = korijen / put
    datoteka.parent.mkdir(parents=True, exist_ok=True)
    tekst = podaci if isinstance(podaci, str) else json.dumps(podaci, ensure_ascii=False)
    datoteka.write_text(tekst, encoding="utf-8")


def _proizvod(korijen: Path) -> None:
    _upisi(
        korijen,
        "sadrzaj/proizvodi/gelonade.json",
        {
            "hr": {
                "naziv": "Gelonade",
                "kategorija": "cvijet",
                "pakiranja": [{"oznaka": "1 g", "cijena": 8}],
            }
        },
    )


def test_tekst_iz_cms_a_ima_prednost():
    jezik = prekrij(
        OSNOVA, {"naslovna": {"uvod": "  Novi uvod.  "}, "proizvod": {"rok_slanja": "Isti dan."}}
    )
    assert jezik["naslovna"]["uvod"] == "Novi uvod."
    assert jezik["proizvod"]["rok_slanja"] == "Isti dan."
    assert jezik["naslovna"]["cinjenice"] == OSNOVA["naslovna"]["cinjenice"]
    assert OSNOVA["naslovna"]["uvod"] == "Uzgajamo ga sami."


def test_prazno_polje_ostavlja_tekst_iz_jezika(caplog):
    jezik = prekrij(OSNOVA, {"naslovna": {"uvod": "   "}, "proizvod": {"rok_slanja": None}})
    assert jezik["naslovna"]["uvod"] == "Uzgajamo ga sami."
    assert jezik["proizvod"]["rok_slanja"] == ""
    assert caplog.text == ""


def test_krivi_tip_i_nepoznat_kljuc_se_preskacu(caplog):
    jezik = prekrij(
        OSNOVA,
        {"naslovna": {"uvod": 5, "nepostojeci": "x"}, "dnevnik": "tekst", "novo": {"a": "b"}},
    )
    assert jezik["naslovna"]["uvod"] == "Uzgajamo ga sami."
    assert "nepostojeci" not in jezik["naslovna"] and "novo" not in jezik
    assert jezik["dnevnik"] == OSNOVA["dnevnik"]
    for put in ("naslovna.uvod", "naslovna.nepostojeci", "dnevnik", "novo"):
        assert f"tekst {put} " in caplog.text


def test_polja_u_viticastim_zagradama_moraju_ostati(caplog):
    for los in ("Snimke sorte.", "Snimke sorte {sorta} i {berba}.", "Snimke {sorta", "{naziv}"):
        jezik = prekrij(OSNOVA, {"dnevnik": {"sorta_uvod": los}})
        assert jezik["dnevnik"]["sorta_uvod"] == "Snimke sorte {sorta}."
    assert caplog.text.count("dnevnik.sorta_uvod") == 4
    dobar = prekrij(OSNOVA, {"dnevnik": {"sorta_uvod": "Kako je rasla {sorta}"}})
    assert dobar["dnevnik"]["sorta_uvod"] == "Kako je rasla {sorta}"
    bez_polja = prekrij(OSNOVA, {"naslovna": {"uvod": "Uzgoj {2026}"}})
    assert bez_polja["naslovna"]["uvod"] == "Uzgajamo ga sami."


def test_vozni_red_cijeli_iz_cms_a_ili_cijeli_iz_jezika(caplog):
    novi = [{"oznaka": "Uzgoj", "tekst": "Zagreb"}, {"oznaka": " Dostava ", "tekst": "BOX NOW"}]
    jezik = prekrij(OSNOVA, {"naslovna": {"cinjenice": novi}})
    assert jezik["naslovna"]["cinjenice"][1] == {"oznaka": "Dostava", "tekst": "BOX NOW"}
    for los in ([], [{"oznaka": "Uzgoj"}], [{"oznaka": "Uzgoj", "tekst": " "}], "Uzgoj"):
        jezik = prekrij(OSNOVA, {"naslovna": {"cinjenice": los}})
        assert jezik["naslovna"]["cinjenice"] == OSNOVA["naslovna"]["cinjenice"]
    assert caplog.text.count("popis naslovna.cinjenice") == 4


def test_jezik_cita_sve_datoteke_iz_cms_a(repo_kopija, caplog):
    _upisi(repo_kopija, "sadrzaj/tekstovi/hr/naslovna.json", {"naslovna": {"uvod": "Iz CMS-a."}})
    _upisi(repo_kopija, "sadrzaj/tekstovi/hr/kosarica.json", {"kosarica": {"naslov": "Kolica"}})
    _upisi(repo_kopija, "sadrzaj/tekstovi/hr/pokvaren.json", '{"naslovna": ')
    jezik = ucitaj_jezik("hr", repo_kopija)
    assert jezik["naslovna"]["uvod"] == "Iz CMS-a."
    assert jezik["kosarica"]["naslov"] == "Kolica"
    assert jezik["kosarica"]["prazna"] == "Košarica je prazna."
    assert "tekst pokvaren preskočen" in caplog.text


def test_gradnja_i_backend_pokazuju_isti_tekst_iz_cms_a(repo_kopija, tmp_path):
    _proizvod(repo_kopija)
    _upisi(
        repo_kopija,
        "sadrzaj/tekstovi/hr/izbornik-i-podnozje.json",
        {"izbornik": {"kosarica": "Kolica"}, "podnozje": {"kontakt": "Javite se"}},
    )
    _upisi(
        repo_kopija, "sadrzaj/tekstovi/hr/kategorije.json", {"kategorije": {"cvijet": "Cvjetovi"}}
    )
    _upisi(repo_kopija, "sadrzaj/tekstovi/hr/naslovna.json", {"naslovna": {"uvod": "Novi uvod."}})
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    naslovna = (izlaz / "index.html").read_text()
    assert "Novi uvod." in naslovna and "Uzgajamo ga sami" not in naslovna
    assert ">Kolica</span>" in naslovna and ">Javite se</p>" in naslovna
    assert "Cvjetovi</a>" in (izlaz / "proizvod" / "gelonade" / "index.html").read_text()

    drzave = ucitaj_drzave(repo_kopija)
    iscrtavac = Iscrtavac(repo_kopija, ucitaj_postavke(repo_kopija), drzave)
    podaci = {"naslov": "Poruka", "retci": [], "obrazac": None}
    html = iscrtavac.stranica("poruka.html", drzave[0], katalog_probni(), podaci)
    assert ">Kolica</span>" in html and ">Javite se</p>" in html and "Cvjetovi</a>" in html


def test_stranice_iz_cms_a(repo_kopija, tmp_path, caplog):
    _upisi(
        repo_kopija,
        "sadrzaj/stranice/hr/kontakt.json",
        {"naslov": "Javite nam se", "tekst": "Pišite na **mail**.\n\n## Dućan\n\nTrg 10."},
    )
    _upisi(repo_kopija, "sadrzaj/stranice/hr/privatnost.json", '{"naslov": ')
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    kontakt = (izlaz / "kontakt" / "index.html").read_text()
    assert "<title>Javite nam se · Terpen Station</title>" in kontakt
    assert "<h1>Javite nam se</h1>" in kontakt and "<h2>Dućan</h2>" in kontakt
    assert 'content="Pišite na mail."' in kontakt
    assert ">Javite nam se</a>" in (izlaz / "index.html").read_text()
    assert not (izlaz / "privatnost").exists()
    assert "tekst stranice privatnost preskočen" in caplog.text
    odustanak = (izlaz / "odustanak" / "index.html").read_text()
    assert odustanak.count("<h1>Odustanak od ugovora</h1>") == 1
