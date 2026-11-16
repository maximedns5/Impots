"""La ventilation des chocs de la première année, par payeur et par instrument (but 26,
volet « ventilation », D-475 à D-477), lue dans les rapports commités, sans passe.

LE PROBLÈME (D-469, J2). Le canal des créations somme, chaque année et dans chaque vue,
les prélèvements que la passe a faits sur les entreprises et le capital (`ΔP`, D-443) :
l'IS, sa contribution sociale, la CEBGE, et trois prélèvements de la passe des MÉNAGES,
les cotisations des employeurs nettes des allègements, le PFU et les prélèvements sociaux
du capital. Jusqu'ici, `mesures.ventilations` ne savait ranger que les premiers par impôt :
le reste refusait la mesure au bloc `chocs_entreprises`. Or les rapports le portent :

* les cotisations des employeurs, E : la passe des ménages de la première année porte
  Δ(salaire_super_brut − salaire_brut) (`aggregate._employer_contribution_delta`), et le
  rapport du chemin annuel porte, CHAQUE ANNÉE ET DANS CHAQUE VUE, l'impulsion de Mésange
  « cotisations_employeurs » (ou « …_ciblees »), qui est −E (`shocks.instrument_deltas`).
  Les deux se recoupent à l'euro dans les onze programmes (D-475) ;
* le PFU et les prélèvements sociaux du capital, K : le reste de ΔP de la première année,
  une fois retirés l'IS, sa contribution, la CEBGE (la passe des entreprises) et E. Le
  rapport ne sépare pas le PFU des prélèvements sociaux : K est porté tel quel, sous un
  nom qui le dit (`CAPITAL`), sur le même signal et la même catégorie du compte des APU
  que les deux (`champs.SIGNAUX_ENTREPRISES`, D5).

QUI PAIE E. Un employeur privé (une société, au signal « cotisations_patronales » que
lisent les naissances et les fermetures), ou les APU elles-mêmes quand le levier est la
rémunération publique (le point d'indice) : alors E est payé par l'État employeur aux
caisses, une opération interne aux APU, que le coût de la passe rend déjà
(`aggregate._salary_terms`) ; il ne va pas aux entreprises. Les leviers le disent
(`payeur`) ; un rapport qui mêle les deux (un Smic et un point d'indice dans la même
passe) ne se sépare pas sans passe : refusé, dit.

LES ANNÉES SUIVANTES ET LA VUE VIEILLIE (`etendre`). E se lit chaque année dans la vue de
la mesure ; le reste, R_t = P_t − E_t, est réparti aux parts de la première année figée
(la convention « parts_premiere_annee », D-414, pour la vue figée ; « parts_figee »,
D-476, pour la vue vieillie, où même la première année est répartie ainsi). Le choc des
ménages suit leur coût, C^m_t = coût_t + F_t + E_t (F les impôts de la passe des
entreprises ; E seulement s'il est privé), aux parts par décile de la première année
figée. Chaque nombre qu'une convention fait est nommé dans `Mesure.conventions`.

LA CORRESPONDANCE (`parametres/ventilation.yaml`) : chaque module d'une passe, son payeur,
le bloc qui le lit et le sous-secteur des APU qui l'encaisse ou le paie, avec son texte.
`premiere_annee` en tire, pour un rapport, la ventilation complète de sa première année
par payeur : ce que les volets « travail », « financement » et « cascade » lisent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from impots.jumeau.mesures import (
    CONVENTION_PARTS,
    EURO,
    EURO_PRES,
    TEXTE_CONVENTION,
    VUE_PREMIERE_ANNEE,
    MesureError,
    _passes,
)
from impots.predictif.creations import PRODUCTION as HORS_CANAL

FICHIER = Path(__file__).resolve().parent / "parametres" / "ventilation.yaml"

#: Les cotisations des employeurs, nettes des allègements (l'impôt du bloc des entreprises).
COTISATIONS = "cotisations_employeurs"
#: Le PFU et les prélèvements sociaux du capital, que les rapports ne séparent pas.
CAPITAL = "pfu_et_prelevements_sociaux_capital"
#: Les impulsions de Mésange qui portent −E (`shocks.build`).
IMPULSIONS_EMPLOYEURS = ("cotisations_employeurs", "cotisations_employeurs_ciblees")
#: Les leviers dont E est payé par les APU employeurs (la rémunération publique).
LEVIERS_PUBLICS = ("point_indice_revalorisation", "point_indice_contractuels")

#: La convention de la vue vieillie (D-476).
CONVENTION_VIEILLIE = "parts_figee"
TEXTE_VIEILLIE = (
    "ventilé par la convention « parts_figee » (D-476) : dans la population vieillie, le "
    "total de chaque année du chemin annuel (vue vieillie) aux parts de la première année "
    "figée, première année comprise ; les cotisations des employeurs, elles, sont lues "
    "année par année dans la vue vieillie ; pas une passe")
#: Ce que dit chaque convention, par son nom (la page les rend, `navigateur._conventions`).
TEXTES = {CONVENTION_PARTS: TEXTE_CONVENTION, CONVENTION_VIEILLIE: TEXTE_VIEILLIE}


@lru_cache(maxsize=1)
def correspondance() -> dict[str, dict[str, Any]]:
    """Les modules, leurs payeurs, blocs et sous-secteurs (`ventilation.yaml`)."""
    return yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["modules"]


# --------------------------------------------------------------------------- #
# ce que les rapports portent
# --------------------------------------------------------------------------- #
def employeurs_lus(payload: Mapping[str, Any], vue: str) -> dict[int, float] | None:
    """E_t, les cotisations des employeurs nettes des allègements, Md€, recettes
    positives, par année du chemin, dans la vue : −Σ des impulsions « cotisations
    employeurs » que le rapport porte. None quand le rapport n'a pas de boucle (il ne
    porte pas d'impulsions) : E n'est pas lu, jamais un zéro."""
    if not (payload.get("rejeu") or {}).get("looped"):
        return None
    out = {}
    for r in payload["years"]:
        imp = r["statistiques"][vue].get("impulses") or {}
        out[int(r["year"])] = -sum(float(imp.get(i, 0.0) or 0.0)
                                   for i in IMPULSIONS_EMPLOYEURS) / EURO
    return out


def leviers(premiere_annee: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Les boutons de la réforme de la passe des ménages de la première année."""
    if premiere_annee is None:
        return ()
    passes = _passes(premiere_annee)
    if "menages" not in passes:
        return ()
    return tuple(sorted(passes["menages"]["requete"].get("reform") or {}))


def payeur(premiere_annee: Mapping[str, Any] | None) -> str:
    """Qui paie E : « publics » quand les seuls leviers qui touchent les salaires sont
    ceux de la rémunération publique, « meles » quand la passe porte aussi d'autres
    leviers sur le coût du travail, « prives » sinon."""
    boutons = leviers(premiere_annee)
    publics = [b for b in boutons if b in LEVIERS_PUBLICS]
    if not publics:
        return "prives"
    prives = [b for b in boutons if b not in LEVIERS_PUBLICS and (
        b.startswith(("smic", "allegement", "heures_sup_exoneration_patronale",
                      "cotisations_employeur", "cotisations_patronales")))]
    return "meles" if prives else "publics"


def employeurs_premiere(premiere_annee: Mapping[str, Any]) -> float | None:
    """E de la première année figée, Md€, tel que la passe des ménages le porte :
    Δ(salaire_super_brut − salaire_brut). None sans passe des ménages."""
    passes = _passes(premiere_annee)
    if "menages" not in passes:
        return None
    d = passes["menages"]["reponse"].get("deltas") or {}
    if "salaire_super_brut" not in d or "salaire_brut" not in d:
        return None
    return (float(d["salaire_super_brut"]) - float(d["salaire_brut"])) / EURO


# --------------------------------------------------------------------------- #
# la première année figée : ce que `mesures.ventilations` ne rangeait pas
# --------------------------------------------------------------------------- #
def completer(payload: Mapping[str, Any], premiere_annee: Mapping[str, Any], *,
              premiere: int, par_impot: Mapping[str, float], reste: float
              ) -> tuple[dict[str, float] | None, dict[str, str]]:
    """Les impôts de la première année figée, `par_impot` (euros, ceux de la passe des
    entreprises) complétés de E et de K, quand la somme du canal des créations ne se
    réduit pas à eux (`reste`, euros) ; en Md€. Rend (impôts, notes) ; impôts None avec
    la raison quand le rapport ne permet pas de les séparer.

    E est lu deux fois et recoupé à l'euro : la passe des ménages et l'impulsion du chemin
    figé de la première année ; deux nombres qui diffèrent ne sont pas la même passe.
    K = reste − E. Un E des APU employeurs ne va pas aux entreprises (notes)."""
    notes: dict[str, str] = {}
    e_passe = employeurs_premiere(premiere_annee)
    lus = employeurs_lus(payload, VUE_PREMIERE_ANNEE)
    e_chemin = None if lus is None else lus.get(premiere)
    if e_passe is None and e_chemin is None:
        return None, {"entreprises": (
            f"{reste / EURO:+.3f} Md€ de prélèvements des ménages en {premiere} (cotisations "
            f"des employeurs, PFU, prélèvements sociaux du capital) que le rapport ne porte "
            f"ni par sa passe des ménages ni par ses impulsions")}
    e = e_passe if e_passe is not None else e_chemin
    if e_passe is not None and e_chemin is not None and abs(e_passe - e_chemin) * EURO > \
            EURO_PRES:
        raise MesureError(f"cotisations des employeurs de {premiere} : {e_passe:+.6f} Md€ "
                          f"dans la passe, {e_chemin:+.6f} Md€ dans le chemin : pas la même "
                          f"passe")
    qui = payeur(premiere_annee)
    if abs(e) * EURO > EURO_PRES and qui == "meles":
        return None, {"entreprises": (
            f"{e:+.3f} Md€ de cotisations des employeurs en {premiere}, que la passe fait "
            f"payer à la fois par des employeurs privés et par les APU employeurs (des "
            f"leviers sur le coût du travail privé et sur la rémunération publique) : le "
            f"rapport ne les sépare pas")}
    out = {i: v / EURO for i, v in par_impot.items()}
    capital = reste / EURO - e
    if abs(e) * EURO > EURO_PRES:
        if qui == "publics":
            notes["cotisations_employeurs"] = (
                f"{e:+.3f} Md€ de cotisations des APU employeurs en {premiere} (la "
                f"rémunération publique) : payées par les APU à leurs caisses, hors des "
                f"impôts des entreprises")
        else:
            out[COTISATIONS] = e
    if abs(capital) * EURO > EURO_PRES:
        out[CAPITAL] = capital
    return out, notes


# --------------------------------------------------------------------------- #
# les années suivantes, et la vue vieillie
# --------------------------------------------------------------------------- #
def etendre(payload: Mapping[str, Any], premiere_annee: Mapping[str, Any] | None,
            entreprises: dict[int, Any] | None, menages: dict[int, Any] | None,
            non_portes: dict[str, str], *, vue: str, premiere: int,
            annees: tuple[int, ...], couts: Mapping[int, float],
            prelevements: Mapping[int, float]
            ) -> tuple[dict[int, Any] | None, dict[int, Any] | None, dict[str, str],
                       dict[str, dict[int, str]]]:
    """Les conventions de ventilation des années que la passe n'a pas ventilées : dans la
    vue figée, les années après la première (« parts_premiere_annee », D-414) ; dans la
    vue vieillie, toutes (« parts_figee », D-476). `entreprises`, `menages` sont ceux de
    la première année FIGÉE (`mesures.ventilations`), `couts` et `prelevements` ceux de
    la vue de la mesure.

    LES ENTREPRISES. E_t lu dans la vue (`employeurs_lus`) ; R_t = P_t − E_t (E de tous
    les employeurs, privés ou publics : P le somme) ; pour chaque impôt i autre que E,
    X_{i,t} = s_i R_t, s_i = X_{i,1} / R_1, X_{i,1} de la première année figée ;
    E_t va aux entreprises s'il est privé. Ce sont les parts de D-414, mais E n'y est plus
    réparti : il est lu.

    LES MÉNAGES. G_{d,t} = g_d C^m_t, g_d = G_{d,1} / C^m_1, C^m_t = coût_t + F_t + E^p_t
    (F les cinq impôts de la passe des entreprises, E^p les cotisations des employeurs
    privés : le coût de la passe les compte, le revenu des ménages non).

    REFUSÉE là où les parts n'existent pas : ce qui manque reste absent, dit dans
    `non_portes`. Sans E ni K, elle redonne au bit les nombres de D-414."""
    from impots.jumeau.mesures import prelevements_lus

    conventions: dict[str, dict[int, str]] = {}
    non_portes = dict(non_portes)
    vieillie = vue != VUE_PREMIERE_ANNEE
    nom = CONVENTION_VIEILLIE if vieillie else CONVENTION_PARTS
    texte = TEXTE_VIEILLIE if vieillie else TEXTE_CONVENTION
    suivantes = list(annees) if vieillie else [a for a in annees if a != premiere]
    if not suivantes:
        return entreprises, menages, non_portes, conventions
    refus: list[str] = []
    prives = payeur(premiere_annee) == "prives"
    e_lus = employeurs_lus(payload, vue)
    x1 = dict(entreprises[premiere]) if entreprises is not None else None
    e1 = (employeurs_premiere(premiere_annee) if premiere_annee is not None else None) or 0.0

    def employeurs(a: int) -> float:
        return 0.0 if e_lus is None else e_lus.get(a, 0.0)

    reste = {a: prelevements.get(a, 0.0) - employeurs(a) for a in suivantes}
    parts: dict[str, float] | None = None
    if x1 is None:
        refus.append("entreprises")
        non_portes["entreprises"] = (f"{non_portes.get('entreprises', '')} ; la convention "
                                     f"« {nom} » n'a pas de parts").lstrip(" ;")
        entreprises = None
    elif e_lus is None and abs(e1) * EURO > EURO_PRES:
        refus.append("entreprises")
        non_portes["entreprises"] = (f"des cotisations des employeurs en {premiere} et un "
                                     f"rapport sans boucle : ses autres années ne les "
                                     f"portent pas")
        entreprises = None if vieillie else {premiere: x1}
    else:
        autres = {i: float(v) for i, v in x1.items() if i != COTISATIONS}
        r1 = sum(autres.values())
        if r1 == 0.0 and any(abs(reste[a]) * EURO > EURO_PRES for a in suivantes):
            refus.append("entreprises")
            non_portes["entreprises"] = (f"prélèvements hors cotisations des employeurs "
                                         f"nuls en {premiere}, pas en {suivantes} : pas de "
                                         f"parts pour la convention")
            entreprises = None if vieillie else {premiere: x1}
        else:
            parts = {i: (v / r1 if r1 else 0.0) for i, v in autres.items()}

            def annee(a: int) -> dict[str, float]:
                out = {i: s * reste[a] for i, s in parts.items()}
                if prives and (COTISATIONS in x1 or abs(employeurs(a)) * EURO > EURO_PRES):
                    out[COTISATIONS] = employeurs(a)
                return out

            entreprises = {**({} if vieillie else {premiere: x1}),
                           **{a: annee(a) for a in suivantes}}
            conventions["entreprises"] = dict.fromkeys(suivantes, nom)

    if menages is None:
        refus.append("menages")
        non_portes["menages"] = (f"{non_portes.get('menages', '')} ; la convention "
                                 f"« {nom} » n'a pas de parts").lstrip(" ;")
    elif parts is None and any(abs(prelevements.get(a, 0.0)) * EURO > EURO_PRES
                               for a in annees):
        # Des prélèvements que la ventilation n'a pas rangés : le coût des ménages de
        # chaque année ne se sépare pas de celui des entreprises.
        refus.append("menages")
        non_portes["menages"] = (
            "le chemin ne sépare pas le coût des ménages de celui des entreprises (leurs "
            "prélèvements ne sont pas ventilés) : pas de total pour la convention")
        if vieillie:
            menages = None
    else:
        # C^m_t = coût_t + P_t − E_t − K_t + E^p_t : le coût, moins ce que paient les
        # entreprises (F_t = P_t − E_t − K_t) et les employeurs privés (E^p_t).
        s_k = (parts or {}).get(CAPITAL, 0.0)

        def cout_menages(cout: float, p: float, e: float, r: float) -> float:
            c = cout + p
            if e:
                c = c - e + (e if prives else 0.0)
            if s_k:
                c = c - s_k * r
            return c

        p1 = prelevements_lus(payload, VUE_PREMIERE_ANNEE)[0].get(premiere, 0.0)
        cout1 = cout_menages(float(payload["years"][0]["mechanical_frozen_eur"]) / EURO,
                             p1, e1, p1 - e1)
        cout = {a: cout_menages(couts[a], prelevements.get(a, 0.0), employeurs(a), reste[a])
                for a in suivantes}
        deciles = list(menages[premiere]["deciles"])
        if cout1 == 0.0 and any(cout[a] for a in suivantes):
            refus.append("menages")
            non_portes["menages"] = (f"coût des ménages nul en {premiere}, pas en "
                                     f"{suivantes} : pas de parts pour la convention")
            if vieillie:
                menages = None
        else:
            echelle = {a: (cout[a] / cout1 if cout1 else 0.0) for a in suivantes}
            menages = {**({} if vieillie else {premiere: menages[premiere]}),
                       **{a: {"deciles": [g * echelle[a] for g in deciles]}
                          for a in suivantes}}
            conventions["menages"] = dict.fromkeys(suivantes, nom)

    if vieillie:
        for axe in ("entreprises", "menages"):
            if axe in conventions:
                non_portes.pop(axe, None)
    if conventions:
        non_portes.pop("annees", None)
        if refus:
            non_portes["annees"] = (f"{suivantes[0]} à {suivantes[-1]} : {', '.join(refus)} "
                                    f"sans parts, absents ; le reste {texte}")
    return entreprises, menages, non_portes, conventions


# --------------------------------------------------------------------------- #
# la ventilation complète de la première année, par payeur (pour les autres volets)
# --------------------------------------------------------------------------- #
def premiere_annee(payload: Mapping[str, Any], premiere_annee_: Mapping[str, Any]
                   ) -> dict[str, Any]:
    """La ventilation de la première année figée d'un rapport, module par module : son
    montant (Md€, au signe d'un solde des APU : une recette en plus ou une dépense en
    moins est positive), son payeur, le bloc du jumeau qui le lit, le sous-secteur des
    APU et la branche (`ventilation.yaml`). Rien n'est ajouté que le rapport ne porte :
    le coût de la passe, moins la somme des lignes, est rendu tel quel (`non_reparti`).

    Les lignes : les recettes et les prestations des ménages que compte l'identité des
    comptes (`guards.STATE_RECEIPTS`, `STATE_TRANSFERS`), E et K (`completer`), les
    impôts de la passe des entreprises. Les ménages ne sont par décile que pour leur total
    (`menages_deciles`, Md€, gain positif) : le rapport ne donne pas le décile d'un
    module."""
    from impots.guards import STATE_RECEIPTS, STATE_TRANSFERS

    table = correspondance()
    passes = _passes(premiere_annee_)
    premiere = int(payload["years"][0]["year"])
    lignes: list[dict[str, Any]] = []

    def ligne(module: str, montant: float, **extra: Any) -> None:
        c = table.get(module, {})
        lignes.append({"module": module, "solde_apu_md": montant,
                       "payeur": extra.pop("payeur", c.get("payeur")),
                       "bloc": c.get("bloc"), "sous_secteur": extra.pop(
                           "sous_secteur", c.get("sous_secteur")),
                       "branche": c.get("branche"), "source": c.get("source"), **extra})

    menages_deciles = None
    if "menages" in passes:
        d = passes["menages"]["reponse"].get("deltas") or {}
        for nom in STATE_RECEIPTS:
            if d.get(nom):
                ligne(nom, float(d[nom]) / EURO)
        for nom in STATE_TRANSFERS:
            if d.get(nom):
                ligne(nom, -float(d[nom]) / EURO)
        dec = passes["menages"]["reponse"].get("deciles")
        if dec:
            from impots.jumeau.blocs.menages import menages_depuis_deciles

            menages_deciles = menages_depuis_deciles(dec)
    e = employeurs_premiere(premiere_annee_)
    qui = payeur(premiere_annee_)
    if e:
        ligne(COTISATIONS, e, payeur=f"employeurs {qui}",
              **({"sous_secteur": "ASSO (payé par les APU employeurs : interne aux APU)"}
                 if qui == "publics" else {}))
    creations = (payload.get("rejeu") or {}).get("creations")
    if creations:
        lus = list(creations["parametres"]["instruments_entreprises"])
        canal = float(creations["variations"][VUE_PREMIERE_ANNEE][0])
        deltas = (passes["entreprises"]["reponse"].get("deltas") or {}
                  if "entreprises" in passes else {})
        capital = canal - sum(float(deltas.get(i, 0.0) or 0.0) for i in lus) - (e or 0.0) * EURO
        if "menages" in passes:
            capital -= float((passes["menages"]["reponse"].get("deltas") or {})
                             .get("prelevements_sociaux_capital", 0.0) or 0.0)
        if abs(capital) > EURO_PRES:
            ligne(CAPITAL, capital / EURO)
    if "entreprises" in passes:
        d = passes["entreprises"]["reponse"].get("deltas") or {}
        for nom in ("impot_societes", "contribution_sociale_is", "cebge", *HORS_CANAL):
            if d.get(nom):
                ligne(nom, float(d[nom]) / EURO)
    cout = sum(float(p["reponse"]["reform_cost"]) for p in passes.values()) / EURO
    somme = sum(x["solde_apu_md"] for x in lignes)
    par_payeur: dict[str, float] = {}
    par_sous_secteur: dict[str, float] = {}
    for x in lignes:
        par_payeur[x["payeur"]] = par_payeur.get(x["payeur"], 0.0) + x["solde_apu_md"]
        s = str(x["sous_secteur"])
        par_sous_secteur[s] = par_sous_secteur.get(s, 0.0) + x["solde_apu_md"]
    return {"scenario": payload.get("scenario"), "annee": premiere,
            "vue": VUE_PREMIERE_ANNEE, "commit": payload.get("commit"),
            "cout_md": cout, "lignes": lignes, "par_payeur": par_payeur,
            "par_sous_secteur": par_sous_secteur,
            "menages_deciles_md": menages_deciles,
            "employeurs": qui if e else None,
            "non_reparti_md": -cout - somme,
            "non_reparti": (
                "le coût de la passe moins la somme des lignes, au signe d'un solde : les "
                "salaires que la passe fait payer (le brut privé d'un Smic, la "
                "rémunération publique), ce que la cascade des prestations fait hors des "
                "modules, l'écart de l'identité des comptes (D-093) ; le rapport ne le "
                "détaille pas")}


def tous(racine: Path | None = None) -> dict[str, Any]:
    """La ventilation de la première année de chaque rapport d'étude commité qui en a
    une : {scénario : `premiere_annee`}."""
    import json

    from impots import etude

    racine = racine or etude.ROOT / "reports" / "etudes"
    out = {}
    for chemin in sorted(racine.glob("presidentielle_*/**/predictif_*.json")):
        prem = chemin.with_name(chemin.name.replace("predictif_", "premiere_annee_"))
        if not prem.exists():
            continue
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        out[payload["scenario"]] = premiere_annee(
            payload, json.loads(prem.read_text(encoding="utf-8")))
    return out


def _main(argv: Sequence[str] | None = None) -> int:
    import json
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    d = tous()
    if args and args[0] == "ecrire":
        from impots import etude

        chemin = etude.ROOT / "reports" / "jumeau" / "ventilation_premiere_annee.json"
        chemin.write_text(json.dumps({"decision": "D-475", "scenarios": d},
                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(chemin)
        return 0
    for s, v in d.items():
        pp = ", ".join(f"{k} {x:+.3f}" for k, x in v["par_payeur"].items())
        print(f"{s}: coût {v['cout_md']:+.3f} ; {pp} ; non réparti {v['non_reparti_md']:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
