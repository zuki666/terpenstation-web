"""WebP u više širina za srcset; ime sadrži hash izvora, pa se cache nikad ne pomiješa."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

log = logging.getLogger(__name__)

SIRINE = (400, 800, 1600)
KVALITETA = 82
MAPA = "slike/r"


@dataclass(frozen=True)
class Slika:
    src: str
    srcset: str
    mala: str
    velika: str
    sirina: int
    visina: int


def _sirine(izvorna: int) -> list[int]:
    # Manja slika se ne povećava; najveća širina je izvorna kad je uža od 1600 px.
    manje = [sirina for sirina in SIRINE if sirina < izvorna]
    return [*manje, min(izvorna, SIRINE[-1])]


class Slike:
    """Pretvara slike iz static/ u dist/slike/r/; svaka se obradi samo jednom po gradnji."""

    def __init__(self, static: Path, izlaz: Path) -> None:
        self.static = static
        self.izlaz = izlaz
        self.gotove: dict[str, Slika | None] = {}

    def obradi(self, put: str) -> Slika | None:
        if put not in self.gotove:
            self.gotove[put] = self._pretvori(put)
        return self.gotove[put]

    def _pretvori(self, put: str) -> Slika | None:
        izvor = self.static / put.lstrip("/")
        if not izvor.is_file():
            log.warning("slika %s ne postoji, preskočena", put)
            return None
        sazetak = hashlib.sha256(izvor.read_bytes()).hexdigest()[:10]
        try:
            with Image.open(izvor) as otvorena:
                slika = ImageOps.exif_transpose(otvorena).convert("RGB")
        except OSError as greska:
            log.warning("slika %s nije čitljiva (%s), preskočena", put, greska)
            return None
        (self.izlaz / MAPA).mkdir(parents=True, exist_ok=True)
        verzije = [
            self._spremi(slika, izvor.stem, sazetak, sirina) for sirina in _sirine(slika.width)
        ]
        srcset = ", ".join(f"{url} {sirina}w" for url, sirina in verzije)
        srednja = verzije[min(1, len(verzije) - 1)][0]
        visina = round(slika.height * verzije[-1][1] / slika.width)
        return Slika(srednja, srcset, verzije[0][0], verzije[-1][0], verzije[-1][1], visina)

    def _spremi(self, slika: Image.Image, ime: str, sazetak: str, sirina: int) -> tuple[str, int]:
        datoteka = f"{ime}-{sirina}-{sazetak}.webp"
        cilj = self.izlaz / MAPA / datoteka
        if not cilj.exists():
            visina = round(slika.height * sirina / slika.width)
            slika.resize((sirina, visina), Image.Resampling.LANCZOS).save(
                cilj, "WEBP", quality=KVALITETA, method=6
            )
        return f"/{MAPA}/{datoteka}", sirina
