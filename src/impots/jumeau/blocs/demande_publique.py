"""Le bloc `demande_publique` (D-411) : les achats des APU d'une mesure, dans les emplois.

Comptable, sans comportement ni θ. Le bloc `mesures` inscrit une dépense sur le compte des
APU (t. 3.201) ; en mode réduit, Mésange en porte la demande par ses variantes de dépense
(« investissement_public », « depense_publique »). En mode structurel, rien ne la portait
dans les emplois du PIB : ce bloc le fait, par les définitions du SEC 2010 et de la
t. 1.101, pour la mesure m et l'année t (Md€) :

    Δc_apu    = ΔP2 + ΔD1 + ΔD29 + ΔD632     la production non marchande se valorise à
                                            ses coûts (consommations intermédiaires,
                                            rémunérations, impôts sur la production), et
                                            les transferts sociaux en nature de produits
                                            marchands sont consommés par les APU
    Δfbcf_apu = ΔP51g

Côté revenus : ΔD1 en rémunérations, ΔD29 en impôts sur la production ; ΔP2, ΔD632 et
ΔP51g sont des achats aux producteurs marchands, dont la valeur ajoutée n'est pas ventilée
(revenus non ventilés). La consommation de capital fixe des APU, qui entre aussi dans leur
production non marchande, ne bouge pas avec une mesure : elle n'est pas lue. Les autres
dépenses (prestations en espèces D62, subventions D3, transferts) ne sont pas des emplois :
elles passent par les revenus (le choc par décile des ménages, lot 4).

Canal « demande_publique », de Mésange (`remplace`), pour tout instrument : avec `mesange`,
refusé. Le PIB est fermé par le cadre (D-411).
"""

from __future__ import annotations

from typing import Any

from impots.jumeau.pas import Contexte

#: Les dépenses des APU qui sont un emploi du PIB, et l'emploi où elles vont.
VERS_EMPLOIS = {"apu_d_p2": "c_apu", "apu_d_d1": "c_apu", "apu_d_d29": "c_apu",
                "apu_d_d632": "c_apu", "apu_d_p51g": "fbcf_apu"}
#: Le revenu de chacune.
VERS_REVENUS = {"apu_d_p2": "revenus_non_ventiles", "apu_d_d1": "remunerations",
                "apu_d_d29": "impots_production", "apu_d_d632": "revenus_non_ventiles",
                "apu_d_p51g": "revenus_non_ventiles"}


class DemandePublique:
    nom = "demande_publique"
    lit = tuple(VERS_EMPLOIS)
    ecrit = ("c_apu", "fbcf_apu", "remunerations", "impots_production",
             "revenus_non_ventiles")
    thetas: tuple[str, ...] = ()
    remplace = ("demande_publique",)

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        for depense in self.lit:
            ctx.lire(depense)
            for (origine, m), v in ctx.courant.de(depense).items():
                if origine != "mesures" or m == "":
                    continue
                for champ_ in (VERS_EMPLOIS[depense], VERS_REVENUS[depense]):
                    parts = out[champ_]
                    parts[m] = parts[m] + v if m in parts else v
        return out
