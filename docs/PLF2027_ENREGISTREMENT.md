# PLF 2027 — les trois enregistrements, prêts à lancer

**Écrit le 2026-10-02, le lendemain de la parution, avant qu'aucun chiffre existe.** Les
tolérances, leurs justifications et les comparateurs ci-dessous sont committés avant le
premier calcul : c'est ce qui en fait des engagements. Les changer après avoir vu un
résultat est exactement l'élargissement que `verify_tolerance_unchanged` attrape dans
l'historique git.

**Mis à jour le 2026-10-04, toujours avant tout chiffre.** La branche `claude/plf2027` est
fusionnée dans `main` (#9), qui porte aussi D-176 et toutes les entrées qui la suivent. Les
commandes partent donc de `main` : c'est sur cette tête, avec ses corrections, que les
chiffrages se calculent. Les enregistrements sont poussés sur une branche à eux. Seules les
références de branche ont changé : ni tolérance, ni justification, ni comparateur.

## Pourquoi ces commandes tournent chez le propriétaire

Ce conteneur cloud n'atteint pas l'INSEE : la connexion s'établit, puis le serveur ne
répond pas (504, puis 502). Sans l'enquête Emploi et les fichiers Ésane, ni la
population ménages ni la population d'entreprises ne se construisent ici, et donc ni
`make full` ni les chiffrages. Tout le reste a été fait sur la branche `claude/plf2027`,
depuis fusionnée dans `main` :

* le texte n° 3210 manifesté, et le découpeur corrigé (il écartait les articles 23, 38
  et 47) ;
* le tri des 33 articles fiscaux, dans `plf_coverage.ARTICLES_2027` et
  `docs/PLF2027_COVERAGE.md` ;
* les leviers manquants : `abattement_pensions_plafond` (art. 3), la prorogation de la
  CEBGE et `chiffrage register-entreprises` (art. 15) ;
* les trois réformes dans `reforms/`, et les deux scénarios ménages, datés du
  2026-10-02.

## La règle, jusqu'au dernier commit d'enregistrement

* **Ne pas ouvrir l'annexe des évaluations préalables**, et ne lire aucun montant dans la
  presse. Ce que la session avait vu avant est consigné dans D-174.
* **Un commit par enregistrement.** Le fichier n'est pas le préenregistrement : le commit
  l'est.
* **Aucune tolérance modifiée** après le premier calcul. Une révision est un nouveau cas,
  sous un nouveau nom, daté du jour.

## 0. Avant tout calcul

```bash
git fetch origin main && git checkout -b plf2027-enregistrements origin/main
make data            # si population_2024.parquet manque
.venv/bin/impots entreprises cells
.venv/bin/impots entreprises build --cells data/processed/firm_cells_2023.json
make full            # une ligne PASS dans reports/full_pass_log.md, sur cette tête
git add reports/full_pass_log.md reports/full_pass_durations.md
git commit -m "Passe complète avant les préenregistrements PLF 2027"
git status --short   # l'arbre doit être propre
```

`firms_2023.manifest.json` doit dire `"cells_are_synthetic": false`.
`register-entreprises` refuse une population qui ne le dit pas.

## 1. Article 2 — la revalorisation du barème

```bash
.venv/bin/python -m impots.population.cli chiffrage register plf2027_art_2 \
  --scenario plf2027_art_2 --sample 20000 \
  --tolerance-relative 0.20 --tolerance-absolute 200e6 \
  --tolerance-rationale "Revalorisation de 2,1 % des tranches, de la décote et du plafond général de la demi-part, contre un arbre gelé aux paramètres des revenus 2025. Plus ou moins 20 % parce que : la ligne IR au barème de cette population sort à +8,8 % de la DGFiP, et le coût d'une revalorisation suit le niveau de l'impôt ; les revenus sont ceux de 2024, non vieillis, ce qui place moins de foyers au-dessus des seuils 2026 ; le scénario ne porte ni les quatre autres plafonds de quotient familial, ni le 196 B, ni l'indexation des limites de déductions ; la base n'a ni revenu du capital ni revenu d'indépendant ; et le sous-échantillon de 20 000 ménages ajoute un bruit de l'ordre du pour cent. Les trois biais du milieu tirent vers le bas, le premier vers le haut : la direction nette n'est pas connue d'avance, d'où une fenêtre symétrique. Plancher de 200 M EUR pour le cas où le chiffre publié serait petit." \
  --note "Comparateur : le seul volet revalorisation du barème si l'annexe le sépare. Sinon l'article entier, et le cas devient un minorant connu : les volets indemnités de rupture, indemnités journalières, prime carburant et CSG des IJ ne sont pas chiffrés. Le compte d'environ 500 000 foyers qui évitent l'entrée dans l'impôt est déjà vu (exposé des motifs) et ne sert pas de test."
git add chiffrages_preregistres/plf2027_art_2.yaml
git commit -m "Pré-enregistrement : PLF 2027 art. 2"
```

## 2. Article 3 — le plafond de l'abattement sur les pensions

```bash
.venv/bin/python -m impots.population.cli chiffrage register plf2027_art_3 \
  --scenario plf2027_art_3 --sample 20000 \
  --tolerance-relative 0.30 --tolerance-absolute 200e6 \
  --tolerance-rationale "Le plafond abaissé à 3 000 EUR mord sur les foyers dont 10 % des pensions dépassent ce montant, soit plus de 30 000 EUR de pensions déclarées par foyer : la moitié haute de la distribution. Aucune pension n'est observée dans cette population : la masse est calée sur les pensions déclarées (DGFiP) et sa distribution tirée de lois publiées ; les pensions d'un couple sont tirées sans corrélation ; le taux marginal des foyers retraités dépend de revenus du capital et fonciers que la population n'a pas, ce qui tire vers le bas. Le contrefactuel est l'arbre gelé (plafond de 4 439 EUR), pas l'arbre revalorisé par l'art. 2 (environ 4 532 EUR) : léger biais vers le bas. Plus ou moins 30 % parce que l'incertitude porte sur une queue de distribution que la population construit plus qu'elle n'observe. Plancher de 200 M EUR." \
  --note "Comparateur : l'article seul. Le compte de 4,6 M de foyers touchés est déjà vu (D-174) et ne sert pas de test."
git add chiffrages_preregistres/plf2027_art_3.yaml
git commit -m "Pré-enregistrement : PLF 2027 art. 3"
```

## 3. Article 15 — la CEBGE, troisième exercice

```bash
.venv/bin/python -m impots.population.cli chiffrage register-entreprises plf2027_art_15 \
  --reform reforms/plf2027_art_15.json --year 2027 --vintage 2023 \
  --tolerance-relative 0.30 --tolerance-absolute 200e6 \
  --tolerance-rationale "Troisième exercice de la CEBGE (2027) à 15,7 % et 31,4 %, seuil de 1,5 Md EUR, contre un droit courant où elle s'est éteinte. La CEBGE de cette population est réconciliée à +23,1 % du rendement publié de son premier exercice (9,3 contre 7,5 Md EUR) : le niveau est biaisé vers le haut, et ce biais se reporte. S'y ajoutent l'absence de report déficitaire et d'intégration fiscale (IS simulé vers le haut), un seul exercice au lieu de deux pour l'assiette et les tests de seuil, et un ratio fiscal/comptable national unique. Direction attendue : au-dessus. Plus ou moins 30 % : assez pour contenir le biais déjà mesuré, pas assez pour qu'un défaut de structure passe inaperçu. Plancher de 200 M EUR." \
  --note "Comparateur : le seul volet CEBGE (I de l'article). La contribution sur le résultat d'exploitation des transporteurs maritimes (II) n'est pas chiffrée. Population : SIRENE x ESANE 2023, pas les cellules de test."
git add chiffrages_preregistres/plf2027_art_15.yaml
git commit -m "Pré-enregistrement : PLF 2027 art. 15"
```

## 4. Ensuite

```bash
git push -u origin plf2027-enregistrements
```

Seulement après ce push : relever l'URL de l'annexe sur la page du dossier `PLF_2027`
de l'Assemblée, la manifester, puis saisir les comparateurs et noter (runbook, étape 5).
Un cas rouge est un constat à écrire, jamais un nombre à faire disparaître.

La branche entre ensuite dans `main` par une PR fusionnée, jamais écrasée : un « squash »
réécrirait les commits d'enregistrement, et c'est leur date qui fait le préenregistrement.
