"""HUB-3 2D barkod za uplatu, po HUB-ovoj uputi za EUR."""

import io
import math
import unicodedata

from pdf417gen import encoding, render_image
from pdf417gen.compaction import BYTE_LATCH, BYTE_LATCH_ALT, compact_bytes
from pdf417gen.error_correction import compute_error_correction_code_words
from pdf417gen.util import chunks

ZAGLAVLJE = "HRVHUB30"
HRVATSKA_SLOVA = frozenset("ČčĆćĐđŠšŽž")
ZNAKOVI = frozenset(" ,.:-+?'/()")
STUPACA = 9
RAZINA_ZASTITE = 4


def _dopusten(znak: str) -> bool:
    return (znak.isascii() and znak.isalnum()) or znak in HRVATSKA_SLOVA or znak in ZNAKOVI


def ocisti(tekst: str, najvise: int) -> str:
    """Samo znakovi koje HUB dopušta, skraćeno na najveći broj znakova (ne bajtova).

    Ostala slova s kvačicama gube kvačicu (Müller → Muller) umjesto da nestanu.
    """
    znakovi = []
    for znak in tekst:
        if znak.isspace():
            znak = " "
        elif not _dopusten(znak):
            znak = unicodedata.normalize("NFKD", znak)[0]
        if _dopusten(znak):
            znakovi.append(znak)
    return " ".join("".join(znakovi).split())[:najvise].strip()


def niz(narudzba: dict, primatelj: dict, opis: str) -> str:
    """Podaci barkoda; svako polje završava znakom LF, i zadnje (HUB, primjer u uputi)."""
    na_adresu = narudzba["dostava"] != "boxnow"
    ulica = (narudzba.get("ulica") or "") if na_adresu else ""
    mjesto = f"{narudzba.get('postanski_broj') or ''} {narudzba.get('mjesto') or ''}"
    mjesto = mjesto if na_adresu else ""
    polja = [
        ZAGLAVLJE,
        "EUR",
        f"{narudzba['ukupno_c']:015d}",
        ocisti(narudzba["ime"], 30),
        ocisti(ulica, 27),
        ocisti(mjesto, 27),
        ocisti(primatelj["naziv"], 25),
        ocisti(primatelj["ulica"], 25),
        ocisti(primatelj["mjesto"], 27),
        "".join(primatelj["iban"].split()).upper()[:21],
        primatelj["model"][:4],
        ocisti(narudzba["broj"], 22),
        primatelj["sifra_namjene"][:4],
        ocisti(opis, 35),
    ]
    return "".join(f"{polje}\n" for polje in polja)


def kodne_rijeci(podaci: bytes) -> list[int]:
    """Podatkovne i zaštitne kodne riječi PDF417, samo u binarnom načinu, kako HUB traži.

    pdf417gen.encode sam bira način (tekst, brojevi, bajtovi), pa se ovdje slaže isto što i on,
    ali samo s byte compaction.
    """
    latch = BYTE_LATCH_ALT if len(podaci) % 6 == 0 else BYTE_LATCH
    rijeci = [latch, *compact_bytes(podaci)]
    broj_zastitnih = 2 ** (RAZINA_ZASTITE + 1)
    dopuna = encoding.get_padding(len(rijeci), broj_zastitnih, STUPACA)
    opisnik = len(rijeci) + len(dopuna) + 1
    encoding.validate_barcode_size(opisnik, math.ceil((opisnik + broj_zastitnih) / STUPACA))
    podatkovne = [opisnik, *rijeci, *dopuna]
    return podatkovne + compute_error_correction_code_words(podatkovne, RAZINA_ZASTITE)


def png(podaci: str, mjerilo: int = 2) -> bytes:
    rijeci = kodne_rijeci(podaci.encode("utf-8"))
    retci = list(encoding.encode_rows(list(chunks(rijeci, STUPACA)), STUPACA, RAZINA_ZASTITE))
    slika = render_image(retci, scale=mjerilo, ratio=3, padding=8)
    izlaz = io.BytesIO()
    slika.save(izlaz, format="PNG", optimize=True)
    return izlaz.getvalue()
