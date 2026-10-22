"""Podaci za prikaz: cijena po gramu, najjeftinija dostava, brojevi perona, ploča polazaka."""

import json
from pathlib import Path

from web.gradnja import gradi
from web.postavke import ucitaj_drzave, ucitaj_jezik
from web.predlosci import cijene_po_gramu, najjeftinija_dostava, veze_kategorija
from web.proizvodi import Pakiranje


def _pakiranje(redni: int, cijena_c: int, tezina_g: float | None) -> Pakiranje:
    return Pakiranje(id=f"g:{redni}", oznaka=f"{tezina_g} g", cijena_c=cijena_c, tezina_g=tezina_g)


def test_cijena_po_gramu_za_proizvod_na_tezinu():
    pakiranja = (_pakiranje(1, 800, 1), _pakiranje(2, 2400, 3), _pakiranje(3, 7000, 10))
    cijene = cijene_po_gramu(pakiranja, na_tezinu=True)
    assert cijene["po_gramu"] == {"g:1": 800, "g:2": 800, "g:3": 700}
    assert cijene["po_gramu_c"] == 700
    assert not cijene["po_gramu_isti"]


def test_bez_cijene_po_gramu_kad_se_ne_prodaje_na_tezinu():
    assert cijene_po_gramu((_pakiranje(1, 1490, 120),), na_tezinu=False) == {
        "po_gramu": {},
        "po_gramu_c": 0,
        "po_gramu_isti": True,
    }
    assert cijene_po_gramu((_pakiranje(1, 1200, None),), na_tezinu=True)["po_gramu"] == {}


def test_najjeftinija_dostava_i_brojevi_perona():
    drzava = ucitaj_drzave()[0]
    cijene = [drzava["dostava"][kljuc]["cijena_c"] for kljuc in drzava["dostave"]]
    assert najjeftinija_dostava(drzava) == min(cijene)
    veze = veze_kategorija(drzava, ucitaj_jezik(drzava["jezik"]), ["cvijet", "ulje"])
    assert [(v["kljuc"], v["peron"]) for v in veze] == [("cvijet", 1), ("ulje", 2)]


def _proizvod(korijen: Path, slug: str, podaci: dict) -> None:
    datoteka = korijen / "sadrzaj" / "proizvodi" / f"{slug}.json"
    datoteka.write_text(json.dumps({"hr": podaci}, ensure_ascii=False), encoding="utf-8")


def test_naslovna_ploca_i_cijena_po_gramu(repo_kopija, tmp_path):
    _proizvod(
        repo_kopija,
        "gelonade",
        {
            "naziv": "Gelonade",
            "kategorija": "cvijet",
            "cbg": "8,08 %",
            "slike": ["/slike/probna.jpg"],
            "pakiranja": [
                {"oznaka": "1 g", "cijena": 8, "tezina_g": 1},
                {"oznaka": "10 g", "cijena": 70, "tezina_g": 10},
            ],
        },
    )
    _proizvod(
        repo_kopija,
        "grinder",
        {
            "naziv": "Grinder",
            "kategorija": "pribor",
            "pakiranja": [{"oznaka": "1 kom", "cijena": 14.9, "tezina_g": 120}],
        },
    )
    izlaz = tmp_path / "dist"
    gradi(izlaz, repo_kopija)

    naslovna = (izlaz / "index.html").read_text()
    assert naslovna.count('class="ploca-red"') == 2
    assert '<span class="za-citac">Gelonade</span>' in naslovna
    assert '<span class="klap" data-klap>G</span>' in naslovna
    assert 'data-sat="Europe/Zagreb"' in naslovna
    # Iznosi imaju tvrdi razmak prije €. Na kartici je najniža cijena po gramu, jer se
    # razlikuje od najniže cijene pakiranja.
    assert "7,00\xa0€/g" in naslovna

    proizvod = (izlaz / "proizvod" / "gelonade" / "index.html").read_text()
    assert "8,00\xa0€/g" in proizvod and "7,00\xa0€/g" in proizvod
    assert 'style="view-transition-name: p-gelonade"' in proizvod
    grinder = (izlaz / "proizvod" / "grinder" / "index.html").read_text()
    assert "/g</span>" not in grinder
    assert '<span class="peron-br" aria-hidden="true">2</span>' in grinder
