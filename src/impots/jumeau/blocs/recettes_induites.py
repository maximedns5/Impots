"""Le bloc `recettes_induites` (mode structurel, D-414) : l'IS sur les profits induits.

Comptable, sans θ. Les recettes que l'activité induite rend aux APU sont portées par les
blocs qui écrivent leur base, et ce bloc ne reprend que ce qu'aucun ne porte :

* la TVA et les accises sur la consommation induite : le bloc `consommation`, au taux
  moyen des cellules de ménages (`taux_conso`), en D2 ;
* les cotisations, la CSG, la CRDS et l'IR sur la masse salariale induite : le bloc
  `salaires`, qui la répartit entre les ménages et les APU aux taux moyens des cellules
  (D61 et D5) ; les allocations chômage, en dépense ;
* ρ ΔY sur le PIB potentiel de l'investissement, de l'implantation et de la démographie
  (`solde_induit`), ρ le taux de prélèvements du départ ;
* L'IS SUR LES PROFITS INDUITS, nulle part : c'est ce bloc.

ÉQUATION, pour la mesure m, l'année t :

    Π_{m,t} = Σ_{(champ, origine) ∈ O} ΔR_{champ, origine, m, t}
    ΔIS_{m,t} = τ_IS Π_{m,t}                        en D5 des APU (recettes)

O, les contributions qui font le profit marchand induit : l'EBE qu'écrivent la
consommation (la valeur hors TVA et accises), l'investissement (l'accélérateur) et les
salaires (la masse salariale induite, en moins), et les revenus non ventilés du commerce
(le solde extérieur) et de la demande publique (ses achats aux producteurs marchands).
Ce que les blocs du PIB potentiel écrivent n'y est pas : ils portent déjà ρ ΔY.
τ_IS = 6,668 %, l'IS avant crédits et la contribution sociale sur les bénéfices de 2024
(t. 3.217, 69,121 Md€) sur l'EBE et le revenu mixte de 2024 (t. 1.105, 1 036,606 Md€) :
`parametres/recettes_induites.yaml`. Un taux apparent, moyen, sur une base large (le
revenu mixte et l'EBE des ménages y sont), payé l'année même (l'IS se paie en partie
l'année suivante : non modélisé, dit). Linéaire : une baisse de profit rend une baisse
d'IS. L'IS ne revient pas aux ménages et ne change aucun emploi : le bloc tourne après la
boucle simultanée et n'écrit que le compte des APU.

Canal « recettes_induites_profits » (`remplace`), de Mésange, dont les variantes portent
ces recettes dans leur solde : avec `mesange`, refusé.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from impots.jumeau.pas import Contexte

FICHIER = Path(__file__).resolve().parents[1] / "parametres" / "recettes_induites.yaml"


def charger(chemin: Path | None = None) -> dict[str, Any]:
    """Le taux et les origines du profit induit, lus une fois, jamais dans un pas."""
    d = yaml.safe_load((chemin or FICHIER).read_text(encoding="utf-8"))
    return {"taux": float(d["impot_societes"]["taux"]["valeur"]),
            "origines": {champ_: tuple(o) for champ_, o in
                         d["impot_societes"]["origines"].items()}}


class RecettesInduites:
    nom = "recettes_induites"
    ecrit = ("apu_r_d5",)
    thetas: tuple[str, ...] = ()
    remplace = ("recettes_induites_profits",)

    def __init__(self, valeurs: Mapping[str, Any] | None = None) -> None:
        v = valeurs if valeurs is not None else charger()
        self.taux = float(v["taux"])
        self.origines = {c: frozenset(o) for c, o in v["origines"].items()}
        self.lit = tuple(self.origines)

    def profits(self, ctx: Contexte) -> dict[str, Any]:
        """Π_{m,t} par mesure, Md€."""
        out: dict[str, Any] = {}
        for champ_, origines in self.origines.items():
            ctx.lire(champ_)
            for (origine, m), v in sorted(ctx.courant.de(champ_).items()):
                if m and origine in origines:
                    out[m] = out[m] + v if m in out else v
        return out

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        return {"apu_r_d5": {m: self.taux * v for m, v in self.profits(ctx).items()}}
