"""SQLite baza trgovine: veza, migracije, narudžbe i odustanci."""

import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

MIGRACIJE = Path(__file__).resolve().parent / "migracije"
TABLICE = frozenset({"narudzbe", "odustanci"})
STUPCI_MAILA = frozenset({"mail_trgovini", "mail_kupcu"})

STUPCI_NARUDZBE = (
    "drzava",
    "ime",
    "email",
    "telefon",
    "dostava",
    "paketomat_id",
    "paketomat_adresa",
    "ulica",
    "postanski_broj",
    "mjesto",
    "placanje",
    "stavke",
    "meduzbroj_c",
    "dostava_c",
    "naknada_c",
    "ukupno_c",
    "pdv_c",
    "tvrtka",
    "oib",
    "napomena",
    "izvor",
    "token",
    "ip",
)
STUPCI_ODUSTANKA = ("drzava", "broj", "email", "ime", "poruka", "ip")


class ZastarjelaBaza(Exception):
    pass


def povezi(putanja: Path | str) -> sqlite3.Connection:
    # Dva gunicorn radnika i timer pišu istovremeno; timeout čeka zaključavanje.
    veza = sqlite3.connect(putanja, timeout=30)
    veza.row_factory = sqlite3.Row
    veza.execute("PRAGMA journal_mode = WAL")
    veza.execute("PRAGMA synchronous = NORMAL")
    veza.execute("PRAGMA foreign_keys = ON")
    return veza


def popis_migracija(mapa: Path = MIGRACIJE) -> list[tuple[int, Path]]:
    migracije = sorted((int(p.name.split("_", 1)[0]), p) for p in mapa.glob("[0-9]*_*.sql"))
    brojevi = [broj for broj, _ in migracije]
    if len(brojevi) != len(set(brojevi)):
        raise ValueError(f"isti broj migracije više puta u {mapa}: {brojevi}")
    return migracije


def verzija(veza: sqlite3.Connection) -> int:
    return veza.execute("PRAGMA user_version").fetchone()[0]


def migriraj(veza: sqlite3.Connection, mapa: Path = MIGRACIJE) -> list[int]:
    trenutna = verzija(veza)
    nove = [(broj, put) for broj, put in popis_migracija(mapa) if broj > trenutna]
    for broj, put in nove:
        # user_version se mijenja u istoj transakciji, pa pukla migracija ne ostavi pola sheme.
        skripta = put.read_text(encoding="utf-8")
        veza.executescript(f"BEGIN;\n{skripta}\nPRAGMA user_version = {broj};\nCOMMIT;")
        log.info("migracija %s primijenjena", put.name)
    return [broj for broj, _ in nove]


def provjeri_verziju(veza: sqlite3.Connection, mapa: Path = MIGRACIJE) -> None:
    najnovija = max((broj for broj, _ in popis_migracija(mapa)), default=0)
    if verzija(veza) < najnovija:
        raise ZastarjelaBaza(
            f"baza je na verziji {verzija(veza)}, kod traži {najnovija}: "
            "pokreni `python -m backend migriraj`"
        )


def upisi_narudzbu(veza: sqlite3.Connection, podaci: dict, godina: int) -> str:
    """Upiše narudžbu pod sljedećim brojem u godini; vraća broj (npr. 2026-0012)."""
    # IMMEDIATE drži zaključavanje od čitanja zadnjeg broja do upisa, pa dva radnika
    # ne mogu dobiti isti broj.
    veza.execute("BEGIN IMMEDIATE")
    try:
        zadnji = veza.execute(
            "SELECT MAX(CAST(substr(broj, 6) AS INTEGER)) FROM narudzbe WHERE broj LIKE ?",
            (f"{godina}-%",),
        ).fetchone()[0]
        broj = f"{godina}-{(zadnji or 0) + 1:04d}"
        stupci = ("broj", *STUPCI_NARUDZBE)
        vrijednosti = (broj, *(podaci.get(stupac) for stupac in STUPCI_NARUDZBE))
        veza.execute(
            f"INSERT INTO narudzbe ({', '.join(stupci)}) VALUES ({', '.join('?' * len(stupci))})",
            vrijednosti,
        )
    except BaseException:
        veza.rollback()
        raise
    veza.commit()
    return broj


def _narudzba(red: sqlite3.Row | None) -> dict | None:
    if red is None:
        return None
    narudzba = dict(red)
    narudzba["stavke"] = json.loads(narudzba["stavke"])
    return narudzba


def narudzba(veza: sqlite3.Connection, broj: str) -> dict | None:
    return _narudzba(veza.execute("SELECT * FROM narudzbe WHERE broj = ?", (broj,)).fetchone())


def postoji_narudzba(veza: sqlite3.Connection, broj: str, email: str) -> bool:
    red = veza.execute(
        "SELECT 1 FROM narudzbe WHERE broj = ? AND lower(email) = lower(?)", (broj, email)
    ).fetchone()
    return red is not None


def upisi_odustanak(veza: sqlite3.Connection, podaci: dict) -> int:
    with veza:
        kursor = veza.execute(
            f"INSERT INTO odustanci ({', '.join(STUPCI_ODUSTANKA)}) "
            f"VALUES ({', '.join('?' * len(STUPCI_ODUSTANKA))})",
            tuple(podaci.get(stupac) for stupac in STUPCI_ODUSTANKA),
        )
    return kursor.lastrowid


def odustanak(veza: sqlite3.Connection, id_: int) -> dict | None:
    red = veza.execute("SELECT * FROM odustanci WHERE id = ?", (id_,)).fetchone()
    return dict(red) if red else None


def oznaci_mail(veza: sqlite3.Connection, tablica: str, id_: int, stupac: str) -> None:
    if tablica not in TABLICE or stupac not in STUPCI_MAILA:
        raise ValueError(f"nepoznat stupac {tablica}.{stupac}")
    with veza:
        veza.execute(f"UPDATE {tablica} SET {stupac} = datetime('now') WHERE id = ?", (id_,))


def neposlani(veza: sqlite3.Connection, tablica: str) -> list[sqlite3.Row]:
    """Zapisi s barem jednim neposlanim mailom, stariji od 2 minute, a mlađi od 7 dana.

    Dvije minute ostavljaju vremena zahtjevu koji upravo šalje, da isti mail ne ode dvaput.
    """
    if tablica not in TABLICE:
        raise ValueError(f"nepoznata tablica {tablica}")
    return veza.execute(
        f"SELECT * FROM {tablica} WHERE (mail_trgovini IS NULL OR mail_kupcu IS NULL) "
        "AND stvoreno <= datetime('now', '-2 minutes') AND stvoreno >= datetime('now', '-7 days') "
        "ORDER BY id"
    ).fetchall()


def zahtjeva_s_ip(veza: sqlite3.Connection, tablica: str, ip: str) -> int:
    if tablica not in TABLICE:
        raise ValueError(f"nepoznata tablica {tablica}")
    return veza.execute(
        f"SELECT COUNT(*) FROM {tablica} WHERE ip = ? AND stvoreno >= datetime('now', '-1 hour')",
        (ip,),
    ).fetchone()[0]


def upisi_boxnow(veza: sqlite3.Connection, broj: str, paket: str) -> None:
    with veza:
        veza.execute(
            "UPDATE narudzbe SET boxnow_paket = ?, boxnow_stvoreno = datetime('now') "
            "WHERE broj = ? AND boxnow_paket IS NULL",
            (paket, broj),
        )
