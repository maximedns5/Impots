"""Les mesures (CADRE.md §5) : ce qui entre dans le jumeau, par son choc statique.

Une `Mesure` porte un identifiant, un libellé, son auteur, ses années d'effet et ses chocs
statiques par année, en Md€ :

* sur les catégories du compte des APU (`chocs`, signe du moteur : un coût est positif) ;
* sur les instruments de Mésange (`impulsions`, signe expansionniste, comme
  `shocks.Impulse.by_instrument`) ;
* sur les prélèvements des entreprises et du capital de la passe (`prelevements`,
  recettes positives), la CVAE et la C3S comprises, et sur ceux que lit le canal des
  créations (`prelevements_canal`, quand ils diffèrent : sans elles depuis D-440 ;
  `prelevements_lus`, D-443) ;
* sur les ménages par décile et les entreprises par impôt (`menages`, `entreprises`),
  portés pour les lots 4 et 2, que le lot 1 ne lit pas ; un rapport ne les porte que
  pour sa première année et sa vue figée (`ventilations`, D-412) ; les années suivantes,
  sur demande, par la convention nommée « parts_premiere_annee » (`CONVENTION_PARTS`,
  D-414), portée sur chaque nombre qu'elle touche (`Mesure.conventions`).

TROIS ORIGINES, et aucune autre. `depuis_rapport` lit le choc d'une passe déjà faite sur la
population, une fois, et garde son rapport et son commit : son coût mécanique et ses
recettes de comportement à θ (les statistiques suffisantes des canaux, D-336), que le
rapport ne ventile pas entre catégories et qui vont donc sur « mesures_non_ventilees ».
`hypothese` déclare une loi directement, pour les curseurs : chaque trajectoire qui la lit
le dit (`Mesure.avertissement`). `OBSERVE` (lot 6, D-417) porte un choc lu dans les
comptes publiés pour rejouer l'histoire (`jumeau.rejeu_histoire`) : la variation d'un
taux apparent ou d'une dépense, datée par la base des mesures votées, sans aucun montant
officiel de mesure. Le jumeau ne relance jamais OpenFisca dans un pas.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from impots.jumeau.champs import DEPENSES, IMPULSIONS, RECETTES
from impots.predictif import rejouer
from impots.predictif.creations import PRODUCTION as HORS_CANAL

#: Les catégories qu'un choc déclaré peut toucher : celles du compte des APU, hors les
#: deux champs que seuls les blocs écrivent.
CATEGORIES = tuple(c for c in (*RECETTES, *DEPENSES)
                   if c not in ("solde_induit", "mesures_non_ventilees"))
INSTRUMENTS = tuple(i.removeprefix("impulsion_") for i in IMPULSIONS)
RAPPORT, HYPOTHESE, OBSERVE = "rapport", "hypothese", "observe"
EURO = 1e9
"""Les rapports sont en euros, le jumeau en Md€."""


class MesureError(ValueError):
    """Une mesure qui ne peut pas entrer telle quelle."""


@dataclass(frozen=True)
class Mesure:
    identifiant: str
    libelle: str
    auteur: str
    origine: str
    annees: tuple[int, ...]
    chocs: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    impulsions: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    prelevements: Mapping[int, float] = field(default_factory=dict)
    """Les prélèvements des entreprises et du capital de la passe, Md€, recettes
    positives, la CVAE et la C3S comprises : ce que les lots 2 et 4 ventilent (D-443)."""
    prelevements_canal: Mapping[int, float] | None = None
    """Ceux que lit le canal des créations, quand ils diffèrent de `prelevements` : un
    rapport dont le canal ne lit plus la CVAE ni la C3S (D-440). Absent, le canal lit
    `prelevements`."""
    couts: Mapping[int, float] = field(default_factory=dict)
    """Le coût mécanique de la passe, Md€, signe du moteur (rapport seulement)."""
    canaux: Mapping[int, Mapping[str, Any] | None] = field(default_factory=dict)
    """Les statistiques suffisantes des canaux de recettes, en euros, par année."""
    lignes: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Les lignes θ du comportement que le rapport réclame."""
    macro: Mapping[str, Any] | None = None
    """Les tables de Mésange des instruments que le rapport lit."""
    creations: Mapping[str, Any] | None = None
    """Les paramètres du canal des créations, tels que le rapport les porte."""
    report: str | None = None
    """« part_pib_constante » : la première année tenue en part du PIB de référence."""
    menages: Mapping[int, Any] | None = None
    """{année : {"deciles": 10 Md€, gain des ménages positif}} (lot 4)."""
    entreprises: Mapping[int, Any] | None = None
    """{année : {impôt : Md€, recettes positives}} (lot 2, `blocs.entreprises`)."""
    rapport: str | None = None
    commit: str | None = None
    non_portes: Mapping[str, str] = field(default_factory=dict)
    """Ce que le rapport ne porte pas, et pourquoi : absent, jamais un zéro (D-412)."""
    conventions: Mapping[str, Mapping[int, str]] = field(default_factory=dict)
    """{"entreprises" | "menages" : {année : convention}} : les nombres qu'une
    convention nommée a faits, et non le rapport (D-414)."""
    part_emplois_publics: Mapping[int, float] = field(default_factory=dict)
    """{année : s} : la part de ΔD1 des APU de l'année qui fait des emplois publics,
    quand la mesure la porte elle-même (D-418) : 1 pour des créations de postes, 0 pour
    un point d'indice (tout en traitements). Absente, le bloc `emploi_public` lit θ."""
    travail: Mapping[int, Mapping[str, Any]] | None = None
    """{année : {"smic": coefficient, "passe": bool}} : une hausse du Smic que lit le bloc
    `travail` (D-478) ; "passe", la loi est déjà dans la passe de la première année."""

    def __post_init__(self) -> None:
        if not self.identifiant:
            raise MesureError("une mesure sans identifiant ne se décompose pas")
        if self.origine not in (RAPPORT, HYPOTHESE, OBSERVE):
            raise MesureError(f"origine « {self.origine} » : « rapport », « hypothese » ou "
                              f"« observe »")
        if self.origine == RAPPORT and not (self.rapport and self.commit):
            raise MesureError(f"mesure « {self.identifiant} » tirée d'un rapport sans son "
                              f"rapport et son commit : son choc ne se retrouverait pas")
        for annee, chocs in self.chocs.items():
            inconnues = sorted(set(chocs) - set(CATEGORIES))
            if inconnues:
                raise MesureError(f"mesure « {self.identifiant} », {annee} : catégories "
                                  f"inconnues du compte des APU {inconnues}")
        for annee, impulsions in self.impulsions.items():
            inconnus = sorted(set(impulsions) - set(INSTRUMENTS))
            if inconnus:
                raise MesureError(f"mesure « {self.identifiant} », {annee} : instruments "
                                  f"de Mésange inconnus {inconnus}")
        if self.report not in (None, rejouer.CARRY):
            raise MesureError(f"convention de report « {self.report} » inconnue")
        for annee, part in self.part_emplois_publics.items():
            if not 0.0 <= float(part) <= 1.0:
                raise MesureError(f"mesure « {self.identifiant} », {annee} : part des "
                                  f"emplois publics {part} hors de [0 ; 1]")
            if not (self.chocs.get(annee) or {}).get("apu_d_d1"):
                raise MesureError(f"mesure « {self.identifiant} », {annee} : une part des "
                                  f"emplois publics sans rémunérations des APU (apu_d_d1)")

    @property
    def avertissement(self) -> str | None:
        if self.origine == HYPOTHESE:
            return (f"Loi hypothétique « {self.libelle} » ({self.identifiant}) : déclarée "
                    f"directement, sans passe sur la population ; chaque nombre qu'elle "
                    f"touche est une hypothèse.")
        if self.origine == OBSERVE:
            return (f"Choc observé « {self.libelle} » ({self.identifiant}) : lu dans les "
                    f"comptes publiés et daté par la base des mesures votées (D-417), "
                    f"sans passe sur la population ni montant officiel de mesure.")
        return None

    @classmethod
    def depuis_rapport(cls, payload: Mapping[str, Any], *, vue: str, identifiant: str,
                       libelle: str, auteur: str, rapport: str,
                       commit: str | None = None,
                       premiere_annee: Mapping[str, Any] | None = None,
                       convention: str | None = None) -> Mesure:
        """La mesure d'un rapport du chemin annuel, ou d'une première année reportée
        (`annuel.carried_payload`), dans la vue `vue` ; ce que `rejouer.chemin` lit.

        Avec `premiere_annee`, le rapport de la première année de la même étude
        (`premiere_annee_*.json`), elle porte aussi, pour cette année seule, les chocs
        par impôt des entreprises (`entreprises`) et par décile des ménages (`menages`),
        quand ce rapport les porte (`ventilations`, D-412). Ce qu'il ne porte pas reste
        absent, et `non_portes` dit pourquoi.

        Avec `convention="parts_premiere_annee"` (D-414), les années suivantes sont
        ventilées aux parts de la première (`etendre`), et `conventions` le dit pour
        chaque année et chaque axe qu'elle touche."""
        if convention not in (None, CONVENTION_PARTS):
            raise MesureError(f"convention « {convention} » inconnue ({CONVENTION_PARTS})")
        if vue not in rejouer.VIEWS:
            raise MesureError(f"vue « {vue} » inconnue ({sorted(rejouer.VIEWS)})")
        rejeu = rejouer._rejeu(payload)
        rows = payload["years"]
        report = payload.get("carry")
        if report not in (None, rejouer.CARRY):
            raise MesureError(f"convention de report « {report} » inconnue")
        if report and len(rows) != 1:
            raise MesureError("un rapport reporté porte sa seule première année")
        premiere = int(rows[0]["year"])
        annees = (tuple(range(premiere, premiere + int(payload["horizon"]))) if report
                  else tuple(int(r["year"]) for r in rows))
        stats = {int(r["year"]): r["statistiques"][vue] for r in rows}
        couts = {int(r["year"]): float(r[rejouer.VIEWS[vue]]) / EURO for r in rows}
        avec_canaux = rejeu["behavioural"] and all(s.get("canaux") is not None
                                                   for s in stats.values())
        canaux = {a: (s["canaux"] if avec_canaux else None) for a, s in stats.items()}
        impulsions = {a: {i: float(v) / EURO for i, v in (s["impulses"] or {}).items()}
                      for a, s in stats.items()} if rejeu["looped"] else {}
        creations = rejeu.get("creations")
        prelevements, canal, note = prelevements_lus(payload, vue)
        entreprises, menages, non_portes = ventilations(
            payload, premiere_annee, vue=vue, premiere=premiere, annees=annees,
            prelevements=prelevements, canal=canal)
        if note:
            non_portes["prelevements"] = note
        conventions: dict[str, dict[int, str]] = {}
        if convention is not None:
            entreprises, menages, non_portes, conventions = etendre(
                entreprises, menages, non_portes, premiere_annee, premiere=premiere,
                annees=annees, couts=couts, prelevements=prelevements)
        return cls(identifiant=identifiant, libelle=libelle, auteur=auteur,
                   origine=RAPPORT, annees=annees, impulsions=impulsions,
                   prelevements=prelevements, prelevements_canal=canal, couts=couts,
                   canaux=canaux,
                   entreprises=entreprises, menages=menages, non_portes=non_portes,
                   conventions=conventions, lignes=dict(rejeu["lignes"]), macro=rejeu["macro"] if rejeu["looped"]
                   else None, creations=dict(creations["parametres"]) if creations
                   else None, report=report, rapport=rapport,
                   commit=commit or payload.get("commit"))

    @classmethod
    def hypothese(cls, identifiant: str, libelle: str, *,
                  chocs: Mapping[int, Mapping[str, float]],
                  impulsions: Mapping[int, Mapping[str, float]] | None = None,
                  prelevements: Mapping[int, float] | None = None,
                  macro: Mapping[str, Any] | None = None,
                  creations: Mapping[str, Any] | None = None,
                  auteur: str = "loi hypothétique",
                  part_emplois_publics: Mapping[int, float] | None = None) -> Mesure:
        """Une loi déclarée directement, en Md€ ; ses années sont celles de ses chocs.
        `part_emplois_publics`, la part de ses rémunérations des APU qui fait des emplois
        (D-418), quand la loi la dit."""
        annees = sorted({*chocs, *(impulsions or {}), *(prelevements or {})})
        if not annees:
            raise MesureError(f"loi hypothétique « {identifiant} » sans aucun choc")
        return cls(identifiant=identifiant, libelle=libelle, auteur=auteur,
                   origine=HYPOTHESE, annees=tuple(annees), chocs=dict(chocs),
                   impulsions=dict(impulsions or {}), prelevements=dict(prelevements or {}),
                   macro=macro, creations=creations,
                   part_emplois_publics=dict(part_emplois_publics or {}))


def prelevements_lus(payload: Mapping[str, Any], vue: str
                     ) -> tuple[dict[int, float], dict[int, float] | None, str | None]:
    """Les prélèvements de la passe et ceux du canal des créations, par année, Md€,
    recettes positives (D-443) : (P, ΔP si elle diffère de P, ce qui manque).

    ΔP, `rejeu.creations.variations`, est la somme des instruments que le canal lit
    (`instruments_entreprises`, `instruments_menages`). Jusqu'à D-440, la CVAE et la C3S
    en étaient : ΔP était aussi le total des impôts des entreprises que le jumeau ventile
    (lots 2 et 4) et dont il déduit le coût des ménages (`etendre`). Depuis D-440, le
    canal ne les lit plus : ΔP ne les somme plus, et P les rajoute, X_t leur montant.

    * le canal les lit encore (un rapport d'avant D-440, la convention de D-401) : P = ΔP ;
    * le rapport porte la somme d'avant (`recalcul.instruments`, D-440 : un rapport
      refait sans passe, ses instruments retirés) : P = `variations_avant`, la somme que
      la passe a faite, au bit ;
    * sinon (une passe qui ne les a jamais sommées) : la couche des entreprises du
      chemin (`mechanical_by_layer`, son coût, signe du moteur), P_t = −coût_t quand elle
      bouge, ΔP_t sinon. Le coût de la couche porte aussi ce qu'elle coûte hors des cinq
      impôts, 59 € en 2026 chez Attal (1e-9 relatif) ; et il ne porte pas les
      prélèvements des ménages que ΔP somme (PFU, cotisations patronales) : là où il y en
      a, la ventilation est absente de toute façon (`ventilations`, le recoupement de la
      première année).

    ΔP reste ce que lit le canal : les créations suivent D-440."""
    creations = (rejouer._rejeu(payload) or {}).get("creations")
    if not creations:
        return {}, None, None
    annees = sorted(int(r["year"]) for r in payload["years"])
    canal = dict(zip(annees, (float(v) / EURO for v in creations["variations"][vue]),
                     strict=True))
    lus = list(creations["parametres"]["instruments_entreprises"])
    hors = [i for i in HORS_CANAL if i not in lus]
    if not hors:
        return canal, None, None
    marque = (payload.get("recalcul") or {}).get("instruments") or {}
    avant = (marque.get("variations_avant") or {}).get(vue)
    if avant is not None and set(hors) <= set(marque.get("retires") or ()):
        return dict(zip(annees, (float(v) / EURO for v in avant), strict=True)), canal, None
    couches = [(r.get("mechanical_by_layer") or {}).get(vue) for r in payload["years"]]
    if any(c is None or "entreprises" not in c for c in couches):
        return canal, canal, (
            f"le canal ne lit pas {', '.join(hors)} (D-440) et le rapport ne porte ni la "
            f"somme d'avant ni le coût de sa couche des entreprises : les prélèvements "
            f"sont ceux du canal, sans elles")
    totaux = {}
    for a, c in zip(annees, couches, strict=True):
        cout = float(c["entreprises"])
        totaux[a] = -cout / EURO if cout else canal[a]
    return totaux, canal, None


#: La vue dont la première année est la passe du rapport `premiere_annee_*.json` : la
#: population figée de l'année (son coût est, à l'euro près, celui du chemin figé).
VUE_PREMIERE_ANNEE = "figee"
#: L'écart toléré entre deux nombres de la même passe, en euros : ils sont égaux au bit
#: dans les rapports commités ; un écart plus grand dit que ce n'est pas la même passe.
EURO_PRES = 1.0


def _passes(premiere_annee: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Les passes du rapport de la première année, {"menages" | "entreprises" : réponse,
    requête} : une réponse mixte en porte deux, les autres une."""
    sorte, reponse, requete = (premiere_annee.get("kind"), premiere_annee["response"],
                               premiere_annee["request"])
    if sorte == "mixte":
        return {k: {"reponse": reponse[k], "requete": requete[k]}
                for k in ("menages", "entreprises")}
    if sorte in ("menages", "entreprises"):
        return {sorte: {"reponse": reponse, "requete": requete}}
    raise MesureError(f"rapport de première année de sorte « {sorte} » inconnue")


def ventilations(payload: Mapping[str, Any], premiere_annee: Mapping[str, Any] | None, *,
                 vue: str, premiere: int, annees: tuple[int, ...],
                 prelevements: Mapping[int, float],
                 canal: Mapping[int, float] | None = None
                 ) -> tuple[dict[int, Any] | None, dict[int, Any] | None, dict[str, str]]:
    """Les chocs par impôt des entreprises et par décile des ménages qu'un rapport porte
    (D-412), et ce qu'il ne porte pas.

    CE QUE LES RAPPORTS PORTENT. Le rapport du chemin annuel (`predictif_*.json`) ne
    porte, par année, que le coût, les impulsions et la somme des prélèvements que lit le
    canal des créations ; ni impôt par impôt, ni décile. Le rapport de la première année
    (`premiere_annee_*.json`) porte, pour cette année et pour la population figée, les
    écarts par impôt de la passe des entreprises (`deltas`, recettes positives, en euros)
    et le gain moyen par décile de la passe des ménages (`deciles`). Donc :

    * seule la première année, et seule la vue figée, sont ventilées ; les autres années
      et la vue vieillie restent absentes ;
    * les entreprises : les impôts que le rapport nomme pour le canal des créations
      (`instruments_entreprises` : IS, contribution sociale sur l'IS, CEBGE), et la CVAE
      et la C3S, que le canal ne lit plus depuis D-440 mais que la passe porte (D-443),
      en Md€, quand la somme des prélèvements du canal, cette année-là (`canal`, ΔP ;
      `prelevements` s'il n'est pas donné), est celle de ses impôts à l'euro près. Sinon, la différence est faite des prélèvements des ménages que le
      lot 2 lit aussi (cotisations patronales nettes des allègements, PFU, prélèvements
      sociaux du capital), que le rapport ne ventile pas : les entreprises restent
      absentes, et le lot 2 refuse la mesure plutôt que de lire un zéro ;
    * les ménages : mean_delta × n_households par décile (`menages_depuis_deciles`).
      Une réforme du Smic laisse les ménages absents : le Smic réel efficace que lit le
      bloc des salaires n'est pas la revalorisation de la requête sans hypothèse.

    Le rapport de la première année doit être celui de la même passe : même commit, même
    scénario, même année, et son coût celui du chemin figé à l'euro près ; sinon refusé.
    """
    non_portes: dict[str, str] = {}
    if premiere_annee is None:
        texte = ("le rapport du chemin annuel ne porte ni ses prélèvements par impôt ni "
                 "ses chocs par décile ; le rapport de la première année n'est pas fourni")
        return None, None, {"entreprises": texte, "menages": texte}
    if premiere_annee.get("commit") != payload.get("commit"):
        raise MesureError(f"première année au commit {premiere_annee.get('commit')}, "
                          f"chemin au commit {payload.get('commit')} : pas la même passe")
    if premiere_annee.get("scenario") != payload.get("scenario"):
        raise MesureError(f"première année du scénario « {premiere_annee.get('scenario')} »"
                          f", chemin de « {payload.get('scenario')} »")
    passes = _passes(premiere_annee)
    for nom, passe in passes.items():
        if int(passe["requete"]["year"]) != premiere:
            raise MesureError(f"passe des {nom} de {passe['requete']['year']}, chemin "
                              f"commençant en {premiere}")
    cout = sum(float(p["reponse"]["reform_cost"]) for p in passes.values())
    figee = float(payload["years"][0]["mechanical_frozen_eur"])
    if abs(cout - figee) > EURO_PRES:
        raise MesureError(f"première année de coût {cout:.0f} €, chemin figé de "
                          f"{figee:.0f} € en {premiere} : pas la même passe")
    if len(annees) > 1:
        non_portes["annees"] = (f"{annees[1]} à {annees[-1]} : le rapport ne ventile que sa "
                                f"première année, {premiere}")
    if vue != VUE_PREMIERE_ANNEE:
        texte = (f"la première année ventilée est la passe de la population figée ; la vue "
                 f"« {vue} » n'a pas de ventilation publiée")
        return None, None, {**non_portes, "entreprises": texte, "menages": texte}

    entreprises = None
    creations = (payload.get("rejeu") or {}).get("creations")
    canal = prelevements if canal is None else canal
    if not creations or premiere not in canal:
        non_portes["entreprises"] = ("le rapport ne porte pas la somme des prélèvements de "
                                     "sa première année : rien à recouper")
    else:
        lus = list(creations["parametres"]["instruments_entreprises"])
        noms = [*lus, *(i for i in HORS_CANAL if i not in lus)]
        deltas = (passes["entreprises"]["reponse"]["deltas"] if "entreprises" in passes
                  else {})
        par_impot = {i: float(deltas.get(i, 0.0) or 0.0) for i in noms}
        reste = canal[premiere] * EURO - sum(par_impot[i] for i in lus)
        if abs(reste) > EURO_PRES:
            non_portes["entreprises"] = (
                f"{reste / EURO:+.3f} Md€ de prélèvements des ménages que lit le lot 2 "
                f"(cotisations patronales nettes, PFU, prélèvements sociaux du capital) en "
                f"{premiere}, que le rapport ne ventile pas")
        else:
            entreprises = {premiere: {i: v / EURO for i, v in par_impot.items()}}

    menages = None
    if "menages" not in passes:
        non_portes["menages"] = "la première année n'a pas de passe des ménages"
    else:
        from impots.jumeau.blocs.menages import menages_depuis_deciles

        requete = passes["menages"]["requete"]
        smic = sorted(k for k in (requete.get("reform") or {}) if k.startswith("smic"))
        deciles = passes["menages"]["reponse"].get("deciles")
        if smic:
            non_portes["menages"] = (f"réforme du Smic ({', '.join(smic)}) : le Smic réel "
                                     f"efficace du bloc des salaires ne se lit pas sans "
                                     f"hypothèse dans la requête")
        elif not deciles:
            non_portes["menages"] = "la passe des ménages ne porte pas ses déciles"
        else:
            menages = {premiere: {"deciles": menages_depuis_deciles(deciles)}}
    return entreprises, menages, non_portes


#: La convention de ventilation des années suivantes (D-414) : chaque année du chemin,
#: le total du rapport est ventilé par impôt et par décile aux parts de la première.
CONVENTION_PARTS = "parts_premiere_annee"
TEXTE_CONVENTION = (
    "ventilé par la convention « parts_premiere_annee » (D-414) : le total de l'année du "
    "chemin annuel aux parts de la première année figée, pas une passe")


def etendre(entreprises: dict[int, Any] | None, menages: dict[int, Any] | None,
            non_portes: dict[str, str], premiere_annee: Mapping[str, Any] | None, *,
            premiere: int, annees: tuple[int, ...], couts: Mapping[int, float],
            prelevements: Mapping[int, float]
            ) -> tuple[dict[int, Any] | None, dict[int, Any] | None, dict[str, str],
                       dict[str, dict[int, str]]]:
    """La convention « parts_premiere_annee » (D-414), décidée par le responsable du
    projet à la place d'une passe nouvelle par année.

    LES TOTAUX DE CHAQUE ANNÉE sont ceux que le chemin annuel porte, dans la vue de la
    mesure : P_t, la somme des prélèvements du canal des créations (recettes positives),
    et le coût des ménages : C^m_t = coût_t + P_t quand la première année a une passe des
    entreprises (le coût, signe du moteur, moins celui des entreprises, −P_t ; il porte
    aussi ce que la passe des entreprises coûte hors des cinq impôts du canal, 59 € en
    2026 pour le programme d'Attal), C^m_t = coût_t sinon (les prélèvements sont alors
    ceux des ménages, dans leur coût).

    LES PARTS sont celles de la première année figée : s_i = P_{i,1} / P_1 pour l'impôt i,
    g_d = G_{d,1} / C^m_1 pour le décile d (G le choc par décile). Pour t > 1 :

        P_{i,t} = s_i P_t,      G_{d,t} = g_d C^m_t

    Ce n'est pas une passe : la structure des prélèvements et des gagnants d'une année
    est tenue sur dix ans. Chaque nombre qu'elle fait est nommé dans `conventions`. Elle
    est REFUSÉE là où les parts n'existent pas, et ce qui manque reste absent, dit dans
    `non_portes` : une première année sans ventilation (une réforme du Smic, des
    cotisations que le rapport ne ventile pas, la vue vieillie, un rapport sans sa
    première année), un total de la première année nul quand une année suivante ne l'est
    pas, un coût des ménages que le chemin ne sépare pas de celui des entreprises."""
    conventions: dict[str, dict[int, str]] = {}
    non_portes = dict(non_portes)
    suivantes = [a for a in annees if a != premiere]
    if not suivantes:
        return entreprises, menages, non_portes, conventions
    refus: list[str] = []

    if entreprises is None:
        refus.append("entreprises")
        non_portes["entreprises"] = (f"{non_portes.get('entreprises', '')} ; la convention "
                                     f"« {CONVENTION_PARTS} » n'a pas de parts").lstrip(" ;")
    else:
        total = sum(entreprises[premiere].values())
        if total == 0.0 and any(prelevements.get(a, 0.0) for a in suivantes):
            refus.append("entreprises")
            non_portes["entreprises"] = (f"prélèvements nuls en {premiere}, pas en "
                                         f"{suivantes} : pas de parts pour la convention")
            entreprises = {premiere: entreprises[premiere]}
        else:
            parts = {i: (v / total if total else 0.0)
                     for i, v in entreprises[premiere].items()}
            entreprises = {premiere: entreprises[premiere], **{
                a: {i: s * prelevements.get(a, 0.0) for i, s in parts.items()}
                for a in suivantes}}
            conventions["entreprises"] = dict.fromkeys(suivantes, CONVENTION_PARTS)

    if menages is None:
        refus.append("menages")
        non_portes["menages"] = (f"{non_portes.get('menages', '')} ; la convention "
                                 f"« {CONVENTION_PARTS} » n'a pas de parts").lstrip(" ;")
    else:
        passes = _passes(premiere_annee) if premiere_annee else {}
        deciles = list(menages[premiere]["deciles"])
        if "entreprises" in passes and entreprises is None:
            # Des prélèvements des ménages mêlés à ceux des entreprises (des cotisations
            # patronales que le rapport ne ventile pas) : le coût des ménages de chaque
            # année ne se sépare pas de celui des entreprises.
            cout = None
        elif "entreprises" in passes:
            cout = {a: couts[a] + prelevements.get(a, 0.0) for a in annees}
        else:
            cout = dict(couts)
        if cout is None:
            refus.append("menages")
            non_portes["menages"] = (
                "le chemin ne sépare pas, après la première année, le coût des ménages de "
                "celui des entreprises (leurs prélèvements ne sont pas ventilés) : pas de "
                "total pour la convention")
        elif cout[premiere] == 0.0 and any(cout[a] for a in suivantes):
            refus.append("menages")
            non_portes["menages"] = (f"coût des ménages nul en {premiere}, pas en "
                                     f"{suivantes} : pas de parts pour la convention")
        else:
            echelle = {a: (cout[a] / cout[premiere] if cout[premiere] else 0.0)
                       for a in suivantes}
            menages = {premiere: menages[premiere], **{
                a: {"deciles": [g * echelle[a] for g in deciles]} for a in suivantes}}
            conventions["menages"] = dict.fromkeys(suivantes, CONVENTION_PARTS)

    if conventions:
        non_portes.pop("annees", None)
        if refus:
            non_portes["annees"] = (f"{suivantes[0]} à {suivantes[-1]} : {', '.join(refus)} "
                                    f"sans parts, absents ; le reste {TEXTE_CONVENTION}")
    return entreprises, menages, non_portes, conventions
