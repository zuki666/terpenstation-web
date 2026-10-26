"""Jedna stranica koju gradnja iscrta: put, predložak, oznake za <head> i podaci predloška."""

from dataclasses import dataclass, field


@dataclass
class Stranica:
    kljuc: tuple[str, str]
    put: str
    predlozak: str
    naslov: str
    opis: str
    podaci: dict = field(default_factory=dict)
    indeks: bool = True
    og_slika: str = ""
    aktivna: str = ""
    json_ld: list[dict] = field(default_factory=list)
