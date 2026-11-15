"""But 23, lot 7 (D-415) — la page « Le jumeau », exécutée dans Chromium.

Le site construit est servi en local ; Chromium (Playwright, celui de la machine) charge
la page, Pyodide et numpy depuis le CDN, puis on règle des curseurs comme un lecteur :
un programme dans le mode réduit, le multiplicateur déplacé ; le mode structurel et la
vue figée, trois θ déplacés ; une loi hypothétique de dépense publique dans le mode
structurel ; une baisse d'impôt sur le revenu dans le mode réduit. Le mode structurel
d'un programme porte la convention « parts_premiere_annee » (D-414, D-419) jusqu'en 2035,
chaque année qu'elle ventile marquée ; sans elle, les années d'après 2026 sont refusées. Le
calcul tourne dans un Web Worker (D-419). À chaque réglage, chaque
nombre que la page affiche (sa valeur exacte, `data-v`) doit être celui de
`trajectoire.calculer` en Python, aux mêmes θ, à 1e-12 près en relatif ; un nombre que la
page dit absent doit l'être en Python. Puis la page à 390 px de large : aucun défilement
horizontal. Le temps de chargement et de recalcul est imprimé (D-335 : mesuré, pas tenu).

Lourd (tests/lourds.txt) : un navigateur et une minute. Il lit le CDN de Pyodide.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np
import pytest

from impots import site, site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.blocs import ordre_lot1, ordre_structurel
from impots.jumeau.gagnants import gagnants_perdants
from impots.jumeau.mesures import Mesure
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer, depart_depuis_start

NODE = shutil.which("node")
PLAYWRIGHT = os.environ.get("IMPOTS_PLAYWRIGHT", "/opt/node-tools/node_modules/playwright")
needs_browser = pytest.mark.skipif(
    NODE is None or not Path(PLAYWRIGHT).exists(),
    reason="node ou Playwright absent : la page ne s'exécute qu'avec un navigateur")
CAPTURES = Path(os.environ.get("IMPOTS_CAPTURES", "/tmp/jumeau-captures"))

HARNAIS = r"""
const { chromium } = require(process.argv[1]);
const url = process.argv[2], etapes = JSON.parse(process.argv[3]), captures = process.argv[4];
(async () => {
  const navigateur = await chromium.launch();
  const page = await navigateur.newPage({ viewport: { width: 1100, height: 900 },
                                           deviceScaleFactor: 1 });
  // Le fil principal ne doit plus figer pendant un calcul : ses tâches longues, relevées.
  await page.addInitScript(() => {
    window.__longues = [];
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__longues.push(e.duration); })
      .observe({ type: "longtask", buffered: true });
  });
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") erreurs.push(m.text()); });
  const t0 = Date.now();
  await page.goto(url);
  const pret = () => window.jumeau && (window.jumeau.erreur || window.jumeau.calculs >= 1);
  await page.waitForFunction(pret, null, { timeout: 240000 });
  const chargement = { ...(await page.evaluate(() => window.jumeau.chargement)),
                       premier_affichage_ms: Date.now() - t0 };
  const lire = () => page.evaluate(() => {
    const series = {};
    for (const s of document.querySelectorAll("section.serie")) {
      const lignes = {};
      for (const tr of s.querySelectorAll("tr[data-ligne]")) {
        const nom = tr.dataset.ligne === "part" ? "part:" + tr.dataset.part : tr.dataset.ligne;
        lignes[nom] = [...tr.querySelectorAll("td")].map((td) => td.dataset.v);
      }
      const marquees = [...s.querySelectorAll("thead th[data-convention]")].map((th) => Number(th.dataset.annee));
      const cellules = [...s.querySelectorAll("tr[data-ligne] td[data-convention]")].length;
      series[s.id.slice(2)] = { lignes, absent: !!s.querySelector("[data-absent]"), marquees, cellules };
    }
    const deciles = [...document.querySelectorAll("#deciles tr[data-decile]")].map(
      (tr) => [...tr.querySelectorAll("td")].map((td) => td.dataset.v));
    const annee = document.getElementById("annee-deciles");
    return { choix: window.jumeau.dernier.choix, series, deciles,
             annee_deciles: annee ? annee.value : null,
             refus: (document.querySelector("[data-refus]") || {}).textContent || null,
             conventions: window.jumeau.dernier.resultat.conventions,
             definition: !!document.getElementById("def-convention"),
             erreur: window.jumeau.erreur || null };
  });
  const sorties = [];
  for (const etape of etapes) {
    const temps = [];
    for (const action of etape) {
      const avant = await page.evaluate(() => window.jumeau.calculs);
      const t = Date.now();
      if (action.choisir) await page.selectOption("#" + action.choisir[0], action.choisir[1]);
      if (action.cocher) await page.check("#" + action.cocher);
      if (action.decocher) await page.uncheck("#" + action.decocher);
      if (action.remplir) {
        await page.fill("#" + action.remplir[0], String(action.remplir[1]));
        await page.dispatchEvent("#" + action.remplir[0], "change");
      }
      if (action.theta) await page.$eval("#r-" + action.theta[0], (el, v) => {
        el.value = String(v); el.dispatchEvent(new Event("input")); }, action.theta[1]);
      await page.waitForFunction((n) => window.jumeau.calculs > n &&
        !document.getElementById("etat").textContent.startsWith("Calcul…"), avant,
        { timeout: 120000 });
      temps.push({ action, mur_ms: Date.now() - t,
                   calcul_ms: await page.evaluate(() => window.jumeau.temps.at(-1)) });
    }
    const longues = await page.evaluate(() => window.__longues.splice(0));
    sorties.push({ ...(await lire()), temps, longue_max_ms: Math.max(0, ...longues) });
    await page.screenshot({ path: `${captures}/etape-${sorties.length}.png`, fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  const telephone = await page.evaluate(() => ({
    largeur: document.documentElement.scrollWidth, fenetre: window.innerWidth }));
  await page.screenshot({ path: `${captures}/telephone.png`, fullPage: false });
  await page.screenshot({ path: `${captures}/telephone-page.png`, fullPage: true });
  process.stdout.write(JSON.stringify({ chargement, sorties, telephone, erreurs }));
  await navigateur.close();
})().catch((e) => { console.error(e); process.exit(1); });
"""

ATTAL = "pres2027_attal_programme"
ETAPES = [
    # La page s'ouvre sur une loi simple, dans le jumeau, population figée (D-459) : la
    # première étape choisit la mesure d'étude, la chaîne des études et la vue vieillie.
    [{"cocher": "entree-candidat"}, {"cocher": "mode-reduit"}, {"choisir": ["vue", "vieillie"]},
     {"choisir": ["candidat", ATTAL]}, {"theta": ["multiplicateur_macro", 0.8]}],
    [{"cocher": "mode-structurel"}, {"choisir": ["vue", "figee"]},
     {"theta": ["idees_creations", 0.9]}, {"theta": ["jumeau_emploi_elasticite_cout", 0.2]},
     {"theta": ["survie_creations", 0.3]}],
    [{"decocher": "convention"}],
    [{"cocher": "entree-hypothese"}, {"choisir": ["h-instrument", "depense_publique"]},
     {"remplir": ["h-montant", 12.5]}, {"choisir": ["h-debut", "2027"]},
     {"choisir": ["h-fin", "2033"]}, {"theta": ["commerce_elasticite_prix_exportations", 0.1]}],
    [{"cocher": "mode-reduit"}, {"choisir": ["h-instrument", "impot_sur_le_revenu"]},
     {"theta": ["multiplicateur_macro", 0.25]}],
]


@pytest.fixture(scope="module")
def serveur():
    """Le site construit, servi en local : la page lit ses fichiers par HTTP."""
    racine = Path(os.environ.get("IMPOTS_SITE_TEST", "/tmp/jumeau-site"))
    racine.mkdir(parents=True, exist_ok=True)
    for nom, texte in site_jumeau.build().items():
        (racine / nom).write_text(texte, encoding="utf-8")
    (racine / "style.css").write_text(site.STYLE, encoding="utf-8")
    gestion = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(racine))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), gestion)
    fil = threading.Thread(target=httpd.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/{site_jumeau.PAGE}"
    httpd.shutdown()


def _lu(v: str):
    return None if v == "absent" else float(v)


ECARTS: list[float] = []


def _egal(page: list, attendu: list, quoi: str) -> None:
    assert len(page) == len(attendu), quoi
    for k, (p, a) in enumerate(zip(page, attendu, strict=True)):
        p = _lu(p)
        if a is None or p is None:
            assert p is None and a is None, (quoi, k, p, a)
        else:
            assert abs(p - a) <= 1e-12 * max(1.0, abs(a)), (quoi, k, p, a)
            ECARTS.append(abs(p - a) / max(1.0, abs(a)))


def _trajectoire(donnees, choix):
    """La trajectoire du réglage, en Python, sans passer par `navigateur.Session.calculer`
    : la mesure lue dans le rapport entier, le départ, les blocs du mode."""
    session = navigateur.Session(donnees)
    if choix.get("candidat"):
        c = donnees["candidats"][choix["candidat"]]
        chemin = site_jumeau.etude.ROOT / c["rapport"]
        premiere = chemin.with_name(chemin.name.replace("predictif_", "premiere_annee_"))
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        m = Mesure.depuis_rapport(payload, vue=choix["vue"], identifiant=choix["candidat"],
                                  libelle=c["libelle"], auteur=c["auteur"],
                                  rapport=c["rapport"],
                                  premiere_annee=json.loads(premiere.read_text()),
                                  convention=choix.get("convention"))
        rejeu, persistance = payload["rejeu"], payload["lectures"]["persistence"]
        boucle, creations = rejeu["looped"], bool(rejeu.get("creations"))
    else:
        m = session.hypothese(choix["hypothese"])
        rejeu, persistance = donnees["cadre"], donnees["cadre"]["persistence"]
        boucle, creations = True, False
    return m, rejeu, persistance, boucle, creations, session


def _attendu(donnees, choix, n_annees):
    m, rejeu, persistance, boucle, creations, session = _trajectoire(donnees, choix)
    annees = navigateur.ANNEES[:n_annees]
    entrees = Entrees.depuis_rejeu(rejeu, annees)
    if choix["mode"] == "reduit":
        depart = depart_depuis_start(rejeu["start"], session.parts)
        blocs, boucles = ordre_lot1(depart, persistance=persistance, boucle=boucle,
                                    creations=creations), ()
    else:
        depart = navigateur.etat_depuis_dict(donnees["entrees"]["depart_publie"])
        blocs, boucles = ordre_structurel(depart, session.population, session.cellules)
    traj = calculer(depart, entrees=entrees, mesures=[m], theta=choix["theta"],
                    blocs=blocs, boucles=boucles)
    return traj, depart, session


def _etiquette(c) -> str:
    return c[0] if not c[1] else f"{c[0]} · {c[1]}"


def _verifier(donnees, sortie) -> int:
    """Chaque nombre de la page contre la trajectoire Python ; rend leur nombre."""
    choix = sortie["choix"]
    ecart_dette = sortie["series"]["dette"]["lignes"]["ecart"]
    n = sum(v != "absent" for v in ecart_dette)
    traj, depart, session = _attendu(donnees, choix, n)
    pad = [None] * (10 - n)
    vus = 0
    for champ, s in sortie["series"].items():
        lignes = s["lignes"]
        if champ == "dette":
            ref, var = traj.niveaux("ratio_dette")
            attendu = {"ecart": [100 * float(x[0]) for x in traj.delta_b],
                       "reference": [100 * float(x[0]) for x in ref],
                       "variante": [100 * float(x[0]) for x in var]}
            parts: dict[str, list] = {}
            for k, a in enumerate(traj.annees):
                for c, x in traj.decomposition(a).items():
                    parts.setdefault(_etiquette(c), [0.0] * n)[k] = 100 * float(x[0])
        else:
            nom = {"solde": "b9"}.get(champ, champ)
            presents = [r.present(nom) and v.present(nom)
                        for r, v in zip(traj.reference, traj.variante, strict=True)]
            if not any(presents):
                assert s["absent"], champ
                continue
            echelle = [100 / float(r["pib"][0]) if champ == "pib" else 1.0
                       for r in traj.reference]
            attendu = {"reference": [float(r[nom][0]) for r in traj.reference],
                       "variante": [float(v[nom][0]) for v in traj.variante],
                       "ecart": ([100 * float(x[0]) for x in traj.ecart_pib] if champ == "pib"
                                 else [float((v[nom] - r[nom])[0]) for r, v in
                                       zip(traj.reference, traj.variante, strict=True)])}
            parts = {}
            for k, (r, v) in enumerate(zip(traj.reference, traj.variante, strict=True)):
                dr, dv = r.de(nom), v.de(nom)
                for c in set(dr) | set(dv):
                    x = float((dv.get(c, np.zeros(1)) - dr.get(c, np.zeros(1)))[0]) * echelle[k]
                    parts.setdefault(_etiquette(c), [0.0] * n)[k] = x
        parts = {c: v for c, v in parts.items() if any(v)}
        for ligne in ("ecart", "reference", "variante"):
            _egal(lignes[ligne], attendu[ligne] + pad, f"{champ} {ligne}")
            vus += n
        assert {k.removeprefix("part:") for k in lignes if k.startswith("part:")} == set(parts)
        for c, v in parts.items():
            _egal(lignes["part:" + c], v + pad, f"{champ} {c}")
            vus += n
    if choix["mode"] == "structurel" and sortie["deciles"]:
        g = gagnants_perdants(traj, depart, session.cellules)
        k = traj.annees.index(int(sortie["annee_deciles"]))
        menages = np.asarray(session.cellules["menages"]).reshape(10, 5).sum(axis=1)
        total = g.ecart_md[k, :, 0].reshape(10, 5).sum(axis=1) * 1e9 / menages
        _egal([r[0] for r in sortie["deciles"]], [float(x) for x in total], "déciles")
        vus += 10
    return vus


@pytest.mark.lourd
@needs_browser
def test_la_page_affiche_les_nombres_du_jumeau(serveur) -> None:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    fait = subprocess.run([NODE, "-e", HARNAIS, PLAYWRIGHT, serveur, json.dumps(ETAPES),
                           str(CAPTURES)], capture_output=True, text=True, timeout=900,
                          check=False)
    assert fait.returncode == 0, fait.stderr[-3000:]
    r = json.loads(fait.stdout)
    assert not r["erreurs"], r["erreurs"]
    donnees = json.loads((Path(os.environ.get("IMPOTS_SITE_TEST", "/tmp/jumeau-site"))
                          / site_jumeau.DONNEES).read_text(encoding="utf-8"))
    attendus = [
        {"mode": "reduit", "vue": "vieillie", "candidat": ATTAL},
        {"mode": "structurel", "vue": "figee", "candidat": ATTAL,
         "convention": "parts_premiere_annee"},
        {"mode": "structurel", "vue": "figee", "candidat": ATTAL, "convention": None},
        {"mode": "structurel", "vue": "figee", "hypothese": {
            "instrument": "depense_publique", "montant": 12.5, "debut": 2027, "fin": 2033}},
        {"mode": "reduit", "vue": "figee", "hypothese": {
            "instrument": "impot_sur_le_revenu", "montant": 12.5, "debut": 2027,
            "fin": 2033}},
    ]
    total = 0
    for sortie, attendu in zip(r["sorties"], attendus, strict=True):
        assert sortie["erreur"] is None, sortie["erreur"]
        choix = sortie["choix"]
        for cle, valeur in attendu.items():
            assert choix.get(cle) == valeur, (cle, choix.get(cle))
        total += _verifier(donnees, sortie)
    assert r["sorties"][0]["choix"]["theta"]["multiplicateur_macro"] == 0.8
    # La convention : dix ans, chaque année d'après la première marquée dans chaque série
    # calculée (l'écart, ses parts, la variante), sa définition affichée ; sans elle, le
    # refus de D-412.
    avec, sans = r["sorties"][1], r["sorties"][2]
    assert avec["refus"] is None and avec["definition"]
    assert avec["conventions"]["annees"] == list(navigateur.ANNEES[1:])
    for champ, s in avec["series"].items():
        if not s["absent"]:
            assert s["marquees"] == list(navigateur.ANNEES[1:]), champ
            assert s["cellules"] == 9 * (len(s["lignes"]) - 1), champ
    assert sans["refus"] and "D-412" in sans["refus"] and not sans["definition"]
    assert all(not s["marquees"] for s in sans["series"].values())
    assert r["sorties"][3]["conventions"] is None
    assert r["telephone"]["largeur"] <= r["telephone"]["fenetre"] == 390, r["telephone"]
    print(f"\n{total} nombres égaux, {sum(e == 0 for e in ECARTS)} au bit, écart relatif "
          f"maximal {max(ECARTS):.1e} ; chargement {json.dumps(r['chargement'])}")
    for i, sortie in enumerate(r["sorties"], 1):
        print(f"étape {i} (tâche longue du fil principal : {sortie['longue_max_ms']:.0f} ms) : "
              + " ; ".join(f"{t['action']} {t['calcul_ms']:.0f} ms "
                                             f"({t['mur_ms']} ms au mur)"
                                             for t in sortie["temps"]))
