"""Oznake u <head>: naslov, opis, kanonski link, hreflang, pregled linka i JSON-LD."""

from web.slike import PREGLED


def prazna(naslov: str) -> dict:
    """Stranice backenda: bez indeksa, kanonskog linka i pregleda."""
    return {
        "naslov": naslov,
        "opis": "",
        "bez_indeksa": True,
        "kanonski": "",
        "alternativni": [],
        "og_tip": "website",
        "og_slika": "",
        "og_velicina": PREGLED,
        "json_ld": [],
        "aktivna": "",
    }


def za_stranicu(stranica: object, plan: object, planovi: list, adresa: str) -> dict:
    """Oznake jedne izgrađene stranice; stranica bez indeksa nema kanonski link ni hreflang."""
    indeks = stranica.indeks
    return {
        **prazna(stranica.naslov),
        "opis": stranica.opis or plan.jezik["naslovna"]["opis"],
        "bez_indeksa": not indeks,
        "kanonski": f"{adresa}{stranica.put}" if indeks else "",
        "alternativni": alternative(stranica, planovi, adresa) if indeks else [],
        "og_tip": "product" if stranica.kljuc[0] == "proizvod" else "website",
        "og_slika": f"{adresa}{stranica.og_slika}" if stranica.og_slika else "",
        "json_ld": stranica.json_ld,
        "aktivna": stranica.aktivna,
    }


def alternative(stranica: object, planovi: list, adresa: str) -> list[dict]:
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
