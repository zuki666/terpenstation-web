"""BOX NOW: potpisani link iz maila trgovini, pošiljka i naljepnica (W19)."""

import hashlib
import hmac
import logging
import time

import httpx

log = logging.getLogger(__name__)

TIMEOUT_S = 20
DULJINA_POTPISA = 32


class BoxNowGreska(Exception):
    def __init__(self, kod: str, poruka: str) -> None:
        super().__init__(f"{kod}: {poruka}")
        self.kod = kod
        self.poruka = poruka


def potpis(broj: str, tajna: str) -> str:
    return hmac.new(tajna.encode(), broj.encode(), hashlib.sha256).hexdigest()[:DULJINA_POTPISA]


def ispravan_potpis(broj: str, dobiveni: str, tajna: str) -> bool:
    return hmac.compare_digest(potpis(broj, tajna), dobiveni)


def _decimalno(centi: int) -> str:
    return f"{centi // 100}.{centi % 100:02d}"


def _tezina_kg(stavke: list[dict]) -> float:
    """Zbroj težina u kg; kad ijedno pakiranje nema težinu, 0 (BOX NOW to prima)."""
    if any(not stavka.get("tezina_g") for stavka in stavke):
        return 0
    return round(sum(stavka["tezina_g"] * stavka["kolicina"] for stavka in stavke) / 1000, 3)


def tijelo_zahtjeva(n: dict, boxnow: dict, velicina_pretinca: int) -> dict:
    pouzece = n["placanje"] == "pouzece"
    ukupno = _decimalno(n["ukupno_c"])
    return {
        "orderNumber": n["broj"],
        "invoiceValue": ukupno,
        "paymentMode": "cod" if pouzece else "prepaid",
        "amountToBeCollected": ukupno if pouzece else "0.00",
        "allowReturn": True,
        "origin": {
            "contactNumber": boxnow["posiljatelj_telefon"],
            "contactEmail": boxnow["posiljatelj_email"],
            "contactName": boxnow["posiljatelj_ime"],
            "locationId": boxnow["skladiste"],
        },
        "destination": {
            "contactNumber": n["telefon"],
            "contactEmail": n["email"],
            "contactName": n["ime"],
            "locationId": n["paketomat_id"],
        },
        "items": [
            {
                "id": n["broj"],
                "name": f"Narudzba {n['broj']}",
                "value": ukupno,
                "weight": _tezina_kg(n["stavke"]),
                "compartmentSize": velicina_pretinca,
            }
        ],
    }


def _greska(odgovor: httpx.Response) -> BoxNowGreska:
    try:
        podaci = odgovor.json()
    except ValueError:
        podaci = {}
    if not isinstance(podaci, dict):
        podaci = {}
    kod = str(podaci.get("code") or podaci.get("errorCode") or f"HTTP {odgovor.status_code}")
    poruka = str(podaci.get("message") or podaci.get("error") or odgovor.text[:300])
    return BoxNowGreska(kod, poruka)


class Klijent:
    def __init__(
        self, adresa: str, pristup: tuple[str, str], http: httpx.Client | None = None
    ) -> None:
        self.adresa = adresa.rstrip("/")
        self.client_id, self.client_secret = pristup
        self.http = http or httpx.Client(timeout=TIMEOUT_S)
        self.token = ""
        self.istek = 0.0

    def _token(self) -> str:
        # Token traje sat vremena (expires_in); novi se traži minutu prije isteka.
        if self.token and time.monotonic() < self.istek - 60:
            return self.token
        odgovor = self.http.post(
            f"{self.adresa}/api/v1/auth-sessions",
            json={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if odgovor.status_code != httpx.codes.OK:
            raise _greska(odgovor)
        podaci = odgovor.json()
        self.token = podaci["access_token"]
        self.istek = time.monotonic() + float(podaci.get("expires_in", 3600))
        return self.token

    def _zaglavlja(self, prihvaca: str = "application/json") -> dict:
        return {"Authorization": f"Bearer {self._token()}", "Accept": prihvaca}

    def posiljka(self, tijelo: dict) -> str:
        """Napravi pošiljku; vraća id paketa za naljepnicu."""
        odgovor = self.http.post(
            f"{self.adresa}/api/v1/delivery-requests", json=tijelo, headers=self._zaglavlja()
        )
        if odgovor.status_code not in (httpx.codes.OK, httpx.codes.CREATED):
            raise _greska(odgovor)
        paketi = odgovor.json().get("parcels") or []
        if not paketi or not paketi[0].get("id"):
            raise BoxNowGreska("bez paketa", odgovor.text[:300])
        log.info("BOX NOW pošiljka %s: paket %s", tijelo["orderNumber"], paketi[0]["id"])
        return str(paketi[0]["id"])

    def naljepnica(self, paket: str) -> bytes:
        odgovor = self.http.get(
            f"{self.adresa}/api/v1/parcels/{paket}/label.pdf",
            headers=self._zaglavlja("application/pdf"),
        )
        if odgovor.status_code != httpx.codes.OK:
            raise _greska(odgovor)
        return odgovor.content
