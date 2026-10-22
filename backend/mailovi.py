"""Mail trgovini i potvrda kupcu; neposlani mail ponavlja timer (stupci mail_* su NULL)."""

import logging
import os
import smtplib
import sqlite3
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from backend import baza, hub3
from backend.iscrtavanje import Iscrtavac
from web.postavke import drzava_po_kodu

log = logging.getLogger(__name__)

TIMEOUT_S = 20
LOKALNI = frozenset({"localhost", "127.0.0.1"})


@dataclass
class Posta:
    posluzitelj: str
    port: int
    korisnik: str
    lozinka: str

    def posalji(self, poruka: EmailMessage) -> None:
        with smtplib.SMTP(self.posluzitelj, self.port, timeout=TIMEOUT_S) as veza:
            # Lokalni hvatač mailova za probu nema TLS ni prijavu.
            if self.posluzitelj not in LOKALNI:
                veza.starttls(context=ssl.create_default_context())
                veza.login(self.korisnik, self.lozinka)
            veza.send_message(poruka)


def posta_iz_postavki(postavke: dict, lozinka: str) -> Posta:
    mail = postavke["mail"]
    # SMTP_POSLUZITELJ=127.0.0.1:1025 šalje u lokalni hvatač umjesto na Gmail.
    posluzitelj, _, port = (os.environ.get("SMTP_POSLUZITELJ") or "").partition(":")
    return Posta(
        posluzitelj or mail["smtp_posluzitelj"],
        int(port or mail["smtp_port"]),
        mail["smtp_korisnik"],
        lozinka,
    )


@dataclass
class Slanje:
    """Sve što treba za slanje: postavke, iscrtavač, pošta i adresa linka za BOX NOW."""

    postavke: dict
    iscrtavac: Iscrtavac
    posta: Posta
    link_boxnow: object

    def _poruka(self, predmet: str, prima: str, odgovori: str) -> EmailMessage:
        poruka = EmailMessage()
        poruka["Subject"] = predmet
        poruka["From"] = self.postavke["mail"]["posiljatelj"]
        poruka["To"] = prima
        poruka["Reply-To"] = odgovori
        poruka["Date"] = formatdate(localtime=True)
        poruka["Message-ID"] = make_msgid(domain=self.postavke["mail"]["trgovina"].split("@")[-1])
        return poruka

    def narudzba_trgovini(self, n: dict, drzava: dict) -> EmailMessage:
        t = self.iscrtavac.jezik(drzava)
        novac = self.iscrtavac.novac(n["ukupno_c"], drzava)
        predmet = t["mail_trgovini"]["predmet"].format(
            broj=n["broj"],
            dostava=t["dostave"][n["dostava"]],
            placanje=t["placanja"][n["placanje"]],
            ukupno=novac,
        )
        poruka = self._poruka(predmet, self.postavke["mail"]["trgovina"], n["email"])
        poruka.set_content(
            self.iscrtavac.tekst(
                "mail/trgovini.txt",
                drzava,
                {
                    "n": n,
                    "boxnow_link": self.link_boxnow(n["broj"]),
                    "vrijeme": self.iscrtavac.vrijeme(n["stvoreno"], drzava),
                },
            )
        )
        return poruka

    def narudzba_kupcu(self, n: dict, drzava: dict) -> EmailMessage:
        t = self.iscrtavac.jezik(drzava)
        predmet = t["mail_kupcu"]["predmet"].format(broj=n["broj"])
        poruka = self._poruka(predmet, n["email"], self.postavke["mail"]["trgovina"])
        cid = make_msgid(domain="terpenstation.com")[1:-1]
        podaci = {
            "n": n,
            "predmet": predmet,
            "cid_barkoda": cid,
            "uplata": self.iscrtavac.uplata(n, drzava),
            "dostava": self.iscrtavac.opis_dostave(n, drzava),
        }
        poruka.set_content(self.iscrtavac.tekst("mail/kupcu.txt", drzava, podaci))
        poruka.add_alternative(
            self.iscrtavac.tekst("mail/kupcu.html", drzava, podaci), subtype="html"
        )
        if n["placanje"] == "uplata":
            barkod = hub3.png(hub3.niz(n, drzava["primatelj"], podaci["uplata"]["opis"]))
            poruka.get_payload()[1].add_related(barkod, "image", "png", cid=f"<{cid}>")
        return poruka

    def odustanak_trgovini(self, o: dict, drzava: dict, postoji: bool) -> EmailMessage:
        t = self.iscrtavac.jezik(drzava)
        predmet = t["mail_odustanak"]["predmet_trgovini"].format(broj=o["broj"])
        poruka = self._poruka(predmet, self.postavke["mail"]["trgovina"], o["email"])
        poruka.set_content(
            self.iscrtavac.tekst(
                "mail/odustanak_trgovini.txt",
                drzava,
                {
                    "o": o,
                    "narudzba_postoji": postoji,
                    "vrijeme": self.iscrtavac.vrijeme(o["stvoreno"], drzava),
                },
            )
        )
        return poruka

    def odustanak_kupcu(self, o: dict, drzava: dict) -> EmailMessage:
        t = self.iscrtavac.jezik(drzava)
        predmet = t["mail_odustanak"]["predmet_kupcu"].format(broj=o["broj"])
        poruka = self._poruka(predmet, o["email"], self.postavke["mail"]["trgovina"])
        poruka.set_content(
            self.iscrtavac.tekst(
                "mail/odustanak_kupcu.txt",
                drzava,
                {
                    "o": o,
                    "vrijeme": self.iscrtavac.vrijeme(o["stvoreno"], drzava),
                },
            )
        )
        return poruka

    def _posalji(
        self, veza: sqlite3.Connection, oznaka: tuple[str, int, str], poruka: object
    ) -> bool:
        tablica, id_, stupac = oznaka
        try:
            self.posta.posalji(poruka() if callable(poruka) else poruka)
        except (smtplib.SMTPException, OSError) as greska:
            log.warning("%s %d: %s nije poslan (%s)", tablica, id_, stupac, greska)
            return False
        baza.oznaci_mail(veza, tablica, id_, stupac)
        log.info("%s %d: %s poslan", tablica, id_, stupac)
        return True

    def posalji_narudzbu(self, veza: sqlite3.Connection, n: dict, drzava: dict) -> None:
        if not n["mail_trgovini"]:
            self._posalji(
                veza,
                ("narudzbe", n["id"], "mail_trgovini"),
                lambda: self.narudzba_trgovini(n, drzava),
            )
        if not n["mail_kupcu"]:
            self._posalji(
                veza, ("narudzbe", n["id"], "mail_kupcu"), lambda: self.narudzba_kupcu(n, drzava)
            )

    def posalji_odustanak(self, veza: sqlite3.Connection, o: dict, drzava: dict) -> None:
        if not o["mail_trgovini"]:
            postoji = baza.postoji_narudzba(veza, o["broj"], o["email"])
            self._posalji(
                veza,
                ("odustanci", o["id"], "mail_trgovini"),
                lambda: self.odustanak_trgovini(o, drzava, postoji),
            )
        if not o["mail_kupcu"]:
            self._posalji(
                veza, ("odustanci", o["id"], "mail_kupcu"), lambda: self.odustanak_kupcu(o, drzava)
            )

    def posalji_neposlane(self, veza: sqlite3.Connection, drzave: list[dict]) -> int:
        """Za timer: ponovi svaki neposlani mail; vraća broj zapisa koje je pokušao."""
        pokusano = 0
        for red in baza.neposlani(veza, "narudzbe"):
            n = baza.narudzba(veza, red["broj"])
            drzava = drzava_po_kodu(drzave, n["drzava"])
            if drzava:
                self.posalji_narudzbu(veza, n, drzava)
                pokusano += 1
        for red in baza.neposlani(veza, "odustanci"):
            drzava = drzava_po_kodu(drzave, red["drzava"])
            if drzava:
                self.posalji_odustanak(veza, dict(red), drzava)
                pokusano += 1
        return pokusano
