"""JSON-LD za Google: proizvod s ponudama, zapis dnevnika, mrvice i podaci o trgovini.

Svi proizvodi koji se grade su dostupni (W4), pa je dostupnost uvijek InStock.
"""

SCHEMA = "https://schema.org"


def _cijena(centi: int) -> str:
    return f"{centi // 100}.{centi % 100:02d}"


def mrvice(drzava: dict, jezik: dict, adresa: str, koraci: list[tuple[str, str]]) -> dict:
    """`koraci` su (naziv, put) od naslovne prema stranici; naslovna se dodaje sama."""
    svi = [(jezik["opcenito"]["naziv_sajta"], drzava["put"]), *koraci]
    return {
        "@context": SCHEMA,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": redni, "name": naziv, "item": f"{adresa}{put}"}
            for redni, (naziv, put) in enumerate(svi, start=1)
        ],
    }


def organizacija(drzava: dict, naziv_sajta: str, adresa: str) -> dict:
    firma = drzava["firma"]
    return {
        "@context": SCHEMA,
        "@type": "Organization",
        "name": naziv_sajta,
        "legalName": firma["naziv"],
        "url": f"{adresa}{drzava['put']}",
        "email": firma["email"],
        "telephone": firma["telefon"].replace(" ", ""),
        "address": firma["adresa"],
        "taxID": firma["oib"],
    }


def _dostave(drzava: dict) -> list[dict]:
    return [
        {
            "@type": "OfferShippingDetails",
            "shippingRate": {
                "@type": "MonetaryAmount",
                "value": _cijena(drzava["dostava"][kljuc]["cijena_c"]),
                "currency": drzava["valuta"],
            },
            "shippingDestination": {
                "@type": "DefinedRegion",
                "addressCountry": drzava["kod"].upper(),
            },
        }
        for kljuc in drzava["dostave"]
    ]


def zapis(z: dict, drzava: dict, adresa: str, naziv_sajta: str) -> dict:
    """Zapis dnevnika kao objava na blogu; video samo kad je na sajtu, uz naslovnu sliku."""
    url = f"{adresa}{z['url']}"
    autor = {"@type": "Organization", "name": naziv_sajta, "url": f"{adresa}{drzava['put']}"}
    podaci = {
        "@context": SCHEMA,
        "@type": "BlogPosting",
        "headline": z["naslov"],
        "datePublished": z["datum_iso"],
        "url": url,
        "mainEntityOfPage": url,
        "inLanguage": drzava["jezik"],
        "author": autor,
        "publisher": autor,
    }
    if z["slike"]:
        podaci["image"] = [f"{adresa}{slika.velika}" for slika in z["slike"]]
    if z["kratko"]:
        podaci["description"] = z["kratko"]
    if z["video"] and z["slika"]:
        podaci["video"] = {
            "@type": "VideoObject",
            "name": z["naslov"],
            "description": z["kratko"] or z["naslov"],
            "thumbnailUrl": f"{adresa}{z['slika'].velika}",
            "uploadDate": z["datum_iso"],
            "contentUrl": f"{adresa}{z['video']}",
        }
    return podaci


def proizvod(p: dict, drzava: dict, adresa: str) -> dict:
    url = f"{adresa}{p['url']}"
    dostave = _dostave(drzava)
    podaci = {
        "@context": SCHEMA,
        "@type": "Product",
        "name": p["naziv"],
        "sku": p["slug"],
        "category": p["naziv_kategorije"],
        "url": url,
        "image": [f"{adresa}{slika.velika}" for slika in p["slike"]],
        "offers": [
            {
                "@type": "Offer",
                "name": pakiranje.oznaka,
                "sku": pakiranje.id,
                "price": _cijena(pakiranje.cijena_c),
                "priceCurrency": drzava["valuta"],
                "availability": f"{SCHEMA}/InStock",
                "itemCondition": f"{SCHEMA}/NewCondition",
                "url": url,
                "shippingDetails": dostave,
            }
            for pakiranje in p["pakiranja"]
        ],
    }
    if p["kratki_opis"]:
        podaci["description"] = p["kratki_opis"]
    return podaci
