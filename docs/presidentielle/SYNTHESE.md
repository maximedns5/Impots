# La présidentielle 2027 dans le moteur : synthèse de la recherche, 1er novembre 2026

Quatre inventaires, sourcés et datés, dans ce dossier : `candidats_gauche.md`,
`candidats_centre_droite.md`, `candidats_rn_autres.md` (les mesures, chacune avec sa citation,
son URL et sa date), `evaluateurs.md` (les juges, sans aucun de leurs montants) et
`moteur.md` (ce que le moteur sait paramétrer). Cette page en tire la carte et le plan.

## Ce que disent les programmes

Une trentaine de candidats déclarés ou pressentis, et 360 mesures relevées : 233 paramétrées
(un taux, un montant, un âge), 127 vagues. Par catégorie, les mesures paramétrées :

| catégorie | paramétrées | ce que le moteur en fait aujourd'hui |
|---|---:|---|
| dépense publique | 52 | rien : la dépense n'est pas microsimulée, seulement un scénario de la chaîne |
| retraites (âge, indexation, capitalisation) | 28 | l'âge est hors du modèle ; l'indexation est un module à écrire |
| énergie et carburants | 22 | porte « consommation » : ni volumes, ni accises |
| patrimoine et capital | 22 | le PFU (part IR) ; successions, Zucman, plus-values latentes : non |
| prestations et minima | 20 | RSA, PPA, AF ; ni l'assurance chômage, ni les fusions de prestations |
| impôts des entreprises | 18 | IS, CVAE, C3S, allègements, surtaxe par la CEBGE ; ni la CFE ni le foncier |
| règle budgétaire et dette | 18 | une hypothèse de la chaîne, un seul scénario de dépense à la fois |
| CSG et cotisations | 17 | la CSG sur l'activité ; pas les cotisations salariales ni les seuils neufs |
| TVA et consommation | 10 | rien : pas d'assiette par taux |
| IR | 9 | le barème, la décote, le plafond du QF ; une 6e tranche demande un ajout |
| SMIC et salaires | 5 | rien : les salaires sont des données |
| autre | 12 | au cas par cas |

À la louche, et à confirmer mesure par mesure : le moteur chiffre aujourd'hui, ou avec un
petit ajout, une trentaine des 233 mesures paramétrées, une sur huit. Ce sont les mesures
fiscales au sens strict. Les mesures qui pèsent le plus sur la dette dans les programmes (les
retraites, la dépense, l'énergie) sont hors de portée.

## Le piège : un programme chiffré en partie ment sur la dette

Un programme qui finance des baisses d'impôts par des économies de dépense (le cas de la
plupart des programmes de droite) ou des dépenses par des impôts sur le patrimoine (le cas de
plusieurs programmes de gauche) serait chiffré sur la seule moitié que le moteur sait voir.
La réponse sur la dette dirait « hausse » ou « baisse » pour une raison qui tient au moteur,
pas au programme, et le biais n'aurait pas le même signe d'un bord à l'autre. Deux règles
en découlent :

1. La réponse sur la dette n'est jamais celle « du programme » : c'est celle de la part
   chiffrée, avec, à côté, la part du programme qu'elle couvre et ce qui est refusé, mesure
   par mesure, avec sa raison.
2. Ce que le candidat annonce lui-même (ses économies, ses recettes) peut s'afficher dans une
   couche à part, marquée « déclaré, non vérifié », avec un paramètre de réalisation ρ dans
   [0, 1] que l'utilisateur fait varier. Elle ne se mêle jamais au verdict du moteur. C'est
   au propriétaire de dire s'il la veut.

## Les juges

- Mesure par mesure en 2022 : l'Institut Montaigne (une fiche par mesure, coût statique
  direct) et la Fondation iFRAP (*Société Civile* n° 232, par an en 2027). 211 mesures de
  2022 dans le périmètre du moteur sont listées par leur seul libellé.
- Pour 2027 : l'Institut Montaigne annonce son chiffrage au premier trimestre 2027. C'est le
  juge à attendre : chaque mesure chiffrable peut être préenregistrée avant qu'il ne sorte,
  exactement comme les fiches du PLF.
- « Déchiffrer 2027 » publie déjà un chiffrage par mesure, de méthode proche de la nôtre ;
  son éditeur n'est pas identifié. Personne ne lit ses montants avant que son indépendance
  soit établie : il pourrait servir de juge, et le lire le gâcherait.

## Les paramètres, au-delà de θ

- Le paramètre de chaque mesure, dans une plage : le taux de la nouvelle tranche, le niveau
  de la CSG, le taux de l'IS. Par défaut, la valeur que le candidat énonce.
- La date d'effet et la montée en charge : aujourd'hui, une mesure part du 1er janvier de son
  année et rien d'autre ; les programmes étalent leurs mesures sur le quinquennat.
- θ, déjà là, et les hypothèses de la chaîne : croissance, taux, règle de dépense.
- ρ, si la couche déclarée est retenue.

Faire bouger un curseur en direct demandera une couche de précalcul : une passe de population
coûte deux minutes, une trajectoire de dette une heure. Ce sera un but à part, avant l'UI.

## Le plan proposé

- **But 11 — Les programmes comme réformes, préenregistrés avant le juge.** Un fichier par
  candidat déclaré, les mesures traduites en paramètres ou refusées avec leur porte ; les
  boutons qui manquent aux mesures fiscales les plus fréquentes ; `impots programme` ; chaque
  mesure chiffrable préenregistrée avant la publication de l'Institut Montaigne.
- **Ensuite, un module par but**, dans l'ordre des euros qu'il ouvre : l'indexation des
  pensions et des prestations ; la consommation (TVA, accises sur l'énergie) ; les
  successions et le patrimoine ; la dépense publique comme scénario par candidat ; l'âge de
  la retraite, le plus lourd, qui demande de faire vieillir la population en âge.
- **Puis** la couche de précalcul pour les curseurs, et l'UI.

## Ce qui reste à faire sur les inventaires

- Les rafraîchir avant tout préenregistrement : *L'Avenir en commun* sort en 5e édition le
  6 novembre, le RN publie sa réforme des retraites le 17 novembre, d'autres programmes ne
  sont pas encore écrits.
- Vérifier aux sources primaires les mesures connues par la presse ou par un agrégateur
  (Villepin, Philippe, Glucksmann notamment), et classer les candidats laissés à la frontière
  des trois périmètres (Dupont-Aignan, Polony, Poisson).
- Les sites qui ont refusé l'accès (403) n'ont pas été contournés.
