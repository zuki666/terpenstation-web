"""python -m web gradi: sve države, njihove stranice, proizvodi.json i sitemap u dist/."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from web import datoteke, stranice
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_jezik, ucitaj_postavke
from web.predlosci import (
    izbornik_drzava,
    kontekst,
    okruzenje,
    podaci_blagajne,
    put_stranice,
    veze_kategorija,
)
from web.proizvodi import Proizvod, ucitaj_sirove, za_jezik
from web.slike import Slike

log = logging.getLogger(__name__)


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


@dataclass
class Drzava:
    """Sve što treba za stranice jedne države."""

    drzava: dict
    jezik: dict
    proizvodi: list[dict]
    stranice: list[Stranica] = field(default_factory=list)


class Gradnja:
    def __init__(self, izlaz: Path, korijen: Path = KORIJEN) -> None:
        self.izlaz = izlaz
        self.korijen = korijen
        self.postavke = ucitaj_postavke(korijen)
        self.drzave = ucitaj_drzave(korijen)
        self.okruzenje = okruzenje(korijen)
        self.slike = Slike(korijen / "static", izlaz)
        self.verzija = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.resursi: dict[str, str] = {}

    def gradi(self) -> list[Drzava]:
        datoteke.pripremi(self.izlaz, self.korijen)
        self.resursi = {
            "css": datoteke.s_hashom(self.izlaz, "css/stil.css"),
            "js": datoteke.s_hashom(self.izlaz, "js/kosarica.js"),
        }
        sirovi = ucitaj_sirove(self.korijen / "sadrzaj" / "proizvodi")
        planovi = [self._planiraj(drzava, sirovi) for drzava in self.drzave]
        for plan in planovi:
            self._iscrtaj(plan, planovi)
        adresa = self.postavke["sajt"]["adresa"]
        datoteke.pisi_robots(self.izlaz, adresa, [d["put"] for d in self.drzave])
        datoteke.pisi_zaglavlja(self.izlaz)
        return planovi

    def _prikaz(self, p: Proizvod, drzava: dict, jezik: dict) -> dict:
        slike = [s for s in (self.slike.obradi(put) for put in p.slike) if s]
        cijene = [pakiranje.cijena_c for pakiranje in p.pakiranja]
        return {
            **{k: getattr(p, k) for k in ("slug", "naziv", "kratki_opis", "kategorija")},
            **{k: getattr(p, k) for k in ("pakiranja", "cbg", "thc", "sarza", "analiza")},
            "opis_html": stranice.u_html(p.opis) if p.opis else "",
            "url": put_stranice(drzava, jezik, "proizvod", p.slug),
            "url_kategorije": put_stranice(drzava, jezik, p.kategorija),
            "naziv_kategorije": jezik["kategorije"][p.kategorija],
            "slike": slike,
            "slika": slike[0] if slike else None,
            "najniza_c": min(cijene),
            "vise_cijena": len(set(cijene)) > 1,
        }

    def _planiraj(self, drzava: dict, sirovi: list) -> Drzava:
        jezik = ucitaj_jezik(drzava["jezik"], self.korijen)
        trgovina = self.postavke["trgovina"]
        kontekst_proizvoda = {
            "zadani_jezik": trgovina["zadani_jezik"],
            "kategorije": trgovina["kategorije"],
        }
        proizvodi = [
            self._prikaz(p, drzava, jezik)
            for p in za_jezik(sirovi, drzava["jezik"], kontekst_proizvoda)
        ]
        plan = Drzava(drzava, jezik, proizvodi)
        plan.stranice = self._stranice(plan)
        log.info("%s: %d proizvoda, %d stranica", drzava["kod"], len(proizvodi), len(plan.stranice))
        return plan

    def _stranice(self, plan: Drzava) -> list[Stranica]:
        drzava, jezik, t = plan.drzava, plan.jezik, plan.jezik
        put = partial(put_stranice, drzava, jezik)
        tekstovi = stranice.ucitaj(self.korijen / "sadrzaj" / "stranice" / drzava["kod"])
        naziv = t["opcenito"]["naziv_sajta"]
        istaknutih = self.postavke["trgovina"]["istaknutih_na_naslovnoj"]
        popis = [
            Stranica(
                ("naslovna", ""),
                put("naslovna"),
                "naslovna.html",
                t["naslovna"]["naslov_stranice"],
                t["naslovna"]["opis"],
                {"istaknuti": plan.proizvodi[:istaknutih]},
            ),
            Stranica(
                ("kosarica", ""),
                put("kosarica"),
                "kosarica.html",
                f"{t['kosarica']['naslov']} · {naziv}",
                "",
                indeks=False,
            ),
            Stranica(
                ("blagajna", ""),
                put("blagajna"),
                "blagajna.html",
                f"{t['blagajna']['naslov']} · {naziv}",
                "",
                indeks=False,
                podaci={
                    "v": {},
                    "greske": {},
                    "obavijest": None,
                    "boxnow": self.postavke["boxnow"],
                    "blagajna_js": podaci_blagajne(drzava, self.postavke),
                },
            ),
            Stranica(
                ("hvala", ""),
                put("hvala"),
                "hvala_preusmjeri.html",
                f"{t['hvala']['preusmjeravanje']} · {naziv}",
                "",
                indeks=False,
            ),
            Stranica(
                ("odustanak", ""),
                put("odustanak"),
                "odustanak.html",
                f"{t['odustanak']['naslov']} · {naziv}",
                t["odustanak"]["opis"],
                {"tekst_html": tekstovi.get("odustanak", {}).get("html", "")},
            ),
            Stranica(
                ("404", ""),
                f"{drzava['put']}404.html",
                "404.html",
                f"{t['greske']['nije_nadjeno_naslov']} · {naziv}",
                "",
                indeks=False,
            ),
        ]
        for kljuc in self.postavke["trgovina"]["pravne_stranice"]:
            if kljuc in tekstovi:
                popis.append(
                    Stranica(
                        ("stranica", kljuc),
                        put(kljuc),
                        "stranica.html",
                        f"{tekstovi[kljuc]['naslov']} · {naziv}",
                        tekstovi[kljuc]["opis"],
                        {"tekst_html": tekstovi[kljuc]["html"]},
                    )
                )
        return popis + self._stranice_proizvoda(plan)

    def _stranice_proizvoda(self, plan: Drzava) -> list[Stranica]:
        drzava, jezik, t = plan.drzava, plan.jezik, plan.jezik
        naziv = t["opcenito"]["naziv_sajta"]
        adresa = self.postavke["sajt"]["adresa"]
        popis = []
        for kategorija in self._kategorije(plan):
            proizvodi = [p for p in plan.proizvodi if p["kategorija"] == kategorija]
            popis.append(
                Stranica(
                    ("kategorija", kategorija),
                    put_stranice(drzava, jezik, kategorija),
                    "kategorija.html",
                    f"{t['kategorije'][kategorija]} · {naziv}",
                    t["kategorije_opis"][kategorija],
                    {
                        "proizvodi": proizvodi,
                        "naziv_kategorije": t["kategorije"][kategorija],
                        "opis_kategorije": t["kategorije_opis"][kategorija],
                    },
                    aktivna=kategorija,
                )
            )
        for p in plan.proizvodi:
            popis.append(
                Stranica(
                    ("proizvod", p["slug"]),
                    p["url"],
                    "proizvod.html",
                    f"{p['naziv']} · {naziv}",
                    p["kratki_opis"] or t["kategorije_opis"][p["kategorija"]],
                    {"p": p},
                    og_slika=f"{adresa}{p['slika'].velika}" if p["slika"] else "",
                    aktivna=p["kategorija"],
                )
            )
        return popis

    def _kategorije(self, plan: Drzava) -> list[str]:
        prisutne = {p["kategorija"] for p in plan.proizvodi}
        return [k for k in self.postavke["trgovina"]["kategorije"] if k in prisutne]

    def _zajednicko(self, plan: Drzava) -> dict:
        tekstovi = stranice.ucitaj(self.korijen / "sadrzaj" / "stranice" / plan.drzava["kod"])
        kljucevi = self.postavke["trgovina"]["pravne_stranice"]
        return {
            **kontekst(plan.drzava, plan.jezik, self.postavke),
            "datoteke": self.resursi,
            "kategorije": veze_kategorija(plan.drzava, plan.jezik, self._kategorije(plan)),
            "pravne": stranice.pravne_veze(plan.drzava, plan.jezik, kljucevi, tekstovi),
            "drzave": izbornik_drzava(self.drzave),
        }

    def _iscrtaj(self, plan: Drzava, planovi: list[Drzava]) -> None:
        zajednicko = self._zajednicko(plan)
        adresa = self.postavke["sajt"]["adresa"]
        for stranica in plan.stranice:
            meta = {
                "naslov": stranica.naslov,
                "opis": stranica.opis or plan.jezik["naslovna"]["opis"],
                "bez_indeksa": not stranica.indeks,
                "kanonski": f"{adresa}{stranica.put}" if stranica.indeks else "",
                "alternativni": alternative(stranica, planovi, adresa) if stranica.indeks else [],
                "og_tip": "product" if stranica.kljuc[0] == "proizvod" else "website",
                "og_slika": stranica.og_slika,
                "aktivna": stranica.aktivna,
            }
            predlozak = self.okruzenje.get_template(stranica.predlozak)
            html = predlozak.render(**zajednicko, **stranica.podaci, stranica=meta)
            datoteke.pisi(self.izlaz, stranica.put, html)
        self._pisi_katalog(plan)
        urlovi = [f"{adresa}{s.put}" for s in plan.stranice if s.indeks]
        datoteke.pisi_sitemap(self.izlaz, f"{plan.drzava['put']}sitemap.xml", urlovi)

    def _pisi_katalog(self, plan: Drzava) -> None:
        proizvodi = [javni_proizvod(p) for p in plan.proizvodi]
        datoteke.pisi_json(
            self.izlaz,
            f"{plan.drzava['put']}proizvodi.json",
            {
                "verzija": self.verzija,
                "drzava": plan.drzava["kod"],
                "datoteke": self.resursi,
                "kategorije": self._kategorije(plan),
                "proizvodi": proizvodi,
            },
        )


def javni_proizvod(p: dict) -> dict:
    """Proizvod u proizvodi.json: ono što trebaju košarica i backend, bez opisa."""
    return {
        "id": p["slug"],
        **{k: p[k] for k in ("naziv", "url", "kategorija")},
        "slika": p["slika"].mala if p["slika"] else "",
        "pakiranja": [
            {k: getattr(pak, k) for k in ("id", "oznaka", "cijena_c", "tezina_g")}
            for pak in p["pakiranja"]
        ],
    }


def alternative(stranica: Stranica, planovi: list[Drzava], adresa: str) -> list[dict]:
    """hreflang tek kad ima više država; ista stranica se prepoznaje po ključu, ne po URL-u."""
    if len(planovi) <= 1:
        return []
    return [
        {
            "jezik": f"{plan.drzava['jezik']}-{plan.drzava['kod'].upper()}",
            "url": f"{adresa}{druga.put}",
        }
        for plan in planovi
        for druga in plan.stranice
        if druga.kljuc == stranica.kljuc and druga.indeks
    ]


def gradi(izlaz: Path, korijen: Path = KORIJEN) -> list[Drzava]:
    return Gradnja(izlaz, korijen).gradi()
