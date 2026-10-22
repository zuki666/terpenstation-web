import json
import shutil
from pathlib import Path

from web.gradnja import gradi


def _proizvod(korijen: Path, slug: str, podaci: dict | str) -> None:
    tekst = podaci if isinstance(podaci, str) else json.dumps(podaci, ensure_ascii=False)
    (korijen / "sadrzaj" / "proizvodi" / f"{slug}.json").write_text(tekst, encoding="utf-8")


def _hr(**polja) -> dict:
    osnova = {
        "naziv": "Gelonade",
        "kategorija": "cvijet",
        "slike": ["/slike/probna.jpg"],
        "pakiranja": [{"oznaka": "1 g", "cijena": 9.9}, {"oznaka": "3 g", "cijena": "27"}],
    }
    return {"hr": {**osnova, **polja}}


def _druga_drzava(korijen: Path) -> None:
    """Slovenija na /si/ sa slovenskim jezikom: kopija hrvatskih tekstova je dovoljna za test."""
    hr = (korijen / "drzave" / "hr.toml").read_text(encoding="utf-8")
    si = hr.replace('kod = "hr"', 'kod = "si"').replace('jezik = "hr"', 'jezik = "sl"')
    (korijen / "drzave" / "si.toml").write_text(si.replace('put = "/"', 'put = "/si/"'))
    shutil.copy(korijen / "jezici" / "hr.toml", korijen / "jezici" / "sl.toml")


def test_gradnja_preskace_neispravne_proizvode(repo_kopija, tmp_path, caplog):
    _proizvod(repo_kopija, "gelonade", _hr())
    _proizvod(repo_kopija, "bez-cijene", _hr(naziv="A", pakiranja=[{"oznaka": "1 g"}]))
    _proizvod(repo_kopija, "negativna", _hr(naziv="B", pakiranja=[{"oznaka": "1 g", "cijena": -1}]))
    _proizvod(repo_kopija, "bez-pakiranja", _hr(naziv="C", pakiranja=[]))
    _proizvod(repo_kopija, "kategorija", _hr(naziv="D", kategorija="cipele"))
    _proizvod(repo_kopija, "bez-naziva", _hr(naziv=""))
    _proizvod(repo_kopija, "pokvaren", '{"hr": {"naziv": ')
    _proizvod(repo_kopija, "ugasen", _hr(naziv="E", dostupno=False))
    izlaz = tmp_path / "dist"

    gradi(izlaz, repo_kopija)

    katalog = json.loads((izlaz / "proizvodi.json").read_text())
    assert [p["id"] for p in katalog["proizvodi"]] == ["gelonade"]
    assert katalog["proizvodi"][0]["pakiranja"][0] == {
        "id": "gelonade:1",
        "oznaka": "1 g",
        "cijena_c": 990,
        "tezina_g": None,
    }
    assert katalog["proizvodi"][0]["pakiranja"][1]["cijena_c"] == 2700
    assert katalog["datoteke"]["css"].startswith("/css/stil.")
    assert (izlaz / katalog["datoteke"]["js"].lstrip("/")).exists()
    for slug in (
        "bez-cijene",
        "negativna",
        "bez-pakiranja",
        "kategorija",
        "bez-naziva",
        "pokvaren",
    ):
        assert f"proizvod {slug} preskočen" in caplog.text
    assert not (izlaz / "proizvod" / "ugasen").exists()
    assert (izlaz / "proizvod" / "gelonade" / "index.html").exists()


def test_kategorija_bez_proizvoda_se_ne_gradi(repo_kopija, tmp_path):
    _proizvod(repo_kopija, "gelonade", _hr())
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    assert (izlaz / "cvijet" / "index.html").exists()
    assert not (izlaz / "pribor").exists()
    naslovna = (izlaz / "index.html").read_text()
    assert 'href="/cvijet/"' in naslovna and 'href="/pribor/"' not in naslovna


def test_slike_u_vise_sirina_bez_povecavanja(repo_kopija, tmp_path):
    _proizvod(repo_kopija, "gelonade", _hr())
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    sirine = sorted(
        int(p.name.split("-")[1]) for p in (izlaz / "slike" / "r").glob("probna-*.webp")
    )
    assert sirine == [400, 800, 1000]
    stranica = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert (
        "400w" in stranica and 'og:image" content="https://terpenstation.com/slike/r/' in stranica
    )


def test_ostale_datoteke(repo_kopija, tmp_path):
    _proizvod(repo_kopija, "gelonade", _hr())
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)
    assert "Disallow: /admin/" in (izlaz / "robots.txt").read_text()
    assert "/admin/*" in (izlaz / "_headers").read_text()
    karta = (izlaz / "sitemap.xml").read_text()
    assert "https://terpenstation.com/proizvod/gelonade/" in karta
    assert "kosarica" not in karta
    assert (izlaz / "wholesale" / "index.html").exists()
    assert (izlaz / "404.html").exists()
    assert "noindex" in (izlaz / "blagajna" / "index.html").read_text()


def test_proizvod_bez_prijevoda_i_hreflang(repo_kopija, tmp_path):
    _druga_drzava(repo_kopija)
    _proizvod(repo_kopija, "gelonade", {**_hr(), "sl": {"naziv": "Gelonade SI"}})
    _proizvod(repo_kopija, "samo-hr", _hr(naziv="Samo HR"))
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)

    si = json.loads((izlaz / "si" / "proizvodi.json").read_text())
    assert [p["naziv"] for p in si["proizvodi"]] == ["Gelonade SI"]
    assert si["proizvodi"][0]["url"] == "/si/proizvod/gelonade/"
    assert si["proizvodi"][0]["pakiranja"][0]["cijena_c"] == 990
    assert not (izlaz / "si" / "proizvod" / "samo-hr").exists()

    stranica = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert 'hreflang="sl-SI" href="https://terpenstation.com/si/proizvod/gelonade/"' in stranica
    assert 'hreflang="hr-HR"' in stranica
    assert 'class="drzave"' in stranica
    samo_hr = (izlaz / "proizvod" / "samo-hr" / "index.html").read_text()
    assert "sl-SI" not in samo_hr
    assert "Sitemap: https://terpenstation.com/si/sitemap.xml" in (izlaz / "robots.txt").read_text()
