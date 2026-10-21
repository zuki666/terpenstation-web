"""Objavljeni proizvodi.json: izvor cijena za narudžbu (W14)."""

import json
import logging
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

TRAJANJE_S = 60
TIMEOUT_S = 10


class KatalogNedostupan(Exception):
    pass


def _ispravan(podaci: object) -> bool:
    return isinstance(podaci, dict) and isinstance(podaci.get("proizvodi"), list)


class Katalog:
    """Dohvat sa sajta uz cache od 60 s; kad dohvat ne uspije, vrijedi zadnja dobra kopija."""

    def __init__(self, adresa: str, mapa: Path, klijent: httpx.Client | None = None) -> None:
        self.adresa = adresa.rstrip("/")
        self.mapa = mapa
        self.klijent = klijent or httpx.Client(timeout=TIMEOUT_S, follow_redirects=True)
        self.memorija: dict[str, tuple[float, dict]] = {}

    def dohvati(self, drzava: dict) -> dict:
        kod = drzava["kod"]
        zapis = self.memorija.get(kod)
        if zapis and time.monotonic() - zapis[0] < TRAJANJE_S:
            return zapis[1]
        url = f"{self.adresa}{drzava['put']}proizvodi.json"
        try:
            odgovor = self.klijent.get(url)
            odgovor.raise_for_status()
            podaci = odgovor.json()
        except (httpx.HTTPError, ValueError) as greska:
            log.warning("dohvat %s nije uspio (%s), koristim zadnju kopiju", url, greska)
            return self._s_diska(kod)
        if not _ispravan(podaci):
            log.warning("%s nema popis proizvoda, koristim zadnju kopiju", url)
            return self._s_diska(kod)
        self._spremi(kod, podaci)
        return podaci

    def _datoteka(self, kod: str) -> Path:
        return self.mapa / f"proizvodi-{kod}.json"

    def _spremi(self, kod: str, podaci: dict) -> None:
        self.memorija[kod] = (time.monotonic(), podaci)
        self.mapa.mkdir(parents=True, exist_ok=True)
        privremena = self._datoteka(kod).with_suffix(".tmp")
        privremena.write_text(json.dumps(podaci, ensure_ascii=False), encoding="utf-8")
        privremena.replace(self._datoteka(kod))

    def _s_diska(self, kod: str) -> dict:
        datoteka = self._datoteka(kod)
        if not datoteka.exists():
            raise KatalogNedostupan(f"nema proizvodi.json za {kod} ni kopije na disku")
        return json.loads(datoteka.read_text(encoding="utf-8"))
