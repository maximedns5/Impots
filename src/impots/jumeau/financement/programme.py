"""Un programme chiffré comme un tout, ses mesures en interaction (D-483).

AUJOURD'HUI, deux nombres coexistent pour un programme : le rapport du programme (une
passe sur la population de toutes ses mesures chiffrées ensemble, puis la chaîne) et ses
mesures, chacune son rapport. La page somme les mesures quand elle les décompose. Cette
somme est fausse à trois endroits, que `chiffrer` sépare, année par année :

1. LA PASSE : deux mesures sur la même base (deux barèmes de cotisations, un Smic et les
   allègements qui le suivent, l'IR d'un revenu qu'une autre mesure change) ne se
   somment pas dans le moteur. L'écart entre le rapport du programme et ses mesures
   lancées ensemble dans le jumeau est l'interaction de la passe : elle se lit dans les
   rapports commités, sans passe nouvelle.
2. LE JUMEAU : ses mesures lancées ensemble contre la somme de leurs trajectoires seules.
   Le modèle est linéaire par mesure (Mésange, les blocs linéarisés), sauf les intérêts
   chargés au taux marginal et la dette sur le PIB : l'écart est sa non-additivité.
3. LE FINANCEMENT : une mesure qui en finance une autre. Un financement chiffré entre
   comme une loi hypothétique (`annonce.mesures_financement`) ; un recouvrement déclaré
   (« ne pas additionner ») n'est compté qu'une fois ; la compensation de la Sécurité
   sociale par l'État se consolide (`comptes`) et ne change pas le total.

Ce qui ne s'écrit pas sans passe : l'interaction d'une mesure chiffrée avec une mesure
que le moteur ne chiffre pas (une économie non désignée qui toucherait la même
prestation), et les effets croisés des comportements (le Smic et l'emploi au voisinage
des allègements, que le volet `travail` porte) ; ils sont dits, pas chiffrés.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from impots.jumeau.financement import annonce, comptes


def _trajectoire(session: Any, mode: str, vue: str, cle_cadre: str,
                 mesures: Sequence[Any], theta: Mapping[str, Any]) -> Any:
    from impots.jumeau.trajectoire import calculer

    depart, entrees, blocs, boucles = session._modele(mode, mesures[0], cle_cadre)
    return calculer(depart, entrees=entrees, mesures=list(mesures), theta=dict(theta),
                    blocs=blocs, boucles=boucles)


def cles_mesures(session: Any, slug: str) -> list[str]:
    prefixe = f"pres2027_{slug}_"
    return [c for c in session.candidats
            if c.startswith(prefixe) and c != f"{prefixe}programme"]


def chiffrer(session: Any, slug: str, *, mode: str = "reduit", vue: str = "vieillie",
             theta: Mapping[str, Any] | None = None,
             financements: Sequence[str] | None = None,
             options: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Le programme comme un tout, ses mesures seules, ensemble, et avec le financement
    nommé (`financements` : des identifiants de mesures du programme, None pour aucun).
    θ : ceux que le modèle lit, ½ par défaut, et ceux du volet."""
    from impots.jumeau.navigateur import ANNEES

    cle_programme = f"pres2027_{slug}_programme"
    programme = session.mesure(cle_programme, vue)
    seules = {c: session.mesure(c, vue) for c in cles_mesures(session, slug)}
    reg = session.thetas(mode, [programme, *seules.values()],
                         session._modele(mode, programme, cle_programme)[2])
    th = {t["cle"]: 0.5 for t in reg if t["lu"]}
    th |= {"financement_a16_part_cnav": 0.5, "financement_compensation": 0.5}
    th |= dict(theta or {})

    def lire(traj: Any) -> dict[str, list[float]]:
        return {"b9": [round(float(x), 3) for x in traj.difference("b9")[:, 0]],
                "dette": [round(float(x), 3) for x in traj.difference("dette")[:, 0]],
                "ratio_dette_pts": [round(100 * float(x), 3)
                                    for x in traj.difference("ratio_dette")[:, 0]]}

    out: dict[str, Any] = {"candidat": slug, "mode": mode, "vue": vue,
                           "annees": list(ANNEES), "mesures": list(seules)}
    t_prog = _trajectoire(session, mode, vue, cle_programme, [programme], th)
    out["programme"] = lire(t_prog)
    out["sous_secteurs_programme"] = comptes.resume(
        comptes.decomposer(t_prog, [programme], th, options))
    lues = {c: lire(_trajectoire(session, mode, vue, c, [m], th)) for c, m in seules.items()}
    out["seules"] = lues
    somme = {k: [round(sum(v[k][i] for v in lues.values()), 3)
                 for i in range(len(ANNEES))] for k in ("b9", "dette", "ratio_dette_pts")}
    out["somme_des_seules"] = somme
    if seules:
        t_ens = _trajectoire(session, mode, vue, cle_programme, list(seules.values()), th)
        ens = lire(t_ens)
        out["ensemble"] = ens
        out["interaction_passe"] = {k: [round(a - b, 3) for a, b in
                                        zip(out["programme"][k], ens[k], strict=True)]
                                    for k in ens}
        out["interaction_jumeau"] = {k: [round(a - b, 3) for a, b in
                                         zip(ens[k], somme[k], strict=True)] for k in ens}
    if financements:
        fins = annonce.mesures_financement(session, slug, ANNEES, ids=financements)
        if fins:
            t_fin = _trajectoire(session, mode, vue, cle_programme, [programme, *fins], th)
            out["avec_financement"] = lire(t_fin)
            out["financements"] = [m.libelle for m in fins]
            out["sous_secteurs_avec_financement"] = comptes.resume(
                comptes.decomposer(t_fin, [programme, *fins], th, options))
    return out


def mesure_seule(session: Any, cle: str, *, mode: str = "reduit", vue: str = "vieillie",
                 theta: Mapping[str, Any] | None = None,
                 options: Mapping[str, str] | None = None,
                 financements: Sequence[Any] = ()) -> dict[str, Any]:
    """Une mesure d'étude, et ses financements (des `Mesure` déjà construites), par
    sous-secteur."""
    m = (session.mesure_structurel(cle, vue, "parts_premiere_annee") if mode == "structurel"
         else session.mesure(cle, vue))
    reg = session.thetas(mode, [m], session._modele(mode, m, cle)[2])
    th = {t["cle"]: 0.5 for t in reg if t["lu"]}
    th |= {"financement_a16_part_cnav": 0.5, "financement_compensation": 0.5}
    th |= dict(theta or {})
    ms = [m, *financements]
    traj = _trajectoire(session, mode, vue, cle, ms, th)
    c = comptes.decomposer(traj, ms, th, options)
    r = comptes.resume(c)
    r["b9"] = [round(float(x), 3) for x in traj.difference("b9")[:, 0]]
    r["dette"] = [round(float(x), 3) for x in traj.difference("dette")[:, 0]]
    r["ratio_dette_pts"] = [round(100 * float(x), 3)
                            for x in traj.difference("ratio_dette")[:, 0]]
    r["annees_calculees"] = list(traj.annees)
    return r


__all__ = ["chiffrer", "cles_mesures", "mesure_seule"]
