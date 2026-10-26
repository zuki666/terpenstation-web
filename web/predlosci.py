"""Jinja2 okruženje, oblik iznosa i zajednički kontekst stranica i mailova."""

from functools import partial
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from web.postavke import KORIJEN

SIMBOLI_VALUTA = {"EUR": "€"}


def okruzenje(korijen: Path = KORIJEN) -> Environment:
    # StrictUndefined: tekst koji fali u jezici/*.toml ruši gradnju i test, ne prazni stranicu.
    return Environment(
        loader=FileSystemLoader(korijen / "predlosci"),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def iznos(centi: int, oblik: dict, valuta: str) -> str:
    cijeli, ostatak = divmod(abs(centi), 100)
    grupe = f"{cijeli:,}".replace(",", oblik["razdjelnik_tisuca"])
    predznak = "-" if centi < 0 else ""
    broj = f"{predznak}{grupe}{oblik['decimalni_znak']}{ostatak:02d}"
    return oblik["uzorak_iznosa"].format(iznos=broj, simbol=SIMBOLI_VALUTA.get(valuta, valuta))


def put_stranice(drzava: dict, jezik: dict, kljuc: str, slug: str = "") -> str:
    """Put stranice unutar države; dijelovi URL-a dolaze iz jezika (`[url]`)."""
    if kljuc == "naslovna":
        return drzava["put"]
    put = f"{drzava['put']}{jezik['url'][kljuc]}/"
    return f"{put}{slug}/" if slug else put


def veze_kategorija(drzava: dict, jezik: dict, kljucevi: list[str]) -> list[dict]:
    """Kategorije za izbornik; `peron` je redni broj, kao broj perona na kolodvoru."""
    return [
        {
            "kljuc": kljuc,
            "naziv": jezik["kategorije"][kljuc],
            "url": put_stranice(drzava, jezik, kljuc),
            "peron": redni,
        }
        for redni, kljuc in enumerate(kljucevi, start=1)
    ]


def cijene_po_gramu(pakiranja: tuple, na_tezinu: bool) -> dict:
    """Cijena po gramu svakog pakiranja s težinom, za usporedbu pakiranja i sorti.

    Samo za proizvode koji se prodaju na težinu: grinder ima težinu za dostavu, ali cijena
    po gramu za njega nema smisla.
    """
    po_gramu = {
        pakiranje.id: round(pakiranje.cijena_c / pakiranje.tezina_g)
        for pakiranje in pakiranja
        if na_tezinu and pakiranje.tezina_g
    }
    return {
        "po_gramu": po_gramu,
        "po_gramu_c": min(po_gramu.values(), default=0),
        "po_gramu_isti": len(set(po_gramu.values())) <= 1,
    }


def najjeftinija_dostava(drzava: dict) -> int:
    return min(drzava["dostava"][kljuc]["cijena_c"] for kljuc in drzava["dostave"])


def izbornik_drzava(drzave: list[dict]) -> list[dict]:
    return [{k: drzava[k] for k in ("kod", "naziv", "jezik", "put")} for drzava in drzave]


def podaci_blagajne(drzava: dict, postavke: dict, stavke: list[dict] | None = None) -> dict:
    """Pravila za pregled iznosa u pregledniku; backend iste iznose računa sam (W14)."""
    pouzece_dopusteno = "pouzece" in drzava["placanja"]
    return {
        "dostave": {
            kljuc: {
                "cijena_c": drzava["dostava"][kljuc]["cijena_c"],
                "pouzece": pouzece_dopusteno and drzava["dostava"][kljuc].get("pouzece", False),
            }
            for kljuc in drzava["dostave"]
        },
        "naknada_pouzeca_c": drzava.get("placanje", {}).get("pouzece", {}).get("naknada_c", 0),
        "besplatna_od_c": drzava.get("besplatna_dostava_od_c", 0),
        "pdv_posto": drzava["pdv_posto"],
        "pozivni": drzava["pozivni_broj"],
        "stavke": stavke,
        "boxnow": {
            "partner_id": postavke["boxnow"]["partner_id"],
            "skripta": postavke["boxnow"]["skripta_widgeta"],
        },
    }


def kontekst(drzava: dict, jezik: dict, postavke: dict, korijen: str = "") -> dict:
    """Varijable koje trebaju svi predlošci; `korijen` je adresa sajta kad iscrtava backend."""
    return {
        "drzava": drzava,
        "t": jezik,
        "firma": drzava["firma"],
        "sajt": postavke["sajt"],
        "korijen": korijen,
        "novac": partial(iznos, oblik=jezik["oblik"], valuta=drzava["valuta"]),
        "put": partial(put_stranice, drzava, jezik),
        "dostava_od_c": najjeftinija_dostava(drzava),
        "besplatna_od_c": drzava.get("besplatna_dostava_od_c", 0),
        "izvori": postavke["trgovina"]["izvori"],
        # Gradnja i backend upišu put dnevnika kad on ima zapise; prazno = nema ga u izborniku.
        "dnevnik_url": "",
        "js_podaci": {
            "tekstovi": jezik["js"],
            "oblik": jezik["oblik"],
            "simbol": SIMBOLI_VALUTA.get(drzava["valuta"], drzava["valuta"]),
        },
    }
