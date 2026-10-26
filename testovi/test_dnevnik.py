"""W8: dnevnik uzgoja iz CMS-a: popis, sorta, zapis, proizvod, naslovna i izbornik."""

import json
import re
from pathlib import Path

import pytest

from backend.iscrtavanje import Iscrtavac
from web.datoteke import NAJVECA_DATOTEKA
from web.dnevnik import mnozina
from web.gradnja import gradi
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_postavke

ZAPISI = ["{broj} zapis", "{broj} zapisa", "{broj} zapisa"]


def _proizvod(korijen: Path) -> None:
    podaci = {
        "hr": {
            "naziv": "Gelonade",
            "kategorija": "cvijet",
            "slike": ["/slike/probna.jpg"],
            "cbg": "8,08 %",
            "pakiranja": [{"oznaka": "1 g", "cijena": 8, "tezina_g": 1}],
        }
    }
    put = korijen / "sadrzaj" / "proizvodi" / "gelonade.json"
    put.write_text(json.dumps(podaci), encoding="utf-8")


def _zapis(korijen: Path, slug: str, **polja) -> None:
    mapa = korijen / "sadrzaj" / "dnevnik"
    mapa.mkdir(parents=True, exist_ok=True)
    osnova = {"naslov": "Zapis", "datum": "2026-10-22", "slike": ["/slike/probna.jpg"]}
    tekst = json.dumps({"hr": {**osnova, **polja}}, ensure_ascii=False)
    (mapa / f"{slug}.json").write_text(tekst, encoding="utf-8")


def _video(korijen: Path) -> str:
    mapa = korijen / "static" / "mediji" / "dnevnik"
    mapa.mkdir(parents=True, exist_ok=True)
    (mapa / "trihomi.mp4").write_bytes(b"\x00")
    return "/mediji/dnevnik/trihomi.mp4"


def _html(izlaz: Path, put: str) -> str:
    return (izlaz / put / "index.html").read_text(encoding="utf-8")


def _json_ld(html: str) -> dict:
    blokovi = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html)
    return {podaci["@type"]: podaci for podaci in map(json.loads, blokovi)}


@pytest.fixture
def izgradjen(repo_kopija: Path, tmp_path: Path, caplog) -> Path:
    _proizvod(repo_kopija)
    _zapis(
        repo_kopija,
        "2026-10-22-trihomi",
        naslov="Trihomi izbliza",
        tekst="Zadnji tjedni cvatnje.\n\nDrugi odlomak.",
        faza="cvjetanje",
        proizvod="gelonade",
        video=_video(repo_kopija),
        trajanje_s=18,
        instagram="https://www.instagram.com/p/abc/",
    )
    _zapis(
        repo_kopija,
        "2026-09-24-susenje",
        naslov="Šarža nakon sušenja",
        datum="2026-09-24",
        faza="susenje",
        proizvod="gelonade",
        video_na_instagramu=True,
        instagram="https://www.instagram.com/p/def/",
    )
    _zapis(
        repo_kopija,
        "2026-06-30-led",
        naslov="Cvatnja pod LED-om",
        datum="2026-06-30",
        slike=["/slike/probna.jpg"] * 3,
    )
    _zapis(repo_kopija, "2026-05-01-skriveno", naslov="Promocija", objavljeno=False)
    _zapis(repo_kopija, "2026-05-02-los-datum", datum="nije datum")
    _zapis(repo_kopija, "2026-05-03-bez-naslova", naslov="")
    _zapis(
        repo_kopija,
        "2026-05-04-link",
        naslov="Opasan link",
        datum="2026-05-04",
        faza="nepoznata",
        instagram="javascript:alert(1)",
    )
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    return izlaz


def test_popis_od_najnovijeg_s_mjesecima_i_oznakama(izgradjen, caplog):
    # Gradnja je u pripremi testa, pa su i njezina upozorenja zapisana u toj fazi.
    log = "\n".join(zapis.getMessage() for zapis in caplog.get_records("setup"))
    popis = _html(izgradjen, "dnevnik")
    redoslijed = [popis.index(naslov) for naslov in ("Trihomi", "Šarža", "Cvatnja", "Opasan")]
    assert redoslijed == sorted(redoslijed)
    for mjesec in ("Listopad 2026", "Rujan 2026", "Lipanj 2026", "Svibanj 2026"):
        assert mjesec in popis
    assert ">0:18</span>" in popis and "3 fotke" in popis and ">Instagram<" in popis
    assert "4 zapisa" in popis and "@canna_lab_hr" in popis
    assert "<title>Dnevnik uzgoja CBG cvijeta · Terpen Station</title>" in popis
    assert not (izgradjen / "dnevnik" / "2026-05-01-skriveno").exists()
    for slug in ("2026-05-02-los-datum", "2026-05-03-bez-naslova"):
        assert f"zapis {slug} preskočen" in log
        assert not (izgradjen / "dnevnik" / slug).exists()
    assert "nepoznata faza" in log
    assert "javascript:" not in _html(izgradjen, "dnevnik/2026-05-04-link")


def test_stranica_zapisa(izgradjen):
    html = _html(izgradjen, "dnevnik/2026-10-22-trihomi")
    assert "<video" in html and 'src="/mediji/dnevnik/trihomi.mp4"' in html
    assert ">22. 10. 2026.</time>" in html and ">Cvjetanje</span>" in html
    assert '<meta property="og:type" content="article">' in html
    assert 'href="https://www.instagram.com/p/abc/"' in html
    assert "Ova sorta u trgovini" in html and 'href="/proizvod/gelonade/"' in html
    assert 'href="/dnevnik/2026-09-24-susenje/"' in html and "Prethodni zapis" in html
    objava = _json_ld(html)["BlogPosting"]
    assert objava["headline"] == "Trihomi izbliza"
    assert objava["datePublished"] == "2026-10-22"
    assert objava["description"] == "Zadnji tjedni cvatnje."
    assert objava["video"]["contentUrl"].endswith("/mediji/dnevnik/trihomi.mp4")
    mrvice = _json_ld(html)["BreadcrumbList"]["itemListElement"]
    assert [m["name"] for m in mrvice] == ["Terpen Station", "Dnevnik uzgoja", "Trihomi izbliza"]


def test_sorta_proizvod_naslovna_i_izbornik(izgradjen):
    sorta = _html(izgradjen, "dnevnik/gelonade")
    assert "Trihomi izbliza" in sorta and "Šarža nakon sušenja" in sorta
    assert "Cvatnja pod LED-om" not in sorta
    assert 'aria-current="page">Gelonade</a>' in sorta
    proizvod = _html(izgradjen, "proizvod/gelonade")
    assert "Iz dnevnika" in proizvod and 'href="/dnevnik/gelonade/"' in proizvod
    assert "Trihomi izbliza" in proizvod and "Cvatnja pod LED-om" not in proizvod
    naslovna = (izgradjen / "index.html").read_text(encoding="utf-8")
    assert 'href="/dnevnik/"' in naslovna and "Cijeli dnevnik" in naslovna
    katalog = json.loads((izgradjen / "proizvodi.json").read_text())
    assert katalog["dnevnik"] == "/dnevnik/"
    sitemap = (izgradjen / "sitemap.xml").read_text()
    assert "https://terpenstation.com/dnevnik/2026-10-22-trihomi/" in sitemap
    assert "https://terpenstation.com/dnevnik/gelonade/" in sitemap


def test_bez_zapisa_nema_dnevnika(repo_kopija, tmp_path):
    _proizvod(repo_kopija)
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    assert not (izlaz / "dnevnik").exists()
    assert 'href="/dnevnik/"' not in (izlaz / "index.html").read_text(encoding="utf-8")
    assert json.loads((izlaz / "proizvodi.json").read_text())["dnevnik"] == ""


def test_popis_po_stranicama(repo_kopija, tmp_path):
    _proizvod(repo_kopija)
    for dan in range(1, 13):
        _zapis(
            repo_kopija, f"2026-01-{dan:02d}-z", naslov=f"Zapis {dan}", datum=f"2026-01-{dan:02d}"
        )
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    prva, druga = _html(izlaz, "dnevnik"), _html(izlaz, "dnevnik/2")
    assert 'href="/dnevnik/2/"' in prva and "Stariji zapisi" in prva
    assert "Zapis 12" in prva and "Zapis 2<" not in prva
    assert 'href="/dnevnik/"' in druga and "Noviji zapisi" in druga
    assert "Zapis 2<" in druga and "· stranica 2 ·" in druga


def test_video_koji_ne_postoji(repo_kopija, tmp_path, caplog):
    _proizvod(repo_kopija)
    _zapis(repo_kopija, "2026-10-22-v", naslov="Bez datoteke", video="/mediji/dnevnik/nema.mp4")
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    assert "video /mediji/dnevnik/nema.mp4 ne postoji" in caplog.text
    assert "<video" not in _html(izlaz, "dnevnik/2026-10-22-v")


def test_prevelik_video_ne_ide_na_sajt(repo_kopija, tmp_path, caplog):
    _proizvod(repo_kopija)
    video = _video(repo_kopija)
    # Rijetka datoteka prijeđe granicu bez pisanja 25 MiB na disk.
    with (repo_kopija / "static" / video.lstrip("/")).open("r+b") as datoteka:
        datoteka.truncate(NAJVECA_DATOTEKA + 1)
    _zapis(repo_kopija, "2026-10-22-v", naslov="Prevelik", video=video)
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    assert "trihomi.mp4 je veća od 25 MiB i ne ide na sajt" in caplog.text
    assert f"video {video} je veći od 25 MiB" in caplog.text
    assert not (izlaz / video.lstrip("/")).exists()
    assert "<video" not in _html(izlaz, "dnevnik/2026-10-22-v")


@pytest.mark.parametrize(
    ("broj", "tekst"),
    [
        (1, "1 zapis"),
        (2, "2 zapisa"),
        (4, "4 zapisa"),
        (5, "5 zapisa"),
        (11, "11 zapisa"),
        (14, "14 zapisa"),
        (21, "21 zapis"),
        (22, "22 zapisa"),
        (111, "111 zapisa"),
    ],
)
def test_mnozina(broj, tekst):
    assert mnozina(broj, ZAPISI) == tekst


def test_fotke_po_broju():
    fotke = ["{broj} fotka", "{broj} fotke", "{broj} fotki"]
    assert [mnozina(n, fotke) for n in (1, 3, 5, 12, 23)] == [
        "1 fotka",
        "3 fotke",
        "5 fotki",
        "12 fotki",
        "23 fotke",
    ]


def test_izbornik_backenda_zna_za_dnevnik():
    iscrtavac = Iscrtavac(KORIJEN, ucitaj_postavke(), ucitaj_drzave())
    drzava = ucitaj_drzave()[0]
    podaci = {"naslov": "N", "retci": ["a"], "obrazac": None}
    s_dnevnikom = iscrtavac.stranica("poruka.html", drzava, {"dnevnik": "/dnevnik/"}, podaci)
    bez = iscrtavac.stranica("poruka.html", drzava, {}, podaci)
    assert 'href="https://terpenstation.com/dnevnik/"' in s_dnevnikom
    assert "/dnevnik/" not in bez
