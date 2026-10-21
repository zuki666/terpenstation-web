import json
import shutil
from pathlib import Path

import httpx
import pytest

from backend import baza
from backend.boxnow import Klijent
from backend.iscrtavanje import Iscrtavac
from backend.mailovi import Slanje
from backend.okolina import Okolina, link_boxnow
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_postavke

TAJNA = "probna-tajna"


class LaznaPosta:
    """Skuplja poslane mailove; `pokvarena` glumi pad SMTP-a."""

    def __init__(self) -> None:
        self.poslano = []
        self.pokvarena = False

    def posalji(self, poruka) -> None:
        if self.pokvarena:
            raise OSError("SMTP ne radi")
        self.poslano.append(poruka)


class LazniKatalog:
    def __init__(self, podaci: dict) -> None:
        self.podaci = podaci

    def dohvati(self, drzava: dict) -> dict:
        return self.podaci


def katalog_probni() -> dict:
    return {
        "verzija": "2026-10-21T10:00:00Z",
        "drzava": "hr",
        "datoteke": {"css": "/css/stil.abc.css", "js": "/js/kosarica.abc.js"},
        "kategorije": ["cvijet", "pribor"],
        "proizvodi": [
            {
                "id": "gelonade",
                "naziv": "Gelonade",
                "url": "/proizvod/gelonade/",
                "slika": "",
                "kategorija": "cvijet",
                "pakiranja": [
                    {"id": "gelonade:1", "oznaka": "1 g", "cijena_c": 990, "tezina_g": 1},
                    {"id": "gelonade:2", "oznaka": "3 g", "cijena_c": 2700, "tezina_g": 3},
                ],
            },
            {
                "id": "papirici",
                "naziv": "Papirići",
                "url": "/proizvod/papirici/",
                "slika": "",
                "kategorija": "pribor",
                "pakiranja": [
                    {"id": "papirici:1", "oznaka": "1 knjižica", "cijena_c": 150, "tezina_g": None}
                ],
            },
        ],
    }


def boxnow_odgovori(zahtjevi: list) -> httpx.MockTransport:
    """Lažni BOX NOW: token, pošiljka s paketom 1234567890 i PDF naljepnica."""

    def odgovor(zahtjev: httpx.Request) -> httpx.Response:
        zahtjevi.append(zahtjev)
        put = zahtjev.url.path
        if put == "/api/v1/auth-sessions":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if put == "/api/v1/delivery-requests":
            return httpx.Response(200, json={"id": "42", "parcels": [{"id": "1234567890"}]})
        if put == "/api/v1/parcels/1234567890/label.pdf":
            return httpx.Response(200, content=b"%PDF-naljepnica")
        return httpx.Response(404)

    return httpx.MockTransport(odgovor)


@pytest.fixture
def okolina(tmp_path: Path) -> Okolina:
    postavke = ucitaj_postavke()
    postavke["sajt"] = {
        "adresa": "https://terpenstation.com",
        "api": "https://api.terpenstation.com",
    }
    drzave = ucitaj_drzave()
    putanja = tmp_path / "trgovina.db"
    veza = baza.povezi(putanja)
    baza.migriraj(veza)
    veza.close()
    iscrtavac = Iscrtavac(KORIJEN, postavke, drzave)
    posta = LaznaPosta()
    zahtjevi: list = []
    klijent = Klijent(
        "https://api-test.boxnow.hr",
        ("id", "tajna"),
        httpx.Client(transport=boxnow_odgovori(zahtjevi)),
    )
    klijent.zahtjevi = zahtjevi
    return Okolina(
        postavke=postavke,
        drzave=drzave,
        baza=putanja,
        katalog=LazniKatalog(katalog_probni()),
        iscrtavac=iscrtavac,
        slanje=Slanje(postavke, iscrtavac, posta, link_boxnow(postavke, TAJNA)),
        tajna_linkova=TAJNA,
        boxnow=klijent,
    )


@pytest.fixture
def klijent(okolina: Okolina):
    from backend.aplikacija import stvori

    app = stvori(okolina)
    app.testing = True
    return app.test_client()


def obrazac(**izmjene: str) -> dict:
    """Ispravna narudžba: 2 × Gelonade 3 g, GLS, uplata = 54,00 + 4,90."""
    podaci = {
        "drzava": "hr",
        "ime": "Ivana Horvat",
        "email": "ivana@example.com",
        "telefon": "091 234 5678",
        "dostava": "gls",
        "ulica": "Ilica 10",
        "postanski_broj": "10000",
        "mjesto": "Zagreb",
        "placanje": "uplata",
        "punoljetan": "da",
        "uvjeti": "da",
        "stavke": json.dumps([{"id": "gelonade:2", "kolicina": 2}]),
        "verzija": "2026-10-21T10:00:00Z",
        "ukupno_c": "5890",
        "sekundi": "40",
        "web": "",
    }
    podaci.update(izmjene)
    return podaci


@pytest.fixture
def repo_kopija(tmp_path: Path) -> Path:
    """Kopija repoa za gradnju, bez videa, s malom probnom slikom."""
    korijen = tmp_path / "repo"
    for mapa in ("drzave", "jezici", "predlosci", "wholesale"):
        shutil.copytree(KORIJEN / mapa, korijen / mapa)
    shutil.copy(KORIJEN / "postavke.toml", korijen / "postavke.toml")
    shutil.copytree(
        KORIJEN / "static", korijen / "static", ignore=shutil.ignore_patterns("mediji", "*.jpg")
    )
    (korijen / "sadrzaj" / "proizvodi").mkdir(parents=True)
    shutil.copytree(KORIJEN / "sadrzaj" / "stranice", korijen / "sadrzaj" / "stranice")
    from PIL import Image

    Image.new("RGB", (1000, 1250), (120, 140, 90)).save(korijen / "static" / "slike" / "probna.jpg")
    return korijen
