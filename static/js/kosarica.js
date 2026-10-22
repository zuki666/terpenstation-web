// Košarica, blagajna i BOX NOW widget. Cijene se nikad ne spremaju: uvijek se čitaju iz
// proizvodi.json, a konačan iznos računa backend.
(() => {
  "use strict";

  const MAKS_KOLICINA = 20;
  const MAKS_STAVKI = 30;
  const tijelo = document.body;
  const podaci = JSON.parse(document.getElementById("ts-podaci").textContent);
  const T = podaci.tekstovi;
  const KLJUC = "ts_kosarica_" + tijelo.dataset.drzava;
  let uMemoriji = [];

  const $ = (izbor, unutar = document) => unutar.querySelector(izbor);
  const $$ = (izbor, unutar = document) => Array.from(unutar.querySelectorAll(izbor));
  const odabrano = (forma, ime) => ($(`input[name=${ime}]:checked`, forma) || {}).value || "";

  function ispravne(popis) {
    if (!Array.isArray(popis)) return [];
    return popis
      .filter((s) => s && typeof s.id === "string" && Number.isInteger(s.kolicina) && s.kolicina > 0)
      .map((s) => ({ id: s.id, kolicina: Math.min(s.kolicina, MAKS_KOLICINA) }));
  }

  // localStorage baca grešku u privatnom prozoru ili kad su podaci blokirani; tada košarica
  // radi u memoriji do zatvaranja stranice.
  function citaj() {
    try {
      const zapis = localStorage.getItem(KLJUC);
      if (zapis !== null) return ispravne(JSON.parse(zapis));
    } catch (e) {
      /* ostaje memorija */
    }
    return uMemoriji.map((s) => ({ ...s }));
  }

  function pisi(stavke) {
    uMemoriji = stavke.map((s) => ({ ...s }));
    try {
      localStorage.setItem(KLJUC, JSON.stringify(stavke));
    } catch (e) {
      /* ostaje memorija */
    }
    osvjeziBroj(stavke);
  }

  function osvjeziBroj(stavke) {
    const broj = stavke.reduce((zbroj, s) => zbroj + s.kolicina, 0);
    for (const oznaka of $$("[data-broj-stavki]")) {
      oznaka.textContent = broj;
      oznaka.hidden = broj === 0;
    }
  }

  function novac(centi) {
    const o = podaci.oblik;
    const apsolutno = Math.abs(centi);
    const cijeli = Math.floor(apsolutno / 100)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, o.razdjelnik_tisuca);
    const iznos = (centi < 0 ? "-" : "") + cijeli + o.decimalni_znak + String(apsolutno % 100).padStart(2, "0");
    return o.uzorak_iznosa.replace("{iznos}", iznos).replace("{simbol}", podaci.simbol);
  }

  function kolicina(vrijednost) {
    const broj = parseInt(vrijednost, 10);
    return Number.isFinite(broj) ? Math.min(Math.max(broj, 1), MAKS_KOLICINA) : 1;
  }

  function poruka(element, tekst) {
    if (!element) return;
    if (tekst !== undefined) element.textContent = tekst;
    element.hidden = false;
  }

  async function katalog() {
    const odgovor = await fetch(tijelo.dataset.katalog, { cache: "no-cache" });
    if (!odgovor.ok) throw new Error("proizvodi.json " + odgovor.status);
    return odgovor.json();
  }

  // Stavka koje više nema ili nije dostupna makne se iz košarice uz poruku.
  function uskladi(k) {
    const pakiranja = new Map();
    for (const p of k.proizvodi) {
      for (const pak of p.pakiranja) pakiranja.set(pak.id, { ...pak, proizvod: p });
    }
    const stavke = citaj();
    const vazece = stavke.filter((s) => pakiranja.has(s.id));
    if (vazece.length !== stavke.length) pisi(vazece);
    const pune = vazece.map((s) => {
      const pak = pakiranja.get(s.id);
      return { id: s.id, kolicina: s.kolicina, naziv: pak.proizvod.naziv, oznaka: pak.oznaka,
        cijena_c: pak.cijena_c, url: pak.proizvod.url, slika: pak.proizvod.slika };
    });
    return { stavke: pune, maknuto: vazece.length !== stavke.length };
  }

  function dodaj(forma) {
    forma.addEventListener("submit", (dogadaj) => {
      dogadaj.preventDefault();
      const id = odabrano(forma, "pakiranje");
      if (!id) return;
      const stavke = citaj();
      const postojeca = stavke.find((s) => s.id === id);
      const greska = $("[data-poruka-greska]", forma);
      greska.hidden = true;
      if (!postojeca && stavke.length >= MAKS_STAVKI) {
        poruka(greska, T.previse_stavki);
        return;
      }
      const dodano = kolicina(forma.elements.namedItem("kolicina").value);
      if (postojeca) postojeca.kolicina = Math.min(MAKS_KOLICINA, postojeca.kolicina + dodano);
      else stavke.push({ id, kolicina: dodano });
      pisi(stavke);
      poruka($("[data-poruka]", forma));
    });
  }

  async function kosarica(okvir) {
    let stanje;
    try {
      stanje = uskladi(await katalog());
    } catch (e) {
      poruka($("[data-poruka]", okvir), T.greska_kataloga);
      return;
    }
    if (stanje.maknuto) poruka($("[data-poruka]", okvir), T.maknuto);
    const popis = $("[data-stavke]", okvir);
    const predlozak = $("#predlozak-stavke");

    function spremi() {
      pisi(stanje.stavke.map((s) => ({ id: s.id, kolicina: s.kolicina })));
      iscrtaj();
    }

    function redak(stavka) {
      const li = predlozak.content.firstElementChild.cloneNode(true);
      for (const veza of $$("[data-poveznica]", li)) veza.href = stavka.url;
      const slika = $("[data-slika]", li);
      if (stavka.slika) slika.src = stavka.slika;
      else slika.remove();
      $("[data-naziv]", li).textContent = stavka.naziv;
      $("[data-oznaka]", li).textContent = stavka.oznaka;
      $("[data-cijena]", li).textContent = novac(stavka.cijena_c);
      $("[data-iznos]", li).textContent = novac(stavka.cijena_c * stavka.kolicina);
      const unos = $("[data-kolicina]", li);
      unos.value = stavka.kolicina;
      unos.addEventListener("change", () => {
        stavka.kolicina = kolicina(unos.value);
        spremi();
      });
      $("[data-ukloni]", li).addEventListener("click", () => {
        stanje.stavke = stanje.stavke.filter((s) => s !== stavka);
        spremi();
      });
      return li;
    }

    function iscrtaj() {
      popis.replaceChildren(...stanje.stavke.map(redak));
      const prazna = stanje.stavke.length === 0;
      $("[data-prazna]", okvir).hidden = !prazna;
      $("[data-zbroj]", okvir).hidden = prazna;
      const meduzbroj = stanje.stavke.reduce((z, s) => z + s.cijena_c * s.kolicina, 0);
      $("[data-meduzbroj]", okvir).textContent = novac(meduzbroj);
    }

    iscrtaj();
  }

  function medjunarodni(telefon, pozivni) {
    let broj = telefon.replace(/[\s\-/().]/g, "");
    if (broj.startsWith("+")) return broj;
    if (broj.startsWith("00")) return "+" + broj.slice(2);
    if (broj.startsWith("0")) return "+" + pozivni + broj.slice(1);
    if (/^\d+$/.test(broj)) return "+" + (broj.startsWith(pozivni) ? "" : pozivni) + broj;
    return broj;
  }

  async function zdravlje() {
    const prekid = new AbortController();
    const sat = setTimeout(() => prekid.abort(), 6000);
    try {
      const odgovor = await fetch(tijelo.dataset.api + "/zdravlje", { signal: prekid.signal, cache: "no-store" });
      return odgovor.ok;
    } catch (e) {
      return false;
    } finally {
      clearTimeout(sat);
    }
  }

  function widget(pravila, forma) {
    if (!pravila.boxnow.partner_id) return;
    const id = forma.elements.namedItem("paketomat_id");
    const adresa = forma.elements.namedItem("paketomat_adresa");
    window._bn_map_widget_config = {
      partnerId: Number(pravila.boxnow.partner_id) || pravila.boxnow.partner_id,
      parentElement: "#boxnowmap",
      type: "popup",
      buttonSelector: "#boxnow-gumb",
      afterSelect: (lokacija) => {
        id.value = lokacija.boxnowLockerId || "";
        adresa.value = [lokacija.boxnowLockerName, lokacija.boxnowLockerAddressLine1, lokacija.boxnowLockerPostalCode]
          .filter(Boolean)
          .join(", ");
        $("[data-paketomat-adresa]").textContent = adresa.value || id.value;
        $("[data-paketomat-prikaz]").hidden = !id.value;
      },
    };
    const skripta = document.createElement("script");
    skripta.src = pravila.boxnow.skripta;
    skripta.async = true;
    document.head.appendChild(skripta);
  }

  function iznosi(pravila, stavke, forma) {
    const dostava = odabrano(forma, "dostava");
    const placanje = odabrano(forma, "placanje");
    const meduzbroj = stavke.reduce((z, s) => z + s.cijena_c * s.kolicina, 0);
    const opcija = pravila.dostave[dostava];
    const besplatna = pravila.besplatna_od_c > 0 && meduzbroj >= pravila.besplatna_od_c;
    const cijenaDostave = opcija && !besplatna ? opcija.cijena_c : 0;
    const naknada = placanje === "pouzece" ? pravila.naknada_pouzeca_c : 0;
    const ukupno = meduzbroj + cijenaDostave + naknada;
    const pdv = Math.round((ukupno * pravila.pdv_posto) / (100 + pravila.pdv_posto));
    return { meduzbroj, dostava: cijenaDostave, naknada, ukupno, pdv, odabrana: Boolean(opcija) };
  }

  function osvjeziBlagajnu(pravila, stavke, forma) {
    const dostava = odabrano(forma, "dostava");
    const opcija = pravila.dostave[dostava];
    for (const pouzece of $$("input[name=placanje][value=pouzece]", forma)) {
      pouzece.disabled = Boolean(opcija) && !opcija.pouzece;
      if (pouzece.disabled) pouzece.checked = false;
    }
    for (const panel of $$("[data-za-dostavu]", forma)) panel.hidden = panel.dataset.zaDostavu !== dostava;
    for (const polje of $$("[data-obavezno-uz]", forma)) polje.required = polje.dataset.obaveznoUz === dostava;

    const i = iznosi(pravila, stavke, forma);
    const prikaz = {
      meduzbroj: novac(i.meduzbroj),
      dostava: i.odabrana ? (i.dostava ? novac(i.dostava) : T.besplatno) : "–",
      naknada: novac(i.naknada),
      ukupno: novac(i.ukupno),
      pdv: novac(i.pdv),
    };
    for (const [kljuc, tekst] of Object.entries(prikaz)) $(`[data-iznos="${kljuc}"]`, forma).textContent = tekst;
    $("[data-red-naknade]", forma).hidden = i.naknada === 0;
    forma.elements.namedItem("ukupno_c").value = i.ukupno;
  }

  async function stavkeBlagajne(pravila, forma) {
    if (pravila.stavke) return pravila.stavke;
    const k = await katalog();
    forma.elements.namedItem("verzija").value = k.verzija;
    const stanje = uskladi(k);
    if (stanje.maknuto) poruka($("[data-poruka]"), T.maknuto);
    return stanje.stavke;
  }

  async function blagajna(forma) {
    const pravila = JSON.parse($("#ts-blagajna").textContent);
    const otvoreno = performance.now();
    let stavke;
    try {
      stavke = await stavkeBlagajne(pravila, forma);
    } catch (e) {
      poruka($("[data-poruka]"), T.greska_kataloga);
      forma.hidden = true;
      return;
    }
    if (!stavke.length) {
      forma.hidden = true;
      $("[data-prazna]").hidden = false;
      return;
    }
    forma.elements.namedItem("stavke").value = JSON.stringify(stavke.map((s) => ({ id: s.id, kolicina: s.kolicina })));
    $("[data-pregled-stavke]", forma).replaceChildren(
      ...stavke.map((s) => {
        const li = document.createElement("li");
        const opis = document.createElement("span");
        opis.textContent = `${s.kolicina} × ${s.naziv} · ${s.oznaka}`;
        const iznos = document.createElement("span");
        iznos.className = "broj";
        iznos.textContent = novac(s.cijena_c * s.kolicina);
        li.append(opis, iznos);
        return li;
      })
    );
    forma.addEventListener("change", () => osvjeziBlagajnu(pravila, stavke, forma));
    osvjeziBlagajnu(pravila, stavke, forma);
    widget(pravila, forma);

    const gumb = $("button[type=submit]", forma);
    const tekstGumba = gumb.textContent;
    window.addEventListener("pageshow", () => {
      gumb.disabled = false;
      gumb.textContent = tekstGumba;
    });
    forma.addEventListener("submit", async (dogadaj) => {
      dogadaj.preventDefault();
      const telefon = forma.elements.namedItem("telefon");
      telefon.value = medjunarodni(telefon.value, pravila.pozivni);
      forma.elements.namedItem("sekundi").value = Math.round((performance.now() - otvoreno) / 1000);
      const paketomat = forma.elements.namedItem("paketomat_id");
      if (odabrano(forma, "dostava") === "boxnow" && paketomat && !paketomat.value) {
        poruka($("[data-poruka]"), T.paketomat);
        ($("#boxnow-gumb") || paketomat).focus();
        return;
      }
      gumb.disabled = true;
      gumb.textContent = T.salje;
      // Kad backend ne radi, kupac dobije mail i telefon umjesto slanja u prazno.
      if (!(await zdravlje())) {
        $("[data-nedostupno]").hidden = false;
        $("[data-nedostupno]").scrollIntoView({ block: "center" });
        gumb.disabled = false;
        gumb.textContent = tekstGumba;
        return;
      }
      HTMLFormElement.prototype.submit.call(forma);
    });
  }

  // Zahvala je na adresi backenda, koja ne vidi košaricu ove stranice; zato se ovdje isprazni.
  function hvala(okvir) {
    const upit = new URLSearchParams(location.search);
    const broj = upit.get("n") || "";
    const token = upit.get("t") || "";
    if (!/^\d{4}-\d{4,6}$/.test(broj) || !/^[\w-]{16,64}$/.test(token)) return;
    pisi([]);
    const adresa = `${tijelo.dataset.api}/hvala/${broj}/${token}`;
    $("[data-hvala-link]", okvir).href = adresa;
    location.replace(adresa);
  }

  // Tko je u sustavu zatražio manje pokreta, videi ne kreću sami nego dobiju kontrole.
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    for (const video of $$("video[autoplay]")) {
      video.removeAttribute("autoplay");
      video.pause();
      video.controls = true;
    }
  }

  osvjeziBroj(citaj());
  for (const forma of $$("[data-dodaj]")) dodaj(forma);
  const okvirKosarice = $("[data-kosarica]");
  if (okvirKosarice) kosarica(okvirKosarice);
  const formaBlagajne = $("[data-blagajna]");
  if (formaBlagajne) blagajna(formaBlagajne);
  const okvirHvala = $("[data-hvala]");
  if (okvirHvala) hvala(okvirHvala);
})();
