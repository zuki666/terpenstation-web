CREATE TABLE narudzbe (
    id INTEGER PRIMARY KEY,
    broj TEXT NOT NULL UNIQUE,
    drzava TEXT NOT NULL,
    stvoreno TEXT NOT NULL DEFAULT (datetime('now')),
    ime TEXT NOT NULL,
    email TEXT NOT NULL,
    telefon TEXT NOT NULL,
    dostava TEXT NOT NULL,
    paketomat_id TEXT,
    paketomat_adresa TEXT,
    ulica TEXT,
    postanski_broj TEXT,
    mjesto TEXT,
    placanje TEXT NOT NULL,
    -- Snimka stavki u trenutku narudžbe: id, naziv, oznaka, cijena_c, kolicina, tezina_g.
    stavke TEXT NOT NULL,
    meduzbroj_c INTEGER NOT NULL,
    dostava_c INTEGER NOT NULL,
    naknada_c INTEGER NOT NULL,
    ukupno_c INTEGER NOT NULL,
    pdv_c INTEGER NOT NULL,
    tvrtka TEXT,
    oib TEXT,
    napomena TEXT,
    token TEXT NOT NULL,
    boxnow_paket TEXT,
    boxnow_stvoreno TEXT,
    -- Vrijeme slanja; NULL znači da timer još pokušava.
    mail_trgovini TEXT,
    mail_kupcu TEXT,
    ip TEXT
);

CREATE INDEX narudzbe_ip ON narudzbe (ip, stvoreno);

CREATE TABLE odustanci (
    id INTEGER PRIMARY KEY,
    drzava TEXT NOT NULL,
    broj TEXT NOT NULL,
    email TEXT NOT NULL,
    ime TEXT NOT NULL,
    poruka TEXT,
    stvoreno TEXT NOT NULL DEFAULT (datetime('now')),
    mail_trgovini TEXT,
    mail_kupcu TEXT,
    ip TEXT
);

CREATE INDEX odustanci_ip ON odustanci (ip, stvoreno);
