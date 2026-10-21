import copy

from backend.iznosi import izracunaj, pdv_u_iznosu
from web.postavke import ucitaj_drzave

HR = ucitaj_drzave()[0]
STAVKE = [{"cijena_c": 2700, "kolicina": 2}, {"cijena_c": 150, "kolicina": 1}]


def test_uplata_bez_naknade():
    i = izracunaj(STAVKE, HR, "gls", "uplata")
    assert i.meduzbroj_c == 5550
    assert i.dostava_c == HR["dostava"]["gls"]["cijena_c"]
    assert i.naknada_c == 0
    assert i.ukupno_c == 5550 + i.dostava_c


def test_pouzece_dodaje_naknadu():
    i = izracunaj(STAVKE, HR, "boxnow", "pouzece")
    naknada = HR["placanje"]["pouzece"]["naknada_c"]
    assert i.naknada_c == naknada
    assert i.ukupno_c == 5550 + HR["dostava"]["boxnow"]["cijena_c"] + naknada


def test_besplatna_dostava_od_praga():
    drzava = copy.deepcopy(HR)
    drzava["besplatna_dostava_od_c"] = 5550
    assert izracunaj(STAVKE, drzava, "gls", "uplata").dostava_c == 0
    drzava["besplatna_dostava_od_c"] = 5551
    assert izracunaj(STAVKE, drzava, "gls", "uplata").dostava_c > 0


def test_nula_znaci_bez_besplatne_dostave():
    drzava = copy.deepcopy(HR)
    drzava["besplatna_dostava_od_c"] = 0
    assert (
        izracunaj(STAVKE, drzava, "gls", "uplata").dostava_c == drzava["dostava"]["gls"]["cijena_c"]
    )


def test_pdv_u_iznosu():
    assert pdv_u_iznosu(6040, 25) == 1208
    assert pdv_u_iznosu(125, 25) == 25
    # 0,05 € s 25 % PDV-a je točno pola centa; zaokružuje se gore, kao Math.round u pregledniku.
    assert pdv_u_iznosu(5, 25) == 1
    assert pdv_u_iznosu(0, 25) == 0
