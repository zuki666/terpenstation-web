"""W7: naslovi, JSON-LD, slike za pregled linka, sitemap i zaglavlja."""

import json
import re
import shutil
from pathlib import Path

from PIL import Image

from web.gradnja import gradi
from web.slike import _sirine


def _gradi(korijen: Path, izlaz: Path, **drzava) -> None:
    proizvod = {
        "hr": {
            "naziv": "Gelonade",
            "kratki_opis": "Hibrid.",
            "kategorija": "cvijet",
            "slike": ["/slike/probna.jpg"],
            "pakiranja": [{"oznaka": "1 g", "cijena": 8}, {"oznaka": "3 g", "cijena": 24.5}],
        }
    }
    (korijen / "sadrzaj" / "proizvodi" / "gelonade.json").write_text(json.dumps(proizvod))
    if drzava:
        put = korijen / "drzave" / "hr.toml"
        tekst = put.read_text(encoding="utf-8")
        for kljuc, vrijednost in drzava.items():
            tekst = re.sub(rf"^{kljuc} = .*$", f"{kljuc} = {vrijednost}", tekst, flags=re.M)
        put.write_text(tekst, encoding="utf-8")
    gradi(izlaz, korijen)


def _json_ld(html: str) -> dict:
    blokovi = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html)
    return {podaci["@type"]: podaci for podaci in map(json.loads, blokovi)}


def test_naslovi_s_pojmovima_koji_se_traze(repo_kopija, tmp_path):
    _gradi(repo_kopija, tmp_path / "dist")
    proizvod = (tmp_path / "dist" / "proizvod" / "gelonade" / "index.html").read_text()
    kategorija = (tmp_path / "dist" / "cvijet" / "index.html").read_text()
    assert "<title>Gelonade · CBG cvijet · Terpen Station</title>" in proizvod
    assert "<title>CBG cvijet · Terpen Station</title>" in kategorija
    assert '<a href="/cvijet/"' in kategorija and ">Cvijet</a>" in kategorija


def test_json_ld_proizvoda_i_mrvica(repo_kopija, tmp_path):
    _gradi(repo_kopija, tmp_path / "dist")
    html = (tmp_path / "dist" / "proizvod" / "gelonade" / "index.html").read_text()
    podaci = _json_ld(html)
    proizvod = podaci["Product"]
    assert proizvod["name"] == "Gelonade" and proizvod["description"] == "Hibrid."
    assert proizvod["image"][0].startswith("https://terpenstation.com/slike/r/")
    assert [(o["name"], o["price"]) for o in proizvod["offers"]] == [
        ("1 g", "8.00"),
        ("3 g", "24.50"),
    ]
    ponuda = proizvod["offers"][0]
    assert ponuda["priceCurrency"] == "EUR" and ponuda["availability"].endswith("InStock")
    assert ponuda["shippingDetails"][0]["shippingRate"]["value"] == "3.50"
    mrvice = [k["name"] for k in podaci["BreadcrumbList"]["itemListElement"]]
    assert mrvice == ["Terpen Station", "CBG cvijet", "Gelonade"]
    naslovna = _json_ld((tmp_path / "dist" / "index.html").read_text())
    assert naslovna["Organization"]["taxID"] == "29737469043"
    assert "BreadcrumbList" in _json_ld((tmp_path / "dist" / "cvijet" / "index.html").read_text())


def test_pregled_linka_jpeg_na_svim_stranicama_koje_se_indeksiraju(repo_kopija, tmp_path):
    mediji = repo_kopija / "static" / "mediji"
    mediji.mkdir()
    Image.new("RGB", (1080, 1350), (90, 110, 70)).save(mediji / "gelonade-staklenka.jpg")
    izlaz = tmp_path / "dist"
    _gradi(repo_kopija, izlaz)
    for put in (
        "index.html",
        "cvijet/index.html",
        "proizvod/gelonade/index.html",
        "privatnost/index.html",
    ):
        html = (izlaz / put).read_text()
        slika = re.search(r'og:image" content="https://terpenstation.com(/[^"]+)"', html).group(1)
        assert slika.endswith(".jpg") and 'og:image:width" content="1200"' in html
        with Image.open(izlaz / slika.lstrip("/")) as otvorena:
            assert otvorena.format == "JPEG" and otvorena.size == (1200, 630)
    proizvod = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert "probna-pregled-" in proizvod
    assert "og:image" not in (izlaz / "blagajna" / "index.html").read_text()
    naslovna = (izlaz / "index.html").read_text()
    assert 'src="/slike/r/gelonade-staklenka-' in naslovna


def test_sitemap_zaglavlja_i_prva_slika(repo_kopija, tmp_path):
    izlaz = tmp_path / "dist"
    _gradi(repo_kopija, izlaz)
    assert "https://terpenstation.com/wholesale/" in (izlaz / "sitemap.xml").read_text()
    zaglavlja = (izlaz / "_headers").read_text()
    assert "https://:project.pages.dev/*\n  X-Robots-Tag: noindex" in zaglavlja
    assert "https://:version.:project.pages.dev/*\n  X-Robots-Tag: noindex" in zaglavlja
    html = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert html.count('fetchpriority="high"') == 1


def test_red_uz_gumb_i_besplatna_dostava(repo_kopija, tmp_path):
    izlaz = tmp_path / "dist"
    _gradi(repo_kopija, izlaz, placanja='["uplata", "pouzece"]')
    html = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert "BOX NOW <span" in html and "uplata na račun ili pouzeće" in html
    assert "Besplatna dostava" not in html
    assert "data-besplatna-od" not in (izlaz / "kosarica" / "index.html").read_text()

    shutil.rmtree(izlaz)
    _gradi(repo_kopija, izlaz, besplatna_dostava_od_c=4000)
    html = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert "Besplatna dostava od 40,00\xa0€." in html
    assert 'data-besplatna-od="4000"' in (izlaz / "kosarica" / "index.html").read_text()


def test_samo_pouzece(repo_kopija, tmp_path):
    izlaz = tmp_path / "dist"
    _gradi(repo_kopija, izlaz, placanja='["pouzece"]')
    proizvod = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    blagajna = (izlaz / "blagajna" / "index.html").read_text()
    assert "uplata na račun" not in proizvod
    assert 'value="uplata"' not in blagajna
    assert 'value="pouzece" required checked' in blagajna


def test_sirine_bez_dvostruke_najvece():
    assert _sirine(2000) == [400, 800, 1600]
    assert _sirine(1600) == [400, 800, 1600]
    assert _sirine(1000) == [400, 800, 1000]
    assert _sirine(300) == [300]
