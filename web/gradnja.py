"""python -m web gradi: sve države, njihove stranice, proizvodi.json i sitemap u dist/."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from web import datoteke, meta, stranice, stranice_dnevnika, strukturirani
from web.postavke import KORIJEN, ucitaj_drzave, ucitaj_jezik, ucitaj_postavke
from web.predlosci import (
    cijene_po_gramu,
    izbornik_drzava,
    kontekst,
    okruzenje,
    podaci_blagajne,
    put_stranice,
    veze_kategorija,
)
from web.proizvodi import Proizvod, javni_proizvod, ucitaj_sirove, za_jezik
from web.slike import Slike
from web.stranica import Stranica

log = logging.getLogger(__name__)


@dataclass
class Drzava:
    """Sve što treba za stranice jedne države."""

    drzava: dict
    jezik: dict
    proizvodi: list[dict]
    stranice: list[Stranica] = field(default_factory=list)
    zapisi: list[dict] = field(default_factory=list)


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
        self.adresa = self.postavke["sajt"]["adresa"]
        self.sirovi_dnevnika: list[tuple[str, dict]] = []

    def gradi(self) -> list[Drzava]:
        datoteke.pripremi(self.izlaz, self.korijen)
        self.resursi = {
            "css": datoteke.s_hashom(self.izlaz, "css/stil.css"),
            "js": datoteke.s_hashom(self.izlaz, "js/kosarica.js"),
        }
        sirovi = ucitaj_sirove(self.korijen / "sadrzaj" / "proizvodi")
        self.sirovi_dnevnika = ucitaj_sirove(self.korijen / "sadrzaj" / "dnevnik", "zapis")
        planovi = [self._planiraj(drzava, sirovi) for drzava in self.drzave]
        for plan in planovi:
            self._iscrtaj(plan, planovi)
        datoteke.pisi_robots(self.izlaz, self.adresa, [d["put"] for d in self.drzave])
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
            "pregled": self.slike.pregled(p.slike[0]) if p.slike else "",
            "najniza_c": min(cijene),
            "vise_cijena": len(set(cijene)) > 1,
            **cijene_po_gramu(p.pakiranja, p.kategorija in self.postavke["trgovina"]["po_gramu"]),
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
        plan.zapisi = stranice_dnevnika.ucitaj(self.sirovi_dnevnika, proizvodi, self._okvir(plan))
        plan.stranice = self._stranice(plan)
        log.info("%s: %d proizvoda, %d stranica", drzava["kod"], len(proizvodi), len(plan.stranice))
        return plan

    def _okvir(self, plan: Drzava) -> stranice_dnevnika.Okvir:
        return stranice_dnevnika.Okvir(
            plan.drzava, plan.jezik, self.postavke, self.slike, self.adresa
        )

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
                {
                    "istaknuti": plan.proizvodi[:istaknutih],
                    "medij": self.slike.obradi,
                    "zapisi": plan.zapisi[: self.postavke["dnevnik"]["na_naslovnoj"]],
                },
                json_ld=[strukturirani.organizacija(drzava, naziv, self.adresa)],
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
        dnevnik_stranice = stranice_dnevnika.stranice(plan.zapisi, self._okvir(plan))
        return popis + self._stranice_proizvoda(plan) + dnevnik_stranice

    def _stranice_proizvoda(self, plan: Drzava) -> list[Stranica]:
        drzava, jezik, t = plan.drzava, plan.jezik, plan.jezik
        naziv = t["opcenito"]["naziv_sajta"]
        popis = []
        for kategorija in self._kategorije(plan):
            proizvodi = [p for p in plan.proizvodi if p["kategorija"] == kategorija]
            url, naslov = (
                put_stranice(drzava, jezik, kategorija),
                t["kategorije_naslov"][kategorija],
            )
            popis.append(
                Stranica(
                    ("kategorija", kategorija),
                    url,
                    "kategorija.html",
                    f"{naslov} · {naziv}",
                    t["kategorije_opis"][kategorija],
                    {
                        "proizvodi": proizvodi,
                        "naziv_kategorije": t["kategorije"][kategorija],
                        "opis_kategorije": t["kategorije_opis"][kategorija],
                    },
                    og_slika=next((p["pregled"] for p in proizvodi if p["pregled"]), ""),
                    aktivna=kategorija,
                    json_ld=[strukturirani.mrvice(drzava, t, self.adresa, [(naslov, url)])],
                )
            )
        po_sorti = stranice_dnevnika.po_sorti(plan.zapisi)
        na_proizvodu = self.postavke["dnevnik"]["na_proizvodu"]
        for p in plan.proizvodi:
            koraci = [(t["kategorije_naslov"][p["kategorija"]], p["url_kategorije"])]
            koraci.append((p["naziv"], p["url"]))
            popis.append(
                Stranica(
                    ("proizvod", p["slug"]),
                    p["url"],
                    "proizvod.html",
                    f"{p['naziv']} · {t['kategorije_naslov'][p['kategorija']]} · {naziv}",
                    p["kratki_opis"] or t["kategorije_opis"][p["kategorija"]],
                    {"p": p, "zapisi": po_sorti.get(p["slug"], [])[:na_proizvodu]},
                    og_slika=p["pregled"],
                    aktivna=p["kategorija"],
                    json_ld=[
                        strukturirani.proizvod(p, drzava, self.adresa),
                        strukturirani.mrvice(drzava, t, self.adresa, koraci),
                    ],
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
            "dnevnik_url": stranice_dnevnika.put_dnevnika(plan.zapisi, self._okvir(plan)),
        }

    def _iscrtaj(self, plan: Drzava, planovi: list[Drzava]) -> None:
        zajednicko = self._zajednicko(plan)
        # Svaka stranica koja se indeksira ima sliku u pregledu linka (Instagram, WhatsApp).
        zadana = self.slike.pregled(self.postavke["trgovina"]["slika_pregleda"])
        for stranica in plan.stranice:
            if stranica.indeks and not stranica.og_slika:
                stranica.og_slika = zadana
            oznake = meta.za_stranicu(stranica, plan, planovi, self.adresa)
            predlozak = self.okruzenje.get_template(stranica.predlozak)
            html = predlozak.render(**zajednicko, **stranica.podaci, stranica=oznake)
            datoteke.pisi(self.izlaz, stranica.put, html)
        self._pisi_katalog(plan)
        urlovi = [f"{self.adresa}{s.put}" for s in plan.stranice if s.indeks]
        if plan.drzava["put"] == "/":
            # Wholesale je kopija gotove stranice, pa ga gradnja ne iscrtava i ne zna za njega.
            urlovi.append(f"{self.adresa}/wholesale/")
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
                # Stranice backenda (zahvala, odustanak) iz ovoga znaju ima li dnevnik u izborniku.
                "dnevnik": stranice_dnevnika.put_dnevnika(plan.zapisi, self._okvir(plan)),
                "proizvodi": proizvodi,
            },
        )


def gradi(izlaz: Path, korijen: Path = KORIJEN) -> list[Drzava]:
    return Gradnja(izlaz, korijen).gradi()
