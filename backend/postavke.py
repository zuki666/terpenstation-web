"""Tajne iz okoline ili .env i putanje backenda."""

import os
from pathlib import Path

from web.postavke import KORIJEN, PostavkeGreska

ENV = KORIJEN / ".env"
TAJNE = ("SMTP_LOZINKA", "TAJNA_LINKOVA")
TAJNE_BOXNOW = ("BOXNOW_API_URL", "BOXNOW_CLIENT_ID", "BOXNOW_CLIENT_SECRET")


def procitaj_env(putanja: Path) -> dict[str, str]:
    if not putanja.exists():
        return {}
    parovi = {}
    for redak in putanja.read_text(encoding="utf-8").splitlines():
        cist = redak.strip()
        if not cist or cist.startswith("#") or "=" not in cist:
            continue
        kljuc, _, desno = cist.partition("=")
        parovi[kljuc.strip()] = desno.strip().strip("\"'")
    return parovi


def citaj(kljucevi: tuple[str, ...], env_putanja: Path = ENV) -> dict[str, str]:
    """Okolina ima prednost pred .env, da systemd EnvironmentFile i ručni export rade isto."""
    iz_datoteke = procitaj_env(env_putanja)
    return {kljuc: os.environ.get(kljuc) or iz_datoteke.get(kljuc, "") for kljuc in kljucevi}


def tajne(potrebne: tuple[str, ...], env_putanja: Path = ENV) -> dict[str, str]:
    """Vrati tražene tajne ili javi sve koje fale odjednom."""
    nadene = citaj(potrebne, env_putanja)
    nedostaju = [kljuc for kljuc, tajna in nadene.items() if not tajna]
    if nedostaju:
        raise PostavkeGreska(f"nedostaju tajne u .env: {', '.join(nedostaju)}")
    return nadene


def putanja_baze() -> Path:
    return Path(os.environ.get("TRGOVINA_BAZA") or KORIJEN / "trgovina.db")


def mapa_cachea() -> Path:
    return Path(os.environ.get("TRGOVINA_CACHE") or KORIJEN / "cache")
