# Le PLF 2027 en trois réponses

<!-- Généré par scripts/write_etude_plf2027.py depuis reports/etude_plf2027/ ; ne pas éditer à la main. -->

Le projet de loi de finances pour 2027 porte 33 articles fiscaux. Cet outil en chiffre 3, et dit pourquoi il ne chiffre pas les autres. Pour chacun des 3, trois réponses : ce qu'il coûte et qui y gagne ; ce qu'il coûte une fois les comportements et l'économie pris en compte ; ce qu'il fait à la dette en 2035. Puis l'écart au chiffrage du gouvernement, l'évaluation préalable publiée avec le texte.

Chaque nombre dépend de ce qui est dit à côté de lui. Le coût de la première année est mécanique : personne ne change de comportement. La bande dit ce que les comportements y changent quand une étude publiée permet de le dire. La dette en 2035 dépend d'hypothèses de croissance, de taux et de dépenses nommées en bas de page, et de θ, la position de chaque réponse dans sa fourchette publiée : θ½ est le milieu, les coins de la boîte en sont les extrêmes.

## En bref

| article | la première année | le chiffrage officiel | dette en 2035, à θ½ | selon θ |
|---|---|---|---|---|
| art. 2 | +2,83 Md€ | +4,20 Md€, hors de la tolérance | +0,82 pt | dépend de θ |
| art. 3 | -1,12 Md€ | -1,10 Md€, dans la tolérance | -0,35 pt | dépend de θ |
| art. 15 | -7,05 Md€ | -5,50 Md€, dans la tolérance | -0,23 pt | baisse |

Un coût positif coûte au budget, un coût négatif lui rapporte. La dette est en points de PIB, dans la vue vieillie et sous la première persistance de l'effet macro de chaque article ; « selon θ » lit toutes les vues et toutes les persistances.

## Art. 2 — Soutenir le travail en revalorisant le barème de l'impôt sur le revenu grâce à un traitement fiscal équivalent des différents types de revenus

*PLF 2027 (AN, texte n° 3210), art. 2 — Soutenir le travail en revalorisant le barème de l'impôt sur le revenu grâce à un traitement fiscal équivalent des différents types de revenus. Volet chiffré : la revalorisation de 2,1 % des tranches, de la décote et du plafond général de la demi-part (I, H, 1° à 3°), revenus 2026.*

Ne porte PAS les autres volets de l'article : indemnités de rupture, IJ ALD et AT/MP, prime carburant 2026, taux de CSG des IJ ; ni les plafonds de QF autres que le général (4 262, 1 079, 1 801, 2 011 €), ni le 196 B, ni l'indexation des limites de déductions (abattements pensions et frais professionnels).

### 1. Ce qu'il coûte, et qui y gagne

La mesure coûte **2,83 Md€** la première année (revenus 2026), sur la population de 2024 au droit de 2026.

| décile | ménages | niveau de vie moyen | delta moyen | gagnants | perdants |
|---|---|---|---|---|---|
| 1 | 3 102 007 | 8 273 € | +0 € | 0 % | 0 % |
| 2 | 3 100 131 | 13 306 € | +0 € | 1 % | 0 % |
| 3 | 3 102 584 | 16 595 € | +1 € | 2 % | 0 % |
| 4 | 3 101 315 | 19 726 € | +12 € | 15 % | 0 % |
| 5 | 3 100 962 | 22 590 € | +48 € | 63 % | 0 % |
| 6 | 3 101 037 | 25 476 € | +86 € | 93 % | 0 % |
| 7 | 3 101 015 | 28 843 € | +105 € | 99 % | 0 % |
| 8 | 3 101 048 | 32 961 € | +143 € | 100 % | 0 % |
| 9 | 3 101 712 | 39 197 € | +205 € | 100 % | 0 % |
| 10 | 3 101 552 | 61 679 € | +312 € | 100 % | 0 % |

Les déciles sont ceux du niveau de vie de la population simulée. Toute structure
plus fine qu'un décile est un artefact de l'imputation, pas un résultat.


### 2. Avec les comportements et l'économie

**Une fois les comportements pris en compte**, la mesure coûte de +2,63 Md€ à +2,72 Md€, central +2,68 Md€ (grade **in-support**), pour +2,83 Md€ sans eux.

*La variation induite par cette réforme reste dans l'intervalle sur lequel les élasticités ont été estimées.*

**L'effet sur l'économie**, l'éventail macro de grade **in-support**, couverture 100 %, conjoncture « normal » :

* **PIB, à 1 an** : [-1,38 Md€ ; +3,81 Md€], central +1,24 Md€
* **PIB, à 2 ans** : [-194 M€ ; +4,93 Md€], central +2,43 Md€
* **PIB, à 3 ans** : [-11 M€ ; +5,02 Md€], central +2,51 Md€
* **emploi, à 1 an** : [-2,82 ; +7,76] milliers ETP, central +2,53
* **emploi, à 2 ans** : [-0,89 ; +22,56] milliers ETP, central +11,11
* **emploi, à 3 ans** : [-0,07 ; +34,60] milliers ETP, central +17,25

> Couche macro (L4) : ordre de grandeur et composition, pas une prévision. L'éventail des estimations crédibles pour un même choc est large — la dispersion entre études publiées est du même ordre que la valeur centrale elle-même. C'est une propriété de la littérature, pas de ce modèle.

Ce que la chaîne ne lit pas, et pourquoi :

* **IS et investissement des entreprises** — aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis.
* **transferts** — Mésange n'a pas de variante de transfert.
* **créations d'entreprises** — C8 est un indice illustratif de la couche entreprises, en points de taux de création de sociétés, jamais une recette : la trajectoire chiffre le coût d'une baisse d'IS (D-244), pas les sociétés qu'elle ferait naître (§6.3, D-221).
* **R&D et CIR** — C9 est un indice illustratif de la couche entreprises, en euros de R&D, jamais une recette.

### 3. La dette en 2035

| persistance | vue | Δ dette 2035, à θ½ | aux coins de la boîte |
|---|---|---|---|
| Effet macro éteint après trois ans | vieillie | +0,82 pt | de +0,68 pt à +0,96 pt |
| Effet macro éteint après trois ans | figée | +0,65 pt | de +0,56 pt à +0,74 pt |
| Effet macro tenu au niveau de la troisième année | vieillie | +0,32 pt | de -0,19 pt à +0,83 pt |
| Effet macro tenu au niveau de la troisième année | figée | +0,25 pt | de -0,14 pt à +0,64 pt |

En points de PIB de 2035, la dette avec la mesure moins la dette sans elle. La vue vieillie fait vieillir la population chaque année avec les salaires ; la vue figée la garde telle qu'elle est. Sur ces passes, son effet sur la dette en 2035 **dépend de θ** : son signe change d'un coin de la boîte, ou d'une vue, à l'autre.

### L'écart au chiffrage officiel

Enregistré le 2026-10-14, sur le commit `b24de21`, avant l'ouverture de l'annexe : simulé +2,93 Md€, publié +4,20 Md€ (PLF 2027, évaluations préalables des articles, art. 2, § 4.2.1.1, p. 29 : « le rendement de l'IR aurait été majoré d'environ 4,2 Md€ en 2027 »). Écart -1,27 Md€ (-30,3%), pour une tolérance déclarée de 840 M€ : **hors de la tolérance**.

La première année de cette étude, sur le code de l'étude, chiffre +2,83 Md€, soit -99 M€ de l'enregistrement. Le chiffre noté reste celui de l'enregistrement : c'est lui qui a été préenregistré.

## Art. 3 — Réduction à 3 000 € du plafond de l'abattement d'impôt sur le revenu en faveur des bénéficiaires de pensions de retraite

*PLF 2027 (AN, texte n° 3210), art. 3 — Réduction à 3 000 € du plafond de l'abattement d'impôt sur le revenu en faveur des bénéficiaires de pensions de retraite. Revenus 2026.*

Le levier déplace le plafond commun (4 439 € dans l'arbre en 2026, non indexé) : exact sur cette population, dont la seule pension est une pension de retraite. Contrefactuel : l'arbre gelé, pas l'arbre après l'art. 2, qui porterait le plafond à environ 4 532 €.

### 1. Ce qu'il coûte, et qui y gagne

La mesure rapporte **1,12 Md€** la première année (revenus 2026), sur la population de 2024 au droit de 2026.

| décile | ménages | niveau de vie moyen | delta moyen | gagnants | perdants |
|---|---|---|---|---|---|
| 1 | 3 102 007 | 8 273 € | +0 € | 0 % | 0 % |
| 2 | 3 100 131 | 13 306 € | +0 € | 0 % | 0 % |
| 3 | 3 102 584 | 16 595 € | +0 € | 0 % | 0 % |
| 4 | 3 101 315 | 19 726 € | -0 € | 0 % | 0 % |
| 5 | 3 100 962 | 22 590 € | -7 € | 0 % | 6 % |
| 6 | 3 101 037 | 25 476 € | -28 € | 0 % | 17 % |
| 7 | 3 101 015 | 28 843 € | -50 € | 0 % | 30 % |
| 8 | 3 101 048 | 32 961 € | -73 € | 0 % | 34 % |
| 9 | 3 101 712 | 39 197 € | -110 € | 0 % | 31 % |
| 10 | 3 101 552 | 61 679 € | -92 € | 0 % | 21 % |

Les déciles sont ceux du niveau de vie de la population simulée. Toute structure
plus fine qu'un décile est un artefact de l'imputation, pas un résultat.


### 2. Avec les comportements et l'économie

**Bande comportementale : aucune, et la raison est donnée.** Aucun canal fondé sur des preuves ne couvre cet instrument : le chiffre reste purement mécanique.

**L'effet sur l'économie**, l'éventail macro de grade **in-support**, couverture 100 %, conjoncture « normal » :

* **PIB, à 1 an** : [-1,51 Md€ ; +547 M€], central -491 M€
* **PIB, à 2 ans** : [-1,95 Md€ ; +77 M€], central -962 M€
* **PIB, à 3 ans** : [-1,99 Md€ ; +4 M€], central -992 M€
* **emploi, à 1 an** : [-3,07 ; +1,11] milliers ETP, central -1,00
* **emploi, à 2 ans** : [-8,93 ; +0,35] milliers ETP, central -4,40
* **emploi, à 3 ans** : [-13,70 ; +0,03] milliers ETP, central -6,83

> Couche macro (L4) : ordre de grandeur et composition, pas une prévision. L'éventail des estimations crédibles pour un même choc est large — la dispersion entre études publiées est du même ordre que la valeur centrale elle-même. C'est une propriété de la littérature, pas de ce modèle.

Ce que la chaîne ne lit pas, et pourquoi :

* **IS et investissement des entreprises** — aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis.
* **transferts** — Mésange n'a pas de variante de transfert.
* **créations d'entreprises** — C8 est un indice illustratif de la couche entreprises, en points de taux de création de sociétés, jamais une recette : la trajectoire chiffre le coût d'une baisse d'IS (D-244), pas les sociétés qu'elle ferait naître (§6.3, D-221).
* **R&D et CIR** — C9 est un indice illustratif de la couche entreprises, en euros de R&D, jamais une recette.

### 3. La dette en 2035

| persistance | vue | Δ dette 2035, à θ½ | aux coins de la boîte |
|---|---|---|---|
| Effet macro éteint après trois ans | vieillie | -0,35 pt | de -0,39 pt à -0,30 pt |
| Effet macro éteint après trois ans | figée | -0,27 pt | de -0,30 pt à -0,24 pt |
| Effet macro tenu au niveau de la troisième année | vieillie | -0,15 pt | de -0,34 pt à +0,05 pt |
| Effet macro tenu au niveau de la troisième année | figée | -0,11 pt | de -0,26 pt à +0,03 pt |

En points de PIB de 2035, la dette avec la mesure moins la dette sans elle. La vue vieillie fait vieillir la population chaque année avec les salaires ; la vue figée la garde telle qu'elle est. Sur ces passes, son effet sur la dette en 2035 **dépend de θ** : son signe change d'un coin de la boîte, ou d'une vue, à l'autre.

### L'écart au chiffrage officiel

Enregistré le 2026-10-14, sur le commit `be5b5f6`, avant l'ouverture de l'annexe : simulé -1,29 Md€, publié -1,10 Md€ (PLF 2027, évaluations préalables des articles, art. 3, § 4.2, p. 36 : « un gain budgétaire estimé à 1,4 Md€ en 2027, 1,8 Md€ en 2028 et 1,1 Md€ à compter de 2029 »). Écart -195 M€ (-17,7%), pour une tolérance déclarée de 330 M€ : **dans la tolérance**.

La première année de cette étude, sur le code de l'étude, chiffre -1,12 Md€, soit +175 M€ de l'enregistrement. Le chiffre noté reste celui de l'enregistrement : c'est lui qui a été préenregistré.

## Art. 15 — Mise à contribution des grandes entreprises

*PLF 2027 (AN, texte n° 3210), art. 15 — Mise à contribution des grandes entreprises. Volet chiffré : le troisième exercice de la CEBGE, à 15,7 % et 31,4 %, seuil de 1,5 Md€ (I de l'article), la réforme que `reforms/plf2027_art_15.json` porte et que son enregistrement a chiffrée.*

Ne porte PAS la contribution sur le résultat d'exploitation des transporteurs maritimes (II). Le texte rétablit la CEBGE pour l'exercice 2027 seul : la mesure est bornée à cette année (D-288).

### 1. Ce qu'il coûte, et qui y gagne

La mesure rapporte **7,05 Md€** en 2027, sur les entreprises de 2023 au droit de 2027.

| taille | entreprises | touchées | impôt en plus |
|---|---|---|---|
| micro | 2 548 832 | 0 | +0 € |
| PME | 162 238 | 0 | +0 € |
| ETI | 6 995 | 26 | +172 M€ |
| GE | 311 | 186 | +6,88 Md€ |

Population d'entreprises synthétique : effectifs et agrégats par secteur × taille issus de sources publiques, financiers de chaque entreprise tirés paramétriquement à l'intérieur de sa cellule. Résultats au niveau secteur × taille uniquement — aucun résultat par entreprise, aucune affirmation sur le haut de la distribution. La CFE n'est pas simulée : elle dépend de valeurs locatives communales et de milliers de taux locaux, et une imitation plausible serait pire qu'un trou déclaré.

### 2. Avec les comportements et l'économie

**Bande comportementale : aucune, et la raison est donnée.** Aucun canal fondé sur des preuves ne couvre cet instrument : le chiffre reste purement mécanique.

Ce que la chaîne ne lit pas, et pourquoi :

* **IS et investissement des entreprises** — aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis.
* **transferts** — Mésange n'a pas de variante de transfert.
* **créations d'entreprises** — C8 est un indice illustratif de la couche entreprises, en points de taux de création de sociétés, jamais une recette : la trajectoire chiffre le coût d'une baisse d'IS (D-244), pas les sociétés qu'elle ferait naître (§6.3, D-221).
* **R&D et CIR** — C9 est un indice illustratif de la couche entreprises, en euros de R&D, jamais une recette.
* **rétroaction PIB → recettes** — aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un constat.
* **multiplicateur macro** — aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un constat.

### 3. La dette en 2035

La mesure ne s'applique qu'en 2027 : le chemin la chiffre cette année-là et ne lui prête rien les autres (D-288).

| persistance | vue | Δ dette 2035, à θ½ | aux coins de la boîte |
|---|---|---|---|
| Effet macro éteint après trois ans | vieillie | -0,23 pt | de -0,23 pt à -0,23 pt |
| Effet macro éteint après trois ans | figée | -0,20 pt | de -0,20 pt à -0,20 pt |
| Effet macro tenu au niveau de la troisième année | vieillie | -0,23 pt | de -0,23 pt à -0,23 pt |
| Effet macro tenu au niveau de la troisième année | figée | -0,20 pt | de -0,20 pt à -0,20 pt |

En points de PIB de 2035, la dette avec la mesure moins la dette sans elle. La vue vieillie fait vieillir la population chaque année avec les salaires ; la vue figée la garde telle qu'elle est. Sur ces passes, elle **baisse la dette** en 2035, à θ½ comme à chaque coin de la boîte, dans les deux vues.

### L'écart au chiffrage officiel

Enregistré le 2026-10-14, sur le commit `e449490`, avant l'ouverture de l'annexe : simulé -7,05 Md€, publié -5,50 Md€ (PLF 2027, évaluations préalables des articles, art. 15, § 4.2.1, p. 160 : « 5 Md€ au titre des acomptes attendus en 2027. Un rendement de 500 M€ est attendu en 2028 au titre du paiement de la contribution par les entreprises dont la clôture de l'exercice comptable est décalée »). Écart -1,55 Md€ (-28,3%), pour une tolérance déclarée de 1,65 Md€ : **dans la tolérance**.

La première année de cette étude, sur le code de l'étude, chiffre -7,05 Md€, soit +0 € de l'enregistrement. Le chiffre noté reste celui de l'enregistrement : c'est lui qui a été préenregistré.

## Les 30 autres articles

Un article refusé n'est pas un article à zéro. Le refus est pris sur le texte, avant tout chiffrage, et sa raison est dite : hors du périmètre (`scope`), hors de la structure du modèle (`structure`), ou hors de ses données (`data`).

| art. | intitulé | case | pourquoi |
|---|---|---|---|
| 1 | Autorisation de percevoir les impôts existants | `scope` | Formalité reconduite chaque année, pas une mesure. |
| 4 | Mesure temporaire d'allègement de la fiscalité des donations pour encourager les transmissions intergénérationnelles | `structure` | Aucun modèle de transmission : ni donation, ni patrimoine transmis, ni barème des droits de mutation. |
| 5 | Recentrage du dispositif de l'apport-cession sur son objectif de soutien à l'investissement | `data` | Aucune plus-value ni aucun report d'imposition dans la population. |
| 6 | Protection du modèle de l'assurance-vie | `data` | Aucun revenu de l'épargne dans la population. |
| 7 | Réorienter les soutiens publics vers le logement familial et de longue durée | `data` | Ni prêt à taux zéro, ni revenu locatif meublé ou nu dans la population. |
| 8 | Soutien au logement social | `structure` | Exonérations de taxe foncière et d'IS des organismes HLM : ni bailleur social ni taxe foncière par logement dans le modèle. |
| 9 | Soutien à l'industrie | `structure` | Le modèle entreprises n'a ni investissement ni amortissement : un suramortissement n'a pas d'assiette. |
| 10 | Soutien aux reprises d'entreprises (pacte « Papin ») | `structure` | Ni transmission ni reprise d'entreprise dans le modèle. |
| 11 | Prorogation d'un an de l'application du crédit d'impôt pour la compétitivité et l'emploi à Mayotte | `data` | Ni Mayotte ni masse salariale par territoire dans la population d'entreprises. |
| 12 | Soutien au secteur culturel | `structure` | Crédits d'impôt sectoriels — l'IS de ce modèle est un IS avant créances — et taxe sur la publicité des plateformes vidéo : aucune assiette. |
| 13 | Soutien au secteur agricole | `data` | Aucun bénéfice agricole dans la population, comme en septembre. |
| 14 | Soutien aux entreprises touchées par les incendies de l'été 2026 | `data` | Ni localisation départementale des entreprises ni sinistre. |
| 16 | Rationalisation des taux de taxe sur la valeur ajoutée applicables aux services de télévision | `structure` | Pas de TVA par taux : F8 attend le budget de famille. |
| 17 | Ajustements sur les taxes sur les réductions de capital | `structure` | Ni rachat ni annulation de titres dans le modèle. |
| 18 | Aménagement du régime des provisions assurantielles | `structure` | Aucune provision dans le modèle entreprises. |
| 19 | Mesures diverses de correction, clarification et coordination en matière de fiscalité sur les biens et services | `structure` | Ajustements de fiscalité indirecte, hors du modèle. |
| 20 | Création de tarifs réduits de taxes sur les installations nucléaires de base applicables pendant la phase de construction | `structure` | Aucune installation de production d'énergie dans le modèle. |
| 21 | Adaptation de la fiscalité aérienne au soutien à la continuité territoriale | `structure` | Ni vol ni passager dans le modèle. |
| 22 | Renforcement de la taxe sur l'exploitation des infrastructures de transport de longue distance pour les exploitants les plus rentables | `structure` | Aucun exploitant d'infrastructure identifiable dans la population d'entreprises. |
| 23 | Instauration d'un prélèvement exceptionnel sur les avoirs en déshérence déposés auprès de la Caisse des dépôts et consignations | `structure` | Ni avoir bancaire ni Caisse des dépôts dans le modèle. |
| 24 | Soutien à l'électrification et renforcement des incitations environnementales dans le secteur des transports | `structure` | Fiscalité des carburants, hors du modèle. |
| 25 | Mesures relatives à la fiscalité des véhicules | `structure` | Aucun véhicule dans le modèle. |
| 26 | Prorogations d'exonérations et précisions en matière de fiscalité locale | `structure` | Régimes zonés, sans localisation fine dans le modèle. |
| 27 | Mesures relatives au financement du service public de la justice | `structure` | Droits et taxes affectés à l'aide juridictionnelle, hors du modèle. |
| 28 | Mise à jour de références au droit de l'Union européenne dans des dispositifs fiscaux | `scope` | Mise en conformité juridique, sans paramètre chiffrable. |
| 29 | Nouvelle étape de la relation de confiance | `scope` | Procédure. |
| 30 | Renforcement de la lutte contre la fraude fiscale et mesures anti-contournement | `scope` | Procédure et contrôle. |
| 31 | Modernisation et simplification des procédures fiscales | `scope` | Procédure. |
| 32 | Sécurisation et amélioration de la lisibilité de dispositifs fiscaux mis en œuvre par la douane | `structure` | Accises et détaxe, hors du modèle. |
| 33 | Modalités d'entrée en vigueur des mesures fiscales | `scope` | Fixe les dates : le 31 décembre 2026 pour l'IR et l'IS, ce qui place les mesures d'IR sur les revenus 2026 et le troisième exercice de la CEBGE en 2027. |

## D'où viennent ces nombres

Les passes ont tourné sur le commit `02fd623`, dans le conteneur de la session, en tâche de fond, depuis une copie de travail figée sur 02fd623. Cadre du chemin annuel : Croissance réelle 1 %, prix 2 % ; Taux implicite tenu à son niveau de 2025 ; Dépenses gelées en volume ; droit reconduit tel qu'openfisca le porte ; θ½ sur toutes les lignes ; comportements et boucle macro appliqués.

*Population vieillie mécaniquement de 2024 à 2035 — salaires 3,0 % par an, prix 2,0 % par an, hypothèses DÉCLARÉES et non prévues (3 % ronds, le rythme du PIB nominal du scénario). La structure des ménages, les âges et les poids n'ont PAS bougé : c'est la France de l'année de base avec l'argent de l'année d'arrivée, et cela biaise vers l'immobilité démographique. **Cette population n'est plus calibrée** : les totaux dépensés au registre le sont sur l'année de base, et il n'existe pas de total publié pour une année future. Toute ligne de réconciliation sur cette année refuse un verdict de tolérance plutôt que d'en donner un qui se lirait comme une validation.*

* `reports/etude_plf2027/premiere_annee_plf2027_art_2.json`, `reports/etude_plf2027/predictif_plf2027_art_2.json`, `chiffrages_preregistres/plf2027_art_2.yaml`
* `reports/etude_plf2027/premiere_annee_plf2027_art_3.json`, `reports/etude_plf2027/predictif_plf2027_art_3.json`, `chiffrages_preregistres/plf2027_art_3.yaml`
* `reports/etude_plf2027/premiere_annee_plf2027_art_15.json`, `reports/etude_plf2027/predictif_plf2027_art_15.json`, `chiffrages_preregistres/plf2027_art_15.yaml`
