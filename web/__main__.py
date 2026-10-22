"""python -m web gradi | posluzi"""

import argparse
import functools
import logging
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from web.gradnja import gradi
from web.postavke import KORIJEN, PostavkeGreska


class Pregled(SimpleHTTPRequestHandler):
    """Lokalni pregled kao na Cloudflare Pagesu: nepostojeći put dobije 404.html."""

    def end_headers(self) -> None:
        # Kao _headers na Pagesu: stranice lokalnog backenda učitavaju font s ovog porta.
        if self.path.startswith("/font/"):
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        stranica = Path(self.directory) / "404.html"
        if code != HTTPStatus.NOT_FOUND or not stranica.exists():
            super().send_error(code, message, explain)
            return
        sadrzaj = stranica.read_bytes()
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(sadrzaj)))
        self.end_headers()
        self.wfile.write(sadrzaj)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="python -m web")
    naredbe = parser.add_subparsers(dest="naredba", required=True)
    naredba_gradi = naredbe.add_parser("gradi", help="složi statični sajt u dist/")
    naredba_gradi.add_argument("--izlaz", type=Path, default=KORIJEN / "dist")
    naredba_posluzi = naredbe.add_parser("posluzi", help="lokalni pregled dist/")
    naredba_posluzi.add_argument("--port", type=int, default=8000)
    naredba_posluzi.add_argument("--mapa", type=Path, default=KORIJEN / "dist")
    argumenti = parser.parse_args()

    if argumenti.naredba == "gradi":
        try:
            gradi(argumenti.izlaz)
        except PostavkeGreska as greska:
            logging.error("%s", greska)
            return 2
        return 0
    rukovatelj = functools.partial(Pregled, directory=str(argumenti.mapa))
    posluzitelj = ThreadingHTTPServer(("127.0.0.1", argumenti.port), rukovatelj)
    logging.info("pregled na http://localhost:%d (Ctrl+C za kraj)", argumenti.port)
    try:
        posluzitelj.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
