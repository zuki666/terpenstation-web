"""python -m backend migriraj | mailovi | posluzi"""

import argparse
import logging
import sys
from contextlib import closing

from backend import baza
from backend.postavke import putanja_baze
from web.postavke import PostavkeGreska


def _migriraj() -> int:
    with closing(baza.povezi(putanja_baze())) as veza:
        nove = baza.migriraj(veza)
    logging.info("baza %s: verzija %s", putanja_baze(), nove[-1] if nove else "bez promjene")
    return 0


def _mailovi() -> int:
    from backend.okolina import iz_postavki

    okolina = iz_postavki()
    with closing(baza.povezi(okolina.baza)) as veza:
        baza.provjeri_verziju(veza)
        pokusano = okolina.slanje.posalji_neposlane(veza, okolina.drzave)
    logging.info("neposlani mailovi: %d zapisa pokušano", pokusano)
    return 0


def _posluzi(port: int) -> int:
    from backend.aplikacija import stvori

    stvori().run(host="127.0.0.1", port=port)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m backend")
    naredbe = parser.add_subparsers(dest="naredba", required=True)
    naredbe.add_parser("migriraj", help="napravi ili nadogradi bazu")
    naredbe.add_parser("mailovi", help="ponovi neposlane mailove (timer svakih 10 min)")
    naredba_posluzi = naredbe.add_parser("posluzi", help="lokalni backend za probu")
    naredba_posluzi.add_argument("--port", type=int, default=8090)
    argumenti = parser.parse_args()
    # Izlaz 2: tajna koja fali ili nemigrirana baza; ponovno pokretanje to ne popravi.
    try:
        if argumenti.naredba == "migriraj":
            return _migriraj()
        if argumenti.naredba == "mailovi":
            return _mailovi()
        return _posluzi(argumenti.port)
    except (PostavkeGreska, baza.ZastarjelaBaza) as greska:
        logging.error("%s", greska)
        return 2


if __name__ == "__main__":
    sys.exit(main())
