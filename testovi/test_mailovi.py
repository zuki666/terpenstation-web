from conftest import obrazac

from backend import baza


def test_neposlani_mail_ponovi_timer_i_ne_salje_dvaput(klijent, okolina):
    posta = okolina.slanje.posta
    posta.pokvarena = True
    klijent.post("/narudzba", data=obrazac())
    klijent.post(
        "/odustanak",
        data={
            "broj": "2026-0001",
            "email": "ivana@example.com",
            "ime": "Ivana",
            "drzava": "hr",
            "web": "",
        },
    )
    assert posta.poslano == []

    posta.pokvarena = False
    with baza.povezi(okolina.baza) as veza:
        # Timer ne dira svježe zapise, da ne pošalje isto što upravo šalje zahtjev.
        assert okolina.slanje.posalji_neposlane(veza, okolina.drzave) == 0
        for tablica in ("narudzbe", "odustanci"):
            veza.execute(f"UPDATE {tablica} SET stvoreno = datetime('now', '-11 minutes')")
        veza.commit()
        assert okolina.slanje.posalji_neposlane(veza, okolina.drzave) == 2
        assert len(posta.poslano) == 4
        assert okolina.slanje.posalji_neposlane(veza, okolina.drzave) == 0
    assert len(posta.poslano) == 4


def test_djelomicno_poslano_salje_samo_ono_sto_fali(klijent, okolina):
    klijent.post("/narudzba", data=obrazac())
    posta = okolina.slanje.posta
    with baza.povezi(okolina.baza) as veza:
        veza.execute("UPDATE narudzbe SET mail_kupcu = NULL, stvoreno = datetime('now', '-1 hour')")
        veza.commit()
        posta.poslano.clear()
        okolina.slanje.posalji_neposlane(veza, okolina.drzave)
    assert [poruka["To"] for poruka in posta.poslano] == ["ivana@example.com"]
