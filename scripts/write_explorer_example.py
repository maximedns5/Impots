#!/usr/bin/env python3
"""Render docs/EXPLORER_EXAMPLE.md — l'exemple de bout en bout que §4.4 met à la DoD.

Aucun chiffre n'est saisi dans le document : tout est calculé ici, depuis la table
d'ancres et depuis des entrées de scénario déclarées comme telles. Même règle que
scripts/write_instrument_coverage.py, et pour la même raison — un document qui dérive
du code qu'il décrit sera cru le jour où ça compte.

**Ce script lit la VRAIE table d'ancres quand elle existe.** Sur une machine sans
`data/raw/`, il retombe sur la fixture des tests, dont les montants sont inventés, et
la bannière du document change en conséquence. Le jour où le propriétaire remplit
`data/processed/receipts_anchors.json`, la même commande produit le même document avec
les montants publiés et sans la bannière d'invention. C'est la seule façon de livrer
l'exemple de §4.4 aujourd'hui sans faire passer une forme pour un chiffrage.
"""

from __future__ import annotations

from pathlib import Path

from impots import explorer as ex
from impots import guards
from impots.agregats import instruments as inst
from impots.agregats.anchors import ANCHOR_TABLE, AnchorTableMissing, load_anchors
from impots.dette import path as dette

OUT = Path("docs/EXPLORER_EXAMPLE.md")
FIXTURE = Path("tests/fixtures/receipts_anchors_fixture.json")
LOG_OUT = Path("data/processed/explorer_example_search.json")

#: §4.4 : « target +20 bn de recettes mécaniques, bounds ±2 points ».
TARGET_EUR = 20e9
POINTS = 0.02
STEP = 0.02

#: Trois réglages par instrument (−2, 0, +2) sur neuf instruments font 3**9 = 19 683
#: points, au-dessus du plafond par défaut de `search()`. Le budget est donc relevé ICI,
#: explicitement, et le document affiche le nombre d'évaluations : c'est l'usage prévu
#: du paramètre. Ce que le plafond interdit, c'est la troncature SILENCIEUSE — une
#: recherche coupée en route rendrait « pas de candidat » pour une raison qui n'est pas
#: la bonne. Un pas de 1 point ferait 5**9 = 1 953 125 points et serait refusé ; la
#: bonne réponse à ce refus est d'élargir le pas, pas de retirer la garde.
BUDGET = 25_000

#: Entrées de TRAJECTOIRE. Ce ne sont pas des données : aucune n'est lue d'un fichier,
#: et elles sont ici pour que l'arithmétique de §3 ait des nombres à mouliner. Le
#: document le dit à l'endroit où elles s'affichent.
B0 = 1.10
R_NOMINAL = 0.032
G_NOMINAL = 0.028
PRIMARY_BALANCE_BASE = -0.020
PIB_SCENARIO = 3000e9
HORIZON = 5

#: Deux scénarios de dépense, §3.5. Les deux livrés par M1, nommés sur le graphique.
#: L'écart entre eux est porté par le solde primaire, seul terme que la récurrence lit.
SPENDING_DELTA = {"part_pib_constante": 0.0, "gele_en_volume": 0.004}

#: La demi-largeur de bande du §3 du document, en PART du Δ mécanique. INVENTÉE, et le
#: document l'écrit en toutes lettres : aucun des neuf instruments ne porte de bande,
#: donc le drapeau de fragilité ne peut pas se lever sur eux. Le cas est construit à la
#: main exactement comme le tueur de §4.2, dont il est la version affichable.
#:
#: Proportionnelle et non absolue parce que la première version prenait ±0,6 md€ sur une
#: cible de 0,62 md€ : TOUS les candidats ressortaient fragiles, et un drapeau qui
#: s'allume toujours est un drapeau qu'on apprend à ignorer. Le document doit montrer
#: que le drapeau DISCRIMINE, sans quoi il ne montre rien.
BAND_SHARE_ILLUSTRATIVE = 0.08


def _anchors() -> tuple[dict, str, bool]:
    """La vraie table si elle existe, sinon la fixture — et de quoi l'écrire en haut."""
    try:
        return load_anchors(), f"`{ANCHOR_TABLE}`", True
    except AnchorTableMissing:
        return load_anchors(FIXTURE), f"`{FIXTURE}`", False


def _evaluator(built: dict, frozen_bonus: float, *, band_share: float | None = None):
    """Un paquet → son Δ mécanique, par `reprice()`, instrument par instrument.

    Passe par l'engine plutôt que de multiplier des ancres à la main : c'est
    `check_base_split()` qui tourne à chaque reprise, et l'exemple doit courir sur la
    machinerie qu'il illustre, pas sur une copie de son arithmétique.
    """
    def evaluate(knobs: dict[str, float]) -> ex.Evaluation:
        aged = 0.0
        for code, factor in knobs.items():
            aged += built[code].reprice(inst.scale(factor)).delta_eur
        # La demi-largeur se prend sur la VALEUR ABSOLUE. Écrit d'abord en
        # `aged * (1 ± share)`, ce qui inverse la bande dès que le paquet coûte au lieu
        # de rapporter — et la garde `bande inversée` de l'explorateur l'a arrêté ici,
        # sur un paquet à −0,96 md€, avant que la page ne s'imprime.
        demi = abs(aged) * (band_share or 0.0)
        return ex.Evaluation(
            aged_eur=aged,
            frozen_eur=aged * (1.0 + frozen_bonus),
            band=None if band_share is None else (aged - demi, aged + demi),
            band_reason="" if band_share is not None else (
                "aucun des neuf instruments ne porte de bande : §2.3 exige une ligne de "
                "preuve vérifiée et la table n'en contient aucune pour eux"),
        )
    return evaluate


def _deltas(built: dict, knobs: dict[str, float]) -> dict[str, float]:
    return {code: built[code].reprice(inst.scale(f)).delta_eur for code, f in knobs.items()}


def _fr(x: float, decimals: int = 3, *, sign: bool = True) -> str:
    """Un NOMBRE en écriture française. Jamais appliqué à une phrase.

    La première version faisait `f"…{x:.1%} de PIB.".replace(".", ",")` sur la chaîne
    entière : le point final de la phrase devenait une virgule, et les séparateurs de
    milliers mangeaient les virgules du texte autour. Un document généré qui se
    ponctue mal se lit comme un document bâclé, et un lecteur qui doute de la
    ponctuation doute du reste.
    """
    return (f"{x:{'+' if sign else ''}.{decimals}f}"
            .replace(".", ",").replace("-", "\u2212"))


def _milliers(n: int) -> str:
    return f"{n:,}".replace(",", "\u202f")


def _pc(x: float, decimals: int = 1, *, sign: bool = False) -> str:
    """Un pourcentage, espace insécable comprise — `x` est un RATIO, pas déjà des %."""
    return _fr(x * 100, decimals, sign=sign) + "\u00a0%"


def _bn(x: float, *, sign: bool = True) -> str:
    return _fr(x / 1e9, 3, sign=sign)


def _pct(x: float) -> str:
    return _fr((x - 1.0) * 100, 0)


def _moves(knobs: dict[str, float], codes: list[str]) -> str:
    """Les instruments qui BOUGENT, nommés ; les autres sont à zéro et se taisent.

    Neuf colonnes de « +0 pt » rendraient le tableau illisible, et un tableau illisible
    est un tableau qu'on croit sur parole.
    """
    moved = [f"`{c}` {_pct(knobs[c])}" for c in codes if knobs[c] != 1.0]
    return " · ".join(moved) if moved else "*aucun*"


#: Le journal de la recherche du §2, posé par `render()` pour que `__main__` l'écrive.
#: PAS écrit depuis `render()` : le test anti-dérive appelle `render()`, et un test qui
#: dépose 9 Mo dans le dépôt à chaque exécution est un test qui salit ce qu'il vérifie.
LAST_LOG: list[ex.SearchLog] = []


def render() -> str:
    anchors, source, is_real = _anchors()
    built, missing = inst.build_all(anchors)
    codes = [s.code for s in inst.PROPORTIONAL if s.code in built]
    bounds = [ex.Bound(c, 1.0 - POINTS, 1.0 + POINTS, STEP) for c in codes]
    baselines = {c: built[c].anchor.amount_eur for c in codes}
    ceiling = ex.ceiling_eur(bounds, baselines)

    L: list[str] = []
    a = L.append

    a("# L'explorateur d'objectif, de bout en bout (§4.4)")
    a("")
    a("> **Ceci illustre une MACHINE, pas une politique.** Aucune ligne de ce document "
      "n'est une recommandation, et le paquet le mieux classé n'est pas « le meilleur » "
      "— il est le premier d'une liste triée par écart à une cible que quelqu'un a "
      "choisie. L'affirmation honnête de ce module est « voici des candidats », jamais "
      "« voici l'optimum ».")
    a("")
    if not is_real:
        a("> ### ⚠ LES MONTANTS CI-DESSOUS SONT INVENTÉS")
        a("> ")
        a(f"> Les ancres viennent de {source}, la fixture des tests, dont les montants "
          f"ont été écrits pour avoir une FORME plausible et rien d'autre. Aucun chiffre "
          f"de ce document ne dit quoi que ce soit sur la France. Il est ici pour que la "
          f"chaîne — recherche, drapeaux, partie double, trajectoire — soit visible en "
          f"entier sur une copie du dépôt sans `data/raw/`.")
        a("> ")
        a(f"> Le jour où `{ANCHOR_TABLE}` est remplie (voir `docs/M2_ANCHORS.md`), "
          f"`python scripts/write_explorer_example.py` réécrit ce même document avec les "
          f"montants publiés, et cet encadré disparaît de lui-même.")
    else:
        a(f"> Ancres lues depuis {source}, provenance vérifiée à la lecture.")
    a("")
    a(f"Généré par `scripts/write_explorer_example.py`. Aucun chiffre n'est saisi dans "
      f"ce fichier ; le journal d'itérations est écrit dans `{LOG_OUT}`.")
    a("")

    # ---------------------------------------------------------------- §1
    a("## 1. La cible de §4.4, et pourquoi elle ne peut pas être atteinte")
    a("")
    a(f"§4.4 pose « **+20 md€ de recettes mécaniques**, ±2 points sur une dizaine "
      f"d'instruments ». Les instruments disponibles sont les {len(codes)} instruments "
      f"proportionnels du seau B (§2.3).")
    a("")
    a("Avant de chercher, on calcule le **plafond arithmétique** : pour un instrument "
      "proportionnel, un facteur `f` sur une ancre `A` rapporte `(f − 1) × A`, donc le "
      "plafond du paquet vaut `Σ (f_max − 1) × A`. C'est une identité, pas un résultat "
      "de recherche.")
    a("")
    a("| | |")
    a("|---|---|")
    a(f"| Somme des ancres, {len(codes)} instruments | "
      f"{_bn(sum(built[c].anchor.amount_eur for c in codes), sign=False)} md€ |")
    a(f"| Plafond à +2 points sur les {len(codes)} | **{_bn(ceiling)} md€** |")
    a(f"| Cible demandée | {_bn(TARGET_EUR)} md€ |")
    a(f"| Rapport cible / plafond | ×{_fr(TARGET_EUR / ceiling, 1, sign=False)} |")
    a("")
    unreachable, log0 = ex.search(target_eur=TARGET_EUR, bounds=bounds,
                                  evaluate=_evaluator(built, 0.0),
                                  max_evaluations=BUDGET)
    a(f"La recherche rend **{len(unreachable)} candidat** après "
      f"{_milliers(log0.evaluations)} évaluations.")
    a("")
    a("**Et ce n'est pas un échec de la recherche.** C'est la distinction que "
      "`ceiling_eur()` existe pour rendre lisible : un tableau vide peut vouloir dire "
      "« la cible est hors d'atteinte par arithmétique » ou « elle est atteignable et la "
      "grille l'a manquée », et sans le plafond les deux s'affichent pareil — le lecteur "
      "accuse alors toujours la recherche. Ici la cible vaut "
      f"{TARGET_EUR / ceiling:.0f} fois ce que ±2 points sur ces instruments peuvent "
      f"produire. Aucun pas de grille plus fin n'y changera rien.")
    a("")
    a("C'est aussi le fait le plus utile de la page : **la « tranche de couverture » du "
      "§2.3.3 élargit ce que le laboratoire sait chiffrer, elle ne donne pas de quoi "
      "boucler une dizaine de milliards.** Les ordres de grandeur de cette taille sont "
      "du côté des grandes assiettes — TVA, CSG, IR — dont `COVERAGE_INSTRUMENTS.md` "
      "dit précisément lesquelles ne sont pas encore chiffrables ici.")
    a("")

    # ---------------------------------------------------------------- §2
    reachable = round(0.60 * ceiling, -7)
    a("## 2. Une cible atteignable, et les candidats qu'elle produit")
    a("")
    a(f"On rejoue la même machine sur une cible que les bornes peuvent atteindre : "
      f"**{_bn(reachable)} md€**, soit 60 % du plafond arithmétique.")
    a("")
    a(f"Les {len(codes)} instruments sont explorés ensemble, à trois réglages chacun "
      f"(−2, 0, +2 points) : **{_milliers(3 ** len(codes))} points de grille**. Un pas "
      f"d'un point en ferait {_milliers(5 ** len(codes))}, "
      "que `search()` **refuse** par son plafond d'évaluations plutôt que de tronquer "
      "la grille en silence — une recherche coupée en route rendrait « pas de candidat » "
      "pour une raison qui n'est pas la bonne. La bonne réponse à ce refus est "
      "d'élargir le pas et de l'écrire, ce que fait cette page.")
    a("")
    a("| bouton | ancre | plage |")
    a("|---|---|---|")
    for c in codes:
        a(f"| `{c}` — {built[c].label} | "
          f"{_bn(built[c].anchor.amount_eur, sign=False)} md€ | −2, 0, +2 points |")
    a("")

    candidates, log = ex.search(target_eur=reachable, bounds=bounds,
                                evaluate=_evaluator(built, 0.30), seed=0,
                                max_evaluations=BUDGET)
    LAST_LOG[:] = [log]
    retenus = ex.plans(candidates)
    geles = ex.frozen_only(candidates)

    a(f"**{_milliers(log.evaluations)} évaluations, {_milliers(len(candidates))} "
      f"candidats rendus, dont {_milliers(len(retenus))} plans et "
      f"{_milliers(len(geles))} qui ne referment l'écart que sur "
      f"l'affichage gelé.** Empreinte du journal : `{log.digest()[:16]}…` — deux "
      "exécutions de cette commande la partagent, sinon « rejouable à l'identique » "
      "serait une intention et non une propriété.")
    a("")
    a("Les dix premiers, triés par écart croissant à la cible :")
    a("")
    a("| # | instruments qui bougent | Δ vieilli | Δ gelé | plan ? |")
    a("|---|---|---|---|---|")
    for i, cand in enumerate(candidates[:10], start=1):
        verdict = "**oui**" if cand.meets_target else "non — *gelé seulement*"
        a(f"| {i} | {_moves(cand.knobs, codes)} | {_bn(cand.aged_eur)} md€ | "
          f"{_bn(cand.frozen_eur)} md€ | {verdict} |")
    a("")
    ex_aequo = sum(1 for c in candidates
                   if abs(c.aged_eur - candidates[0].aged_eur) < 1.0)
    a(f"**{_milliers(ex_aequo)} paquets atteignent le même Δ mécanique à l'euro près** "
      f"que celui de tête. Le chiffre mécanique ne les départage pas, et c'est "
      f"l'argument le plus direct contre « voici l'optimum » : le choix entre eux se "
      f"fait sur tout ce que ce module ne sait pas mesurer — incidence, faisabilité, "
      f"acceptabilité — et pas sur la colonne qui les classe.")
    if not is_real:
        a("")
        a("*Une réserve sur ce nombre précis* : les ancres de la fixture sont des "
          "montants ronds, donc les substitutions tombent JUSTE "
          "(0,014 + 0,016 + 0,020 = 0,050 md€). Sur des ancres publiées, les égalités "
          "exactes deviendraient des quasi-égalités. L'argument ne change pas de nature "
          "— un peloton que le modèle ne sait pas départager reste un peloton — mais le "
          "nombre ci-dessus est une propriété de la fixture, pas des instruments.")
    a("")
    a("**La colonne « Δ gelé » est la raison d'être de ce tableau.** L'affichage gelé "
      "est systématiquement le plus beau : un barème gelé « rapporte » d'autant plus que "
      "la population qu'on lui oppose est figée. Un paquet qui referme l'écart dans "
      "cette colonne et pas dans la précédente **n'est pas un plan**, et il reste affiché "
      "plutôt que retiré — le cacher le rendrait indétectable, et quelqu'un le "
      "retrouverait ailleurs en croyant l'avoir trouvé.")
    a("")

    # ---------------------------------------------------------------- §3
    a("## 3. Le drapeau de fragilité")
    a("")
    a("**Sur les neuf instruments ci-dessus, le drapeau ne peut pas se lever, et c'est "
      "un résultat.** Aucun d'eux ne porte de bande comportementale : §2.3 conditionne "
      "toute bande à une ligne de preuve vérifiée, et la table n'en contient aucune pour "
      "eux. Ce que l'explorateur affiche alors est une phrase, pas un blanc :")
    a("")
    sans_bande = candidates[0].fragility_reason
    a(f"> {sans_bande}")
    a("")
    a("La seconde moitié de cette phrase est la garde. « Pas de drapeau » sur un "
      "candidat sans bande se lirait comme « robuste » si la ligne ne le démentait pas "
      "dans le même souffle.")
    a("")
    a(f"Voici donc ce que le drapeau DONNE, sur un cas **construit à la main** : la même "
      f"recherche, avec une bande de ±{_pc(BAND_SHARE_ILLUSTRATIVE, 0)} du Δ mécanique "
      f"posée autour de chaque candidat. **Cette largeur est inventée pour la "
      f"démonstration** — c'est la version affichable du tueur de §4.2, pas un "
      f"chiffrage.")
    a("")
    fragiles_all, _ = ex.search(target_eur=reachable, bounds=bounds,
                                evaluate=_evaluator(built, 0.30,
                                                    band_share=BAND_SHARE_ILLUSTRATIVE),
                                max_evaluations=BUDGET)
    marques = ex.fragile(fragiles_all)
    solides = [c for c in fragiles_all if not c.fragile]
    a(f"Sur {_milliers(len(fragiles_all))} candidats, **{_milliers(len(marques))} "
      f"sont marqués fragiles** et {_milliers(len(solides))} ne le sont pas. Le mieux "
      f"classé est fragile :")
    a("")
    a(f"> {marques[0].fragility_reason}")
    a("")
    a("Mécaniquement il atteint la cible ; l'intervalle des preuves contient l'échec. "
      "Les deux sont vrais en même temps, et le dire est tout l'objet. Le réduire à un "
      "point central — « il rapporte X » — serait la faute que toute la phase 3 refuse.")
    a("")
    a("**Et le drapeau discrimine**, ce qui est la moitié du test : un candidat dont la "
      "bande passe entièrement au-dessus de la cible n'est pas marqué, et dit pourquoi.")
    a("")
    a(f"> {solides[0].fragility_reason}")
    a("")
    a("La première version de cette page posait une bande ABSOLUE de 0,6 md€ sur une "
      "cible de 0,62 md€ : les 2 442 candidats ressortaient fragiles. Un drapeau qui "
      "s'allume toujours est un drapeau qu'on apprend à ignorer — c'est d'ailleurs ce "
      "qu'un des tests de `test_explorer.py` interdit explicitement, et la page le "
      "violait pendant que le test passait.")
    a("")
    a("La question est posée à la **cible**, pas à zéro : un paquet visant +20 md€ dont "
      "l'intervalle va de +5 à +35 md€ est fragile bien qu'il ne s'approche jamais de "
      "zéro.")
    a("")

    # ---------------------------------------------------------------- §4
    best = retenus[0] if retenus else candidates[0]
    deltas = _deltas(built, best.knobs)
    total = sum(deltas.values())
    ledger = guards.sector_balance({}, reform_cost=-total, aggregate_deltas=deltas)
    a("## 4. La partie double, sur le candidat de tête")
    a("")
    a("Le paquet retenu pour la suite est le premier plan du tableau :")
    a("")
    a("| instrument | facteur | Δ mécanique | résidu `check_base_split` |")
    a("|---|---|---|---|")
    for c in codes:
        residu = built[c].check_base_split()
        a(f"| `{c}` | {_pct(best.knobs[c])} pt | {_bn(deltas[c])} md€ | "
          f"{'0' if residu == 0.0 else f'{residu:+.1e}'} |")
    a(f"| **total** | | **{_bn(total)} md€** | |")
    a("")
    a(f"`guards.sector_balance` referme l'identité : part agrégée "
      f"{_bn(ledger['aggregate'])} md€, **inexpliqué {ledger['unexplained']:+.0f} €**. "
      f"L'identité est vérifiée contre la somme des INSTRUMENTS, pas contre une "
      f"reconstruction du total — la première version de cette garde écrivait un côté "
      f"en fonction de l'autre et s'équilibrait à zéro en ne pouvant pas attraper le "
      f"bug pour lequel elle existait.")
    a("")
    a("**Le résidu `check_base_split` vaut 0 par construction sur ces instruments, et "
      "ce n'est pas une validation** (D-153). Pour un instrument proportionnel, la "
      "ventilation EST l'ancre : le contrôle n'a rien d'indépendant à comparer. Il reste "
      "affiché parce qu'un résidu non nul signifierait que l'assiette a été construite "
      "depuis autre chose que cette ancre.")
    a("")

    # ---------------------------------------------------------------- §5
    a("## 5. La conséquence sur la trajectoire de dette, sous deux scénarios de dépense")
    a("")
    a("> **Les entrées de cette section sont des ENTRÉES DE SCÉNARIO, pas des données.** "
      "Ni le PIB, ni le ratio d'ouverture, ni le taux implicite ne sont lus d'un "
      "fichier ici : les comptes INSEE (`insee_cn2025_pib_T1101_1103.xlsx`, "
      "`insee_dette_maastricht_detail.xlsx`) ne sont pas sur cette machine. Elles sont "
      "posées pour que l'arithmétique de §3 ait des nombres à mouliner.")
    a("")
    a("| entrée de scénario | valeur |")
    a("|---|---|")
    a(f"| Ratio dette/PIB d'ouverture | {_pc(B0, 0)} |")
    a(f"| Taux implicite nominal `r` | {_pc(R_NOMINAL)} |")
    a(f"| Croissance nominale `g` | {_pc(G_NOMINAL)} |")
    a(f"| Solde primaire de départ (déficit) | {_pc(PRIMARY_BALANCE_BASE, sign=True)} |")
    a(f"| PIB de référence | {_milliers(int(PIB_SCENARIO / 1e9))} md€ |")
    a("")
    a(f"Le paquet améliore le solde primaire de {_bn(total)} md€, soit "
      f"{_pc(total / PIB_SCENARIO, 3, sign=True)} de PIB.")
    a("")
    a("`project()` **refuse de rendre une trajectoire sans scénario de dépense nommé** : "
      "les dépenses pèsent ~57 % du PIB, seule la tranche des transferts est "
      "microsimulée, et une trajectoire où les recettes bougent et où la dépense reste "
      "tue laisserait entendre que l'impôt porte seul l'ajustement. Les deux scénarios "
      "livrés par M1 :")
    a("")
    header = ["année"]
    series: dict[str, list[dette.DebtPoint]] = {}
    for key, scen in dette.SHIPPED.items():
        pb = PRIMARY_BALANCE_BASE + total / PIB_SCENARIO + SPENDING_DELTA[key]
        years = [dette.YearInputs(year=2026 + i, r=R_NOMINAL, g=G_NOMINAL,
                                  primary_balance=pb)
                 for i in range(HORIZON)]
        series[key] = dette.project(B0, years, spending=scen)
        header.append(scen.name)
    a("| " + " | ".join(header) + " |")
    a("|---|" + "---|" * len(series))
    for i in range(HORIZON):
        row = [str(2026 + i)]
        row += [_pc(series[k][i].ratio) for k in dette.SHIPPED]
        a("| " + " | ".join(row) + " |")
    ecart = (series["gele_en_volume"][-1].ratio
             - series["part_pib_constante"][-1].ratio)
    a("")
    a(f"**{_pc(abs(ecart))} de PIB d'écart entre les deux scénarios à l'horizon "
      f"{2025 + HORIZON}**, contre "
      f"{_pc(abs(total / PIB_SCENARIO) * HORIZON, 2)} apportés par le paquet fiscal "
      f"lui-même sur la même durée.")
    a("")
    a("C'est la raison pour laquelle le refus de `project()` n'est pas une formalité : "
      "**le choix du scénario de dépense pèse plus, sur la trajectoire, que le paquet "
      "fiscal qu'on est en train d'explorer.** Une page qui afficherait la trajectoire "
      "sans nommer ce choix attribuerait à l'impôt un mouvement qui vient d'ailleurs.")
    a("")
    a(f"> {dette.BANNER}")
    a("")

    # ---------------------------------------------------------------- fin
    a("## Ce que cet exemple ne dit pas")
    a("")
    a("- **Ce n'est pas une recommandation.** La cible du §2, les bornes, le pas, la "
      "demi-largeur de bande du §3 et toutes les entrées du §5 ont été choisis pour "
      "montrer la machine.")
    a("- **Le candidat de tête n'est pas l'optimum.** C'est le premier d'une liste "
      "triée par écart à une cible choisie, sur une grille choisie.")
    a("- **Aucune sortie distributionnelle n'est possible ici.** Ces instruments sont "
      "agrégés : ils n'ont pas de population derrière eux, et `output('decile')` est "
      "refusé par son nom (§2.2).")
    if missing:
        a(f"- **{len(missing)} instruments déclarés n'ont pas d'ancre** dans la table "
          f"lue ({', '.join(f'`{m}`' for m in missing)}) et ne sont donc pas dans "
          f"l'espace de recherche.")
    a("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    text = render()
    OUT.write_text(text, encoding="utf-8")
    LAST_LOG[0].persist(LOG_OUT)
    print(f"wrote {OUT} ({len(text.splitlines())} lines) "
          f"and {LOG_OUT} ({LAST_LOG[0].evaluations} évaluations)")
