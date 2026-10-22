"""Stranice i mailovi backenda, istim predlošcima i tekstovima kao gradnja."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from web import stranice
from web.postavke import ucitaj_jezik
from web.predlosci import izbornik_drzava, iznos, kontekst, okruzenje, veze_kategorija

ZONA = ZoneInfo("Europe/Zagreb")
SIRINA_BARKODA = 300


def lokalno(utc: str) -> datetime:
    """SQLite datetime('now') je UTC bez zone; prikaz ide po zagrebačkom vremenu."""
    return datetime.fromisoformat(utc).replace(tzinfo=UTC).astimezone(ZONA)


class Iscrtavac:
    def __init__(self, korijen: object, postavke: dict, drzave: list[dict]) -> None:
        self.korijen = korijen
        self.postavke = postavke
        self.drzave = drzave
        self.okruzenje = okruzenje(korijen)
        self.jezici = {d["jezik"]: ucitaj_jezik(d["jezik"], korijen) for d in drzave}
        self.tekstovi = {
            d["kod"]: stranice.ucitaj(korijen / "sadrzaj" / "stranice" / d["kod"]) for d in drzave
        }

    def jezik(self, drzava: dict) -> dict:
        return self.jezici[drzava["jezik"]]

    def _kontekst(self, drzava: dict, katalog: dict | None) -> dict:
        jezik = self.jezik(drzava)
        adresa = self.postavke["sajt"]["adresa"]
        katalog = katalog or {}
        kljucevi = self.postavke["trgovina"]["pravne_stranice"]
        return {
            **kontekst(drzava, jezik, self.postavke, korijen=adresa),
            "adresa": adresa,
            "datoteke": katalog.get("datoteke")
            or {"css": "/css/stil.css", "js": "/js/kosarica.js"},
            "kategorije": veze_kategorija(drzava, jezik, katalog.get("kategorije", [])),
            "pravne": stranice.pravne_veze(drzava, jezik, kljucevi, self.tekstovi[drzava["kod"]]),
            "drzave": izbornik_drzava(self.drzave),
        }

    def stranica(self, predlozak: str, drzava: dict, katalog: dict | None, podaci: dict) -> str:
        """`podaci` mora imati `naslov`; ostalo ide predlošku kako jest."""
        osnova = self._kontekst(drzava, katalog)
        meta = {
            "naslov": f"{podaci['naslov']} · {osnova['t']['opcenito']['naziv_sajta']}",
            "opis": "",
            "bez_indeksa": True,
            "kanonski": "",
            "alternativni": [],
            "og_tip": "website",
            "og_slika": "",
            "aktivna": "",
        }
        return self.okruzenje.get_template(predlozak).render(**osnova, **podaci, stranica=meta)

    def tekst(self, predlozak: str, drzava: dict, podaci: dict) -> str:
        return self.okruzenje.get_template(predlozak).render(
            **self._kontekst(drzava, None), **podaci
        )

    def uplata(self, narudzba: dict, drzava: dict) -> dict:
        """Podaci za uplatu: hvala stranica, mail i HUB-3 ih prikazuju isto."""
        jezik = self.jezik(drzava)
        primatelj = drzava["primatelj"]
        rok = lokalno(narudzba["stvoreno"]) + timedelta(days=drzava["rok_uplate_dana"])
        iban = "".join(primatelj["iban"].split())
        return {
            "primatelj": f"{primatelj['naziv']}, {primatelj['ulica']}, {primatelj['mjesto']}",
            "iban": " ".join(iban[i : i + 4] for i in range(0, len(iban), 4)),
            "model": primatelj["model"],
            "opis": jezik["hvala"]["opis_vrijednost"].format(broj=narudzba["broj"]),
            "rok": rok.strftime(jezik["oblik"]["datum"]),
            "sirina_barkoda": SIRINA_BARKODA,
        }

    def novac(self, centi: int, drzava: dict) -> str:
        return iznos(centi, self.jezik(drzava)["oblik"], drzava["valuta"])

    def opis_dostave(self, n: dict, drzava: dict) -> str:
        naziv = self.jezik(drzava)["dostave"][n["dostava"]]
        if n["dostava"] == "boxnow":
            return f"{naziv}: {n['paketomat_adresa'] or n['paketomat_id']}"
        return f"{naziv}: {n['ulica']}, {n['postanski_broj']} {n['mjesto']}"

    def vrijeme(self, utc: str, drzava: dict) -> str:
        return lokalno(utc).strftime(self.jezik(drzava)["oblik"]["datum_vrijeme"])
