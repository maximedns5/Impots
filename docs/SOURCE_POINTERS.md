# La règle du pointeur — comment une source se transmet entre sessions

Née d'un incident, le 2026-09-08. Un cahier des charges annonçait une source « localisée,
lue et confirmée » et donnait son URL. **L'URL renvoyait 404** : le fichier avait été
redéposé neuf mois plus tôt sous un autre chemin. La session de relecture l'avait bien
lue — son accès avait résolu par une route que celui de l'implémenteur n'a pas retrouvée —
mais ce qui a été transmis était un **pointeur**, pas le contenu.

Le même cahier des charges nommait aussi le mauvais tableau : il annonçait des montants
d'ISF par tranche là où le tableau ne porte que des **parts**. Les deux erreurs ont été
survivables parce que la session a traité le cahier des charges comme une **piste** et non
comme un fait — ce que toutes les règles permanentes enseignent déjà.

## La règle

**Un passage de relais transmet des IDENTIFIANTS, jamais une URL nue comme référence
porteuse.** Un identifiant, ici, c'est :

* le **titre** et l'**éditeur** ;
* le **numéro** de publication et sa **date** ;
* le **sujet du tableau ou de la page** visée — « le tableau des niveaux par statut de
  plafonnement », pas « tableau 1.1 » seul, parce qu'une numérotation se renumérote ;
* et, dès que le fichier est manifesté, son **sha256**, qui est le seul pointeur qui ne
  pourrit pas.

**L'implémenteur re-résout au moment de l'usage.** Une URL peut accompagner un identifiant
comme commodité ; elle ne peut pas le remplacer.

## Corollaire, appris le même jour

Une URL trouvée dans un index de recherche peut être **périmée alors même que l'index la
sert encore** : la recherche continuait de renvoyer le chemin de 2023 après le redépôt de
2025. Le chemin courant s'est relevé sur la **page de publication** de l'éditeur, jamais
sur un index.

## Les sources porteuses de la phase 5, par identifiant

| Fichier manifesté | sha256 (12 premiers) | Identifiant à transmettre |
|---|---|---|
| `ipp_rapport46_isf_plafonnement.pdf` | `aa6250072ea7` | IPP, Rapport n° 46, octobre 2023, « Le plafonnement de l'impôt sur la fortune ». **Le tableau utile est celui des NIVEAUX par statut de plafonnement** (patrimoine, revenus, ISF avant et après plafonnement) — pas celui des parts par tranche. |
| `ggmsz_french_wealth_tax.pdf` | `17a0027e2709` | Garbinti, Goupille-Lebret, Munoz, Stantcheva & Zucman, « Tax Design, Information, and Elasticities », NBER WP 31333, révision 2026. **La figure des quatre élasticités de coude pur**, pas la phrase du résumé qui n'en cite que deux. |
| `dgfip_stats_33_ifi_2024.xlsx` | `f35f57885046` | DGFiP Statistiques n° 33, avril 2025, IFI 2024. **La feuille du graphique des parts par tranche** porte la répartition ; l'encadré du PDF porte l'avertissement sur la base comptable. |
| `dgfip_stats_45_ifi_2025.xlsx` | `626c8f246761` | DGFiP Statistiques n° 45, avril 2026, IFI 2025. **Le tableau des agrégats**, qui donne 2024 ET 2025 en colonnes. En-tête en « M€ », cellules en euros. |
| `vm_tome1_plf2026_recettes.pdf` | `4703605df8bf` | Évaluation des voies et moyens, annexe au PLF 2026, tome I. **La notice de la ligne 1406**. Le montant y figure aussi ailleurs pour une autre imposition : chercher la ligne, pas le nombre. |
| `insee_rpm2023_patrimoine_composition.html` | `4e2aae05bcdd` | INSEE, « Les revenus et le patrimoine des ménages », éd. 2023. **La figure de composition du patrimoine brut par fractile**, ligne « Supérieur à P99 ». |
| `senat_r19_042_isf_ifi_transition.html` | `3daf07837c33` | Sénat, rapport d'information n° 42 (2019-2020), bilan ISF→IFI. **Les deux tableaux d'effectifs** : redevables IFI 2018 par tranche, et redevables ISF 2017 exonérés d'IFI par tranche. |
| `ipp_note92_milliardaires.pdf` | `743769b02199` | IPP, Note n° 92, « Quels impôts les milliardaires paient-ils ? ». **Ne porte aucun chiffre de patrimoine** — manifestée pour ce constat. |
| `bdf_comptes_distributionnels_methodologie_2024.pdf` | `5f16534e7f6d` | Banque de France, méthodologie des comptes distributionnels, février 2024. **Manifestée pour sa note de limite** : les données ne descendent pas plus finement que le top 5 %. |

Deux de ces lignes sont manifestées **pour ce qu'elles ne contiennent pas**. C'est
délibéré : une source dont on a établi qu'elle ne porte pas ce qu'on lui prêtait est un
résultat, et le perdre coûterait le même travail une deuxième fois.
