# M0 de la phase 9 — la reconnaissance

**Date :** 2026-10-16. **Spec :** `docs/PHASE9_SPEC.md` §10. **Entrée :** D-214.
**Code mesuré :** `f437822`. **Rejouable :** `scripts/verify_mesange_solde.py`.

M0 lit avant de coder. La spec lui donne quatre questions : ce que dit la ligne de solde
de Mésange (R1), ce que dit la note du HCFP en recoupement (R2), ce que coûte une année de
calcul (R3), et où sont les sources des canaux de §5 et §6 (R4). Chaque section finit sur
un verdict. Aucun chiffre trouvé ici n'entre dans le code autrement que par un fichier au
manifeste (D-026).

---

## R1 — La ligne « Solde primaire des APU » de Mésange

Lue dans `insee_G2017-04_mesange.pdf` (au manifeste, sha256 `a90bc254…`) : §3.7.2,
folios 92-93 ; le cadre des variantes, folio 100 ; les tableaux, folios 102 à 121. Les
chiffres viennent du parseur du dépôt (`mesange.load`), pas d'une recopie.

### Ce qu'est la ligne

Le document la définit : « c'est le solde primaire (solde public hors charges d'intérêt de
la dette) qui est retenu lors de l'analyse des résultats », et « quand un choc fiscal sera
réalisé, il ne sera pas imposé de contrainte d'équilibre budgétaire et on laissera le
déficit se creuser » (folio 92).

**La ligne contient le choc lui-même.** Pour une baisse d'IR d'un point de PIB ex ante,
elle vaut −0,81 la première année, et le texte conclut : « la hausse pérenne de l'activité
et des assiettes fiscales ne parvient pas à compenser la baisse des recettes […], et le
solde primaire des administrations publiques est durablement dégradé » (folio 118). Le
choc coûte un point net ex ante pour toutes les variantes fiscales ; pour la TVA, 1,18
point brut pour un point net, parce que les APU paient environ 15 % de la TVA (folio 112).
La rétroaction que §4.1 veut est donc **solde + 1**, en points de PIB.

| Variante | Rétroaction à 1, 2, 3 ans | Rapport à l'effet sur le PIB |
|---|---|---|
| Impôt sur le revenu | 0,19 · 0,50 · 0,58 | 0,46 · 0,60 · 0,66 |
| CSG | 0,19 · 0,50 · 0,57 | 0,46 · 0,60 · 0,63 |
| Cotisations salariés | 0,27 · 0,53 · 0,61 | 0,71 · 0,74 · 0,81 |
| Cotisations employeurs | 0,28 · 0,58 · 0,73 | 1,40 · 1,05 · 0,96 |
| TVA | 0,20 · 0,64 · 0,72 | 0,62 · 0,97 · 1,00 |
| Taxe carbone | 0,32 · 0,85 · 0,86 | 0,63 · 1,06 · 1,15 |
| Cotisations employeurs, ciblée | pas de ligne de solde | — |

Lecture : une baisse d'IR d'un point de PIB rapporte, par l'activité qu'elle crée, 0,19
point la première année et 0,58 la troisième. Elle ne se finance jamais entièrement.

Le script vérifie que, la première année, chaque variante fiscale dégrade le solde de
moins que son coût ex ante : la valeur doit tomber entre −1 et 0. Une ligne lue avec le
mauvais signe, ou qui exclurait le choc, sort de cet intervalle. Le contrôle a été vu
échouer sur une ligne de signe inversé.

### Ce que fait la dépense pendant une variante

Le tableau 10 (folio 93) dit comment chaque poste réagit, et la note 70 résume : « La
quasi intégralité des dépenses et des recettes publiques réagit en prix, pour un effet
quasi symétrique et donc neutre sur le solde public. En volume, seules les recettes et les
prestations chômage réagissent, conformément aux stabilisateurs automatiques usuels. »
L'investissement public, les prestations en nature et les subventions sont exogènes.

**Conséquence pour §3.2.** Pendant une variante, la dépense de Mésange suit les prix et
pas l'activité, à l'exception des allocations chômage. C'est le scénario `gele_en_volume`.
Sous `part_pib_constante`, la dépense croîtrait avec le PIB réel, ce que Mésange ne fait
pas : une partie de l'amélioration du solde que la ligne affiche disparaîtrait, à peu près
la part des dépenses dans le PIB multipliée par l'écart de PIB. Cette correction est
dérivée, pas lue.

### Le rapport au PIB n'est pas constant

Si la rétroaction ne passait que par le PIB, le rapport serait à peu près le même partout.
Il va de 0,46 (IR, première année) à 1,40 (cotisations employeurs, première année). Une
baisse de cotisations employeurs rapporte plus que son effet sur le PIB : elle relève les
marges, donc l'IS et d'autres assiettes, avant de relever l'activité. L'hypothèse de §4.1,
« la rétroaction suit le multiplicateur proportionnellement » quand θ macro bouge, est donc
une approximation. Elle est bonne pour l'IR et la CSG, médiocre pour les cotisations
employeurs la première année.

### Ce que les tableaux ne portent pas

- **Pas de déflateur du PIB.** Les variantes ordinaires impriment six lignes de prix
  (consommation, production, production marchande, valeur ajoutée marchande,
  consommations intermédiaires, échanges extérieurs), aucune pour le PIB. §4.4 tient donc
  les prix de la réforme constants dans g, convention affichée. Le solde, lui, est déjà en
  points de PIB nominal dans Mésange ; il n'y a pas de double compte, parce que l'effet de
  dénominateur sur la dette (b × y) n'est pas celui sur le ratio du solde.
- **Pas de solde pour la variante ciblée** (encadré 14), que le dépôt utilise pour les
  allègements sur les bas salaires (D-055). Ni prix, ni solde.
- **Les horizons longs existent mais ne servent pas.** La ligne est imprimée à 5 ans,
  10 ans et long terme. D-055 a écarté ces colonnes pour le PIB, parce qu'elles dépendent
  d'un choix de spécification ; la même raison vaut pour le solde, qui s'en déduit.

### Verdict R1

**La candidate A passe M0, à quatre conditions** que la spec doit reprendre :

1. la rétroaction ne s'applique en v1 que sous `gele_en_volume`, l'hypothèse même de
   Mésange ; sous les autres scénarios elle est **absente**, avec sa raison, plutôt que
   corrigée par une formule dérivée (la correction peut venir plus tard, par D-entrée) ;
2. variantes fiscales seulement ; la variante ciblée n'a pas de rétroaction ;
3. horizons 1 à 3 ans ;
4. prix de la réforme constants dans g.

---

## R2 — La note du HCFP 2023-1, en recoupement

**Pas relue.** `hcfp_note_methodologique_2023-1_elasticite_po.pdf` est au manifeste, mais
www.hcfp.fr coupe la connexion depuis ce conteneur : deux essais le 2026-10-16, par le
téléchargeur du manifeste puis par curl, avec la même erreur (« connection reset by
peer »).

Ce que le dépôt en garde, c'est le relevé de la vérification adverse du 2026-09-03
(`macro/parameters/revenue_elasticity.yaml`) : l'équation (4) du tableau 3 (p. 11) ajoute
la part des salaires privés au PIB, et son écart-type de résidu est la bonne largeur. C'est
la lecture du vérificateur, consignée, et non une relecture de ce jour.

**Verdict R2.** La candidate B n'est pas nécessaire, puisque A passe. Elle reste le
recoupement. Le fichier se télécharge sur le réseau du propriétaire, et la relecture se
fait avant toute ligne B, pas avant M1.

---

## R3 — Le coût d'une année de calcul

Mesuré sur cette machine (4 cœurs, 15 Go), une passe à la fois et machine au repos : une
durée relevée pendant qu'autre chose tourne n'est pas une durée (D-161). Une passe
mécanique est un `runner.run` plein tarif, référence et réforme comprises ; une passe de
taux marginaux est l'`emtr.compute` que l'API lance pour la bande comportementale. La
réforme mesurée supprime le plafond de l'abattement de 10 % sur les pensions.

| Passe | Année | Ménages | Durée | Mémoire au pic |
|---|---|---|---|---|
| mécanique | 2026 | 20 000 | 160 s | 6,3 Go |
| mécanique | 2032 | 20 000 | 151 s | 6,3 Go |
| mécanique | 2036 | 20 000 | 148 s | 6,3 Go |
| mécanique | 2026 | 40 000 | 287 s | 12,0 Go |
| taux marginaux | 2026 | 3 000 | 60 s | 1,2 Go |
| taux marginaux | 2032 | 3 000 | 60 s | 1,2 Go |

**L'année ne coûte rien.** 2036 se calcule comme 2026, sans erreur. Mais la loi s'arrête
plus tôt : `trajectoires.last_legislated_year`, remesuré ici jusqu'à 2036, rend 2027 pour
les ménages et 2030 pour les entreprises. Au-delà, l'arbre reconduit les dernières
valeurs, et chaque année le dit (`basis_for`). L'API, elle, n'accepte que 2022 à 2026
(`schemas.MAX_YEAR`) : la chaîne prédictive ne passera pas par cette fenêtre.

**Le nombre de ménages coûte tout, à peu près linéairement.** Doubler les ménages multiplie
la durée par 1,8 et la mémoire par 1,9. Toute la population (199 451 ménages) demanderait
de l'ordre de 60 Go, hors de portée de cette machine : c'est une extrapolation, pas une
mesure. Deux passes ne tournent jamais en parallèle ici.

**Une année de trajectoire, ce sont deux passes** (vue figée et vue vieillie,
`population/cli.py`), quatre contre la référence `indexe`, plus les taux marginaux si la
bande est notée chaque année. Soit environ six minutes par année en `reconduit` à 20 000
ménages : une heure pour dix ans, près de deux heures en `indexe`. **θ ne coûte rien** :
les canaux de comportement et la couche macro sont de l'arithmétique sur ces passes, et les
2^K coins de la boîte θ ne relancent pas le moteur.

### Verdict R3

Dix années chiffrées une à une ne tiennent pas dans une requête : la simulation actuelle
avec bande prend déjà trois à quatre minutes. Recommandation pour M1, à consigner :

1. **une commande** (`impots predictif`, sur le modèle de `impots trajectoires`) calcule la
   trajectoire année par année et écrit un rapport JSON, que la page lit ;
2. **l'API sert une version rapide** : la première année projetée chiffrée (figée et
   vieillie), puis Δ tenu en part de PIB constante, avec l'étiquette « convention ». C'est
   la règle de repli de §3.1, ramenée de trois années à une par la mesure.

---

## R4 — Les sources de §5 et §6

Localiser, pas charger. Chaque piste est un identifiant (titre, éditeur, numéro, date),
selon la règle du pointeur ; une URL vue dans un index de recherche n'en est pas un.
Le contenu des documents non lus est marqué **non lu**.

| Canal | Piste | Accès | Ce qu'elle mesure | Verdict |
|---|---|---|---|---|
| Transferts (§5) | IMK WP117 (2013) et WP139 (2014), colonne TRANS, **au manifeste** | lues par le parseur | multiplicateur moyen et écart-type, toutes économies avancées, horizons confondus | rester fermé en v1 (ci-dessous) |
| IS, multiplicateur (§5) | Mésange 2017, §4.1 | lu | huit variantes budgétaires et fiscales, **aucune sur l'IS** | fermé |
| | OFCE, billet « 2013 : quel impact des mesures budgétaires nationales sur la croissance ? » | non lu | un multiplicateur moyen de hausse d'IS, selon l'index | à lire avant tout usage |
| IS, investissement (§6.2) | France Stratégie, Comité d'évaluation des réformes de la fiscalité du capital, rapport d'octobre 2023 | **non lu** : l'URL de l'index renvoie une 404 après redirection vers strategie-plan.gouv.fr | PFU, IFI et baisse de l'IS à 25 % | à lire ; la meilleure piste |
| Offre de travail (§6.1) | Bargain, Orsini, Peichl, « Comparing Labor Supply Elasticities in Europe and the United States: New Results », IZA DP n° 6735, juillet 2012 | **en accès libre**, téléchargé hors du dépôt (1 065 161 octets, sha256 `bafcea33…`) | tableaux F.1 à F.8 par sexe et situation conjugale ; France sur 1998 et 2001, via EUROMOD | à manifester ; le canal peut ouvrir en M5 |
| Créations, indice (§6.3) | INSEE, Informations rapides « Créations d'entreprises », mensuel ; séries longues corrigées depuis janvier 2015 | publiques | sociétés, entreprises individuelles classiques, micro-entrepreneurs | manifestable |
| Créations, réponse (§6.3) | INSEE Analyses n° 68 (octobre 2021) et document de travail 2021-01, sur les JEI | non lus | l'emploi des entreprises bénéficiaires, pas les créations | ne répond pas à la question |
| | IGAS, rapport sur le régime de l'auto-entrepreneur ; INSEE Hauts-de-France, enquête 2023 | non lus | un régime, et des déclarations | ne répond pas à la question |
| R&D (§6.4) | CNEPI (France Stratégie), « Évaluation du crédit d'impôt recherche », juin 2021 | public | les effets de la réforme de 2008 | à lire |
| | DG Trésor, « Évaluation de la réforme du Crédit Impôt Recherche de 2008 », 2021 | public | idem | à lire |
| | MESR, base GECIR | non localisée en fichier ouvert | créances et bénéficiaires | D-154 tient |

**Transferts.** Les deux méta-analyses, au manifeste, donnent pour la colonne TRANS :

| | moyenne | écart-type | n |
|---|---|---|---|
| WP117 | 0,39 | 0,47 | 59 |
| WP139 | 0,54 | 1,16 | 36 |

Deux papiers du même auteur, qui ne s'accordent ni sur le centre ni sur la largeur, avec
un facteur 2,5 sur la seconde. Aucun profil par horizon (les horizons d'un à douze ans sont
mêlés), aucune ligne de solde, et un centre qui n'est pas français. Recommandation :
**laisser les transferts fermés en v1**. Une réforme des prestations garde son chiffrage
mécanique et sa bande ; elle n'a pas d'éventail, et la page dit pourquoi.

**Créations d'entreprises.** L'indice de base existe. Aucune évaluation trouvée ne mesure
la réponse des créations à un **taux** d'impôt : celles qui existent portent sur un
dispositif (JEI) ou un régime (auto-entrepreneur), et l'une mesure l'emploi, pas les
créations. L'avertissement de §6.3 se vérifie : le canal reste fermé pour les taux.

---

## Ce que M0 change dans la spec

- **§3.1** : la trajectoire complète se calcule par une commande ; l'API sert la version
  rapide, première année chiffrée puis Δ en part de PIB constante, étiquetée.
- **§3.2 et §4.1** : la rétroaction de Mésange ne s'applique que sous `gele_en_volume`
  en v1 ; absente ailleurs, avec sa raison.
- **§4.1** : la proportionnalité au multiplicateur est une approximation, médiocre pour
  les cotisations employeurs la première année ; l'étiquette le dit.
- **§4.4** : pas de déflateur du PIB dans les tableaux ; prix constants confirmés.
- **§4.5** : les colonnes de solde à 5 et 10 ans ne servent pas au scénario de
  persistance.
- **§5** : transferts fermés en v1 ; IS fermé, faute de variante.
- **§6.1** : la source est en accès libre ; à manifester.
- **§6.3** : aucune source de réponse aux taux ; fermé.

## Le gel de conception

M1 (la chaîne, §3) et M3 (la rétroaction, §4) peuvent se figer sur ce qui précède. M1 n'a
besoin d'aucune donnée nouvelle.
