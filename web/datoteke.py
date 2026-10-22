"""Pisanje u dist/: kopija static/ i wholesale/, hash u imenu, robots, _headers, sitemap."""

import hashlib
import json
import shutil
from pathlib import Path
from xml.sax.saxutils import escape

# Datoteke s hashom u imenu nikad se ne mijenjaju, pa smiju u cache zauvijek. Font treba
# CORS jer ga učitavaju i stranice backenda s api.terpenstation.com.
ZAGLAVLJA = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin

/slike/r/*
  Cache-Control: public, max-age=31536000, immutable

/css/*
  Cache-Control: public, max-age=31536000, immutable

/js/*
  Cache-Control: public, max-age=31536000, immutable

/font/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/*proizvodi.json
  Cache-Control: public, max-age=60

/admin/*
  Cache-Control: no-store
  X-Robots-Tag: noindex
"""


def pripremi(izlaz: Path, korijen: Path) -> None:
    if izlaz.exists():
        shutil.rmtree(izlaz)
    shutil.copytree(korijen / "static", izlaz)
    shutil.copytree(korijen / "wholesale", izlaz / "wholesale")


def s_hashom(izlaz: Path, relativni: str) -> str:
    """Preimenuje datoteku tako da ime nosi hash sadržaja; vraća novi URL."""
    izvor = izlaz / relativni
    sazetak = hashlib.sha256(izvor.read_bytes()).hexdigest()[:10]
    novo = izvor.rename(izvor.with_name(f"{izvor.stem}.{sazetak}{izvor.suffix}"))
    return "/" + novo.relative_to(izlaz).as_posix()


def pisi(izlaz: Path, put: str, sadrzaj: str) -> None:
    """URL put u datoteku: "/kosarica/" → kosarica/index.html, "/404.html" ostaje isti."""
    relativni = put.lstrip("/")
    if not relativni or relativni.endswith("/"):
        relativni += "index.html"
    cilj = izlaz / relativni
    cilj.parent.mkdir(parents=True, exist_ok=True)
    cilj.write_text(sadrzaj, encoding="utf-8")


def pisi_json(izlaz: Path, put: str, podaci: dict) -> None:
    pisi(izlaz, put, json.dumps(podaci, ensure_ascii=False, separators=(",", ":")))


def pisi_sitemap(izlaz: Path, put: str, urlovi: list[str]) -> None:
    retci = "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urlovi)
    pisi(
        izlaz,
        put,
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{retci}</urlset>\n',
    )


def pisi_robots(izlaz: Path, adresa: str, putevi_drzava: list[str]) -> None:
    sitemapi = "".join(f"Sitemap: {adresa}{put}sitemap.xml\n" for put in putevi_drzava)
    pisi(izlaz, "/robots.txt", f"User-agent: *\nDisallow: /admin/\n\n{sitemapi}")


def pisi_zaglavlja(izlaz: Path) -> None:
    pisi(izlaz, "/_headers", ZAGLAVLJA)
