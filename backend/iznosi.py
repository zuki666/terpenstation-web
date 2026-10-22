"""Iznosi narudžbe u centima."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Iznosi:
    meduzbroj_c: int
    dostava_c: int
    naknada_c: int
    ukupno_c: int
    pdv_c: int


def pdv_u_iznosu(ukupno_c: int, posto: int) -> int:
    """„Od toga PDV”, zaokruženo na cent kao u pregledniku (pola se zaokružuje gore)."""
    nazivnik = 100 + posto
    return (2 * ukupno_c * posto + nazivnik) // (2 * nazivnik)


def izracunaj(stavke: list[dict], drzava: dict, dostava: str, placanje: str) -> Iznosi:
    meduzbroj = sum(stavka["cijena_c"] * stavka["kolicina"] for stavka in stavke)
    prag = drzava.get("besplatna_dostava_od_c", 0)
    besplatna = prag > 0 and meduzbroj >= prag
    cijena_dostave = 0 if besplatna else drzava["dostava"][dostava]["cijena_c"]
    naknada = drzava["placanje"]["pouzece"]["naknada_c"] if placanje == "pouzece" else 0
    ukupno = meduzbroj + cijena_dostave + naknada
    return Iznosi(
        meduzbroj, cijena_dostave, naknada, ukupno, pdv_u_iznosu(ukupno, drzava["pdv_posto"])
    )
