# La vidéo explicative : le script de narration

Écrit par `python video/build.py script` depuis `video/scenes.py` ; ne pas le
modifier à la main. Chaque nombre dit est recopié d'un fichier commité du dépôt,
nommé sous la scène. Rien n'a été recalculé pour la vidéo.

## 0. Titre

> Un candidat promet de rendre de l'argent aux salariés. Combien cela coûte-t-il, qui y gagne, et que devient la dette dans dix ans ?

> Voici comment l'outil Impôts y répond, à partir de données publiques, et où il peut se tromper.

## 1. Chapitre 1 — Trois réponses pour chaque mesure

> Pour chaque mesure, trois réponses.

> Un : le coût la première année, et qui y gagne.

> Deux : le coût une fois comptées les réactions des gens, en fourchette.

> Trois : l'effet sur la dette publique en 2035, rapportée au PIB, la richesse produite en un an, avec un verdict. Plus on avance, moins le chiffre est sûr.

Sources :

* les trois réponses, l'ordre de confiance : `docs/BUT.md ; src/impots/site_textes/methode.html`

## 2. Chapitre 2 — D'abord, un seul ménage

> D'abord, un seul ménage : une personne seule, 30 000 euros brut par an, sur les revenus de 2024.

> Après les cotisations sociales, puis la CSG et la CRDS, deux prélèvements qui financent la Sécurité sociale, il reste 23 748 euros nets.

> Elle paie 812 euros d'impôt sur le revenu et touche 213 euros de prime d'activité, une aide aux travailleurs modestes. Revenu disponible : 23 148 euros.

> Ces règles viennent d'OpenFisca, le modèle public qui traduit la loi française en programme.

> Et il est contrôlé : sur deux ménages, le simulateur des impôts trouve le même impôt, à l'euro près. Les cotisations et les prestations n'ont pas ce contrôle.

Sources :

* le ménage single_30k, chaque ligne : `reports/parcours/menages.json`
* le contrôle à l'euro contre la DGFiP : `site/parcours-1-menage.html ; tests/golden/CROSSCHECK.md`

## 3. Chapitre 3 — Une mesure : « Droit au brut »

> La mesure d'Attal promet 250 euros nets de plus par mois au salaire médian, celui qui coupe les salariés en deux moitiés. C'est un gain, pas un taux.

> Au salaire médian de 2026, 34 000 euros brut par an, supprimer toutes les cotisations retraite des salariés rendrait 3 845 euros par an.

> En garder 22 pour cent rend 3 000 euros par an, soit 250 par mois : une traduction choisie par l'outil, appliquée à tous les salaires.

Sources :

* +250 € par mois, 0,22, 34 000 €, 3 845 €, 3 000 € : `site/parcours-3-cout.html ; programmes/attal.json`

## 4. Chapitre 4 — Les données d'entrée

> Pour toute la France, il faut des millions de ménages. Les vrais ne sont pas publics : l'outil en construit d'autres.

> La structure vient de l'enquête Emploi 2024 de l'Insee : de vrais ménages, avec l'âge, l'emploi, le logement. Mais aucun revenu.

> Les salaires sont donc tirés au hasard sur les courbes publiées : la moitié des salariés du privé gagne moins de 2 190 euros nets par mois, à temps plein. Un revenu tiré a la bonne forme, mais il n'est celui de personne.

> Les entreprises viennent des tableaux de l'Insee ; la loi et les programmes sont relevés avec leur source.

Sources :

* enquête Emploi, revenus tirés, 2 190 € : `site/parcours-2-france.html ; src/impots/population/margins.py`
* entreprises (Ésane 2023) : `docs/diagnostics/demarche.md, § 1.2`

## 5. Chapitre 5 — Une population calée sur les totaux publiés

> Puis on ajuste le poids de chaque ménage pour retrouver 24 totaux publiés : la masse des salaires, 1 111 milliards d'euros en 2024, le nombre de ménages, les retraites…

> On obtient 31 millions de ménages. Un calcul en tire 20 000, dont les poids représentent toute la France.

> Attention : un total imposé est « dépensé ». La population le retrouve parce qu'on l'y a forcée ; il ne peut plus servir à la vérifier.

Sources :

* 24 totaux, 1 111,65 Md€ : `site/parcours-2-france.html (le tableau des totaux calés)`
* 31,01 M, 31,27 M, −0,8 %, 20 000 ménages, 31,05 M : `site/parcours-3-cout.html ; reports/reconciliation.md`

## 6. Chapitre 6 — Le coût : deux passes sur la même population

> Le coût : l'outil fait tourner la loi de 2026 deux fois sur la même population, sans la mesure, puis avec. Le coût, c'est la différence.

> Les cotisations des salariés passent de 120 à 43 milliards d'euros : 77 milliards reviennent en salaire net.

> Mais tout est recalculé : l'impôt sur le revenu en reprend 12 milliards, les aides sous condition de ressources près de 2.

> Ces aides comptent le non-recours : environ la moitié des foyers ayant droit à la prime d'activité ne la demandent pas.

> Coût pour les ménages : 63,14 milliards ; avec la CVAE, un impôt des entreprises, supprimée : 65,69 milliards la première année. Personne ne change de comportement : c'est mécanique.

Sources :

* 120,17 ; 43,03 ; +77,14 ; −12,05 ; −1,92 ; −0,03 ; +63,14 ; +2,55 ; +65,69 Md€ : `site/parcours-3-cout.html ; reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json`
* non-recours : 50 % des foyers, Drees 48 à 52 % : `site/parcours-2-france.html ; src/impots/population/recours.py`

## 7. Chapitre 7 — Qui y gagne ?

> Qui y gagne ? On range les ménages en dix groupes égaux, les déciles, du plus modeste au plus aisé.

> Le premier décile gagne 197 euros par an en moyenne ; le dernier, 4 595.

> La mesure passe par les salaires : 26 pour cent de gagnants dans le premier décile, 68 pour cent dans le dernier.

> Personne n'y perd ici : seules 2 mesures sur 20 sont chiffrées. Les 150 milliards d'économies annoncées ne désignent aucune dépense : l'outil les refuse, et le dit.

Sources :

* gains et parts de gagnants par décile : `site/presidentielle_attal.html ; reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json`
* 2 mesures sur 20, 33 relevées, 150 Md€ refusés : `site/presidentielle_attal.html ; programmes/attal.json`

## 8. Chapitre 8 — Les comportements : lus dans des études publiées

> Deuxième réponse : les comportements. L'outil lit des élasticités dans des études publiées : de combien une chose réagit quand une autre bouge.

> Exemple : le revenu déclaré des 10 pour cent les plus aisés réagit à l'impôt avec une élasticité de 0,31, entre 0,15 et 0,50.

> Une lettre grecque, thêta, choisit le point dans la fourchette : 0 en bas, un demi au milieu, 1 en haut.

> Pour Attal, aucune de ces réactions n'est branchée : le coût reste mécanique. C'est un choix du modèle : la réaction des heures de travail n'est branchée que sur la CSG.

Sources :

* 0,31 entre 0,15 et 0,50 ; θ : `site/parcours-4-comportements.html ; src/impots/behavioural/parameters/eti.yaml`
* aucun canal pour Attal, D-220 : `site/presidentielle_attal.html ; site/parcours-comparer.html`

## 9. Chapitre 9 — L'activité : ce que la croissance rend

> Troisième étage : l'économie. 77 milliards rendus aux salariés font monter l'activité, qui ramène des impôts.

> Cet effet est lu dans Mésange, le modèle de l'Insee et du Trésor : pour une baisse des cotisations des salariés, 76 centimes par euro reviennent après dix ans.

> Les études divergent : selon thêta, il revient de 32 centimes à un euro.

> Ce que Mésange ne couvre pas, comme les prestations ou les impôts des entreprises, ne rapporte rien ici : faute de mesure, pas faute d'effet.

Sources :

* solde à 10 ans −0,24 → 0,76 ; θ = 0 : 0,32 ; θ = 1 : 1,00 : `site/parcours-5-activite.html ; src/impots/macro/parameters/multipliers.yaml`
* σ = 0,66 (méta-analyses IMK) : `src/impots/macro/parameters/dispersion.yaml`
* 2,65 points de PIB en 2026 : `site/parcours-5-activite.html`

## 10. Chapitre 10 — La dette : une identité comptable

> La dette est une identité comptable : la dette d'avant porte intérêt, le déficit s'y ajoute, le tout rapporté au PIB. En 2035, un point de PIB vaut environ 40 milliards d'euros.

> Départ publié : 115,69 pour cent du PIB fin 2025. Puis un cadre déclaré, pas une prévision : 1 pour cent de croissance, 2 pour cent de hausse des prix, dépenses gelées. Sans réforme, la dette tomberait à 103,78 pour cent en 2035 : plus favorable que la prévision du gouvernement.

> Les revenus de la population sont vieillis de 3 pour cent par an : autre hypothèse.

> Pour Attal, sans effet sur l'activité, la dette de 2035 monterait de 20,28 points de PIB. Le PIB plus haut en retire 3,07, les recettes que ramène l'activité 13,01. Il reste 4,21.

> De 20 à 4 points : tout tient au maillon le moins sûr, l'effet sur l'activité.

Sources :

* 115,69 %, 2 991 Md€, 1,883 %, référence 103,78 %, 121,70 % / 117,47 % : `site/parcours-6-dette.html ; etudes/cadres/central.json`
* +20,28 ; −3,07 ; −13,01 ; +4,21 pt : `reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json`
* salaires vieillis à 3 % par an : `site/parcours-6-dette.html`
* un point de PIB de 2035 vaut environ 40 Md€ : `src/impots/site_textes/methode.html`

## 11. Chapitre 11 — Le verdict : un tirage au sort sous des lois écrites

> Ce 4,21 suppose chaque effet au milieu de sa fourchette. Aux extrêmes, la dette va de moins 4 à plus 15,6 points.

> L'outil tire donc 2 000 fois les incertitudes au hasard, selon des lois écrites d'avance : c'est un Monte-Carlo. La dette monte dans 64,65 pour cent des tirages.

> Le seuil, fixé avant tout calcul, est de 90 pour cent : le verdict est « dépend ». Et 98 pour cent de l'incertitude vient de l'effet sur l'activité.

Sources :

* boîte θ −4,04 à +15,63 ; 64,65 % ; quantiles −4,99 · +4,58 · +20,09 : `site/parcours-7-verdict.html ; reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json`
* seuil de 90 %, 2 000 tirages : `src/impots/predictif/montecarlo.py (SEUIL_VERDICT)`

## 12. Chapitre 12 — Où l'outil se trompe : la grille

> Où l'outil se trompe-t-il ? Une grille compare chaque grand total simulé au total publié, de 2022 à 2024, avec une marge écrite d'avance : la tolérance.

> 84 lignes sur 113 tiennent leur tolérance. Mais c'est la même population, ramenée en arrière : ce ne sont pas 113 vérifications indépendantes.

> Pour Attal, la ligne clé : les cotisations des salariés, 9,7 pour cent sous les comptes nationaux. Si l'écart touche la retraite, le coût est trop bas d'autant ; ce n'est pas vérifié.

Sources :

* 84 sur 113, par année, chaque ligne : `reports/verification/grille.json ; site/parcours-2-france.html ; site/parcours-8-erreur.html`
* cotisations des salariés −9,7 % en moyenne : `site/parcours-3-cout.html`

## 13. Chapitre 13 — Les juges officiels

> Pour le coût, le juge est extérieur : le chiffrage officiel publié avec un projet de loi. Chaque cas est enregistré avant de lire ce chiffre.

> Résultat : 3 sur 5. Le raté le plus net : la prime d'activité au budget 2027. 887 millions d'euros d'économies pour l'outil, 332 pour le gouvernement.

> Avec cinq cas, la note ne distingue pas un bon outil d'un mauvais. Attal attend son juge : l'Institut Montaigne, début 2027.

Sources :

* les cinq cas, 3 sur 5, 15 % à 95 % : `site/parcours-3-cout.html ; reports/chiffrages_preregistres.md`
* art. 74, −887 M€ contre −332 M€ : `chiffrages_preregistres/plf2027_art_74_ppa.yaml ; site/parcours-8-erreur.html`
* Attal +75,66 Md€, juge attendu : `site/presidentielle_attal.html`

## 14. Chapitre 14 — Ce que l'outil ne fait pas, et pourquoi on ne compare pas tout

> L'outil ne simule ni la dépense publique, ni les retraites, ni les successions, ni la fraude ; et les prix ne réagissent pas aux mesures.

> Les candidats ne se comparent donc pas ligne à ligne : chacun n'est chiffré qu'en partie, et l'effet sur l'activité ne passe que par certains impôts.

> Ce qui se compare : le coût de la première année, et la dette sans effet sur l'activité : plus 20,28 points pour Attal, plus 4,96 pour Retailleau.

Sources :

* ce que l'outil ne fait pas : `src/impots/site_textes/methode.html`
* ce qui se compare, +20,28 et +4,96 pt, 2 sur 20 et 2 sur 29 : `site/parcours-comparer.html ; site/parcours-6-dette.html`

## 15. En résumé — Du ménage au verdict

> En résumé : une loi codée et contrôlée, une population calée, deux passes pour le coût, des réactions lues dans des études, une identité comptable pour la dette, et un tirage au sort pour dire ce qui est sûr.

> Chaque nombre a sa source, chaque hypothèse son nom. Le détail, page par page, est sur le site du projet.

Sources :

* chaque nombre repris des scènes précédentes : voir plus haut
