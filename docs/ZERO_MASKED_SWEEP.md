# Le balayage des comparaisons masquées

> Une comparaison qui n'est juste que parce qu'un des deux côtés est identiquement nul
> n'est pas juste, elle n'est pas testée.

Verdict du relecteur, exécuté sur **toutes** les lignes de réconciliation — ménages et
entreprises. Dix agents, un par groupe de lignes, chacun tenu de *mesurer* sur la
population plutôt que de raisonner, puis une passe de vérification adverse par groupe.

Trois verdicts : **SOUND** (aucun zéro ne porte la ligne), **CONDITIONNELLEMENT VALIDE**
(un zéro porte la ligne, le sens est connu, le statut ne bascule pas), **MASQUÉE** (la
ligne ne passe que parce qu'une composante est vide, ou son résidu n'est pas ce qu'il
prétend mesurer).

## Ce que le balayage a changé dans le code

Résidus sur la **population complète**, qui produit désormais `reports/reconciliation.md` : plus aucun terme d'échantillonnage, après que D-074 a montré que le sous-échantillon était biaisé. Les notes de ligne, dans le rapport lui-même, restent **dérivées** de leur propre passage plutôt que recopiées d'ici.

| Ligne | Avant | Après | Nature |
|---|---|---|---|
| Niveau de vie médian | −12,2 % | −5,0 % | **mauvais estimateur** : moyenne du décile 5 contre une médiane publiée |
| Rapport interdécile D9/D1 | +39,1 % | +3,6 % | **mauvais estimateur** : rapport de moyennes de déciles contre un rapport de seuils |
| Allocataires AF | *aucune ligne* | −12,3 % | figure `use="validation"` imprimée en Sources, jamais comparée |
| Allocataires prime d'activité | *aucune ligne* | +6,5 % | idem |
| Foyers allocataires du RSA | *aucune ligne* | **+96,3 %** | idem |
| Allocataires d'une aide au logement | *aucune ligne* | −18,0 % | idem |
| Pensions et retraites | `None` | −0,05 % | comparait un `None` en affichant « calibrated (spent) » |
| Allocations chômage | `None` | +0,26 % | idem |
| IR — barème | lisait `ir` | `ir_avant_niches` | net contre une cible brute (D-069) |

**Deux lignes se sont améliorées à cause d'un changement que nous avons fait**, ce qui
est précisément le mouvement qui mérite d'être suspecté. Les deux sont des corrections
d'estimateur : la statistique publiée est un quantile pondéré par personne, la nôtre
était une moyenne de décile pondérée par ménage. Le tableau de déciles lui-même reste
pondéré par ménage — c'est ce dont l'incidence d'une réforme a besoin — et
`test_the_decile_table_itself_is_still_household_weighted` interdit que la correction y
fuie.

**Une figure a été mesurée deux fois.** Le balayage annonçait que D9/D1 sortait de sa
tolérance dès 10 % de capital ajouté. Notre propre mesure donne +5,5 points de résidu,
ce qui la laisse dedans. Le sens était bon, la magnitude non, et c'est la mesure qui tranche
(D-026 : la prose d'un agent n'est jamais la source d'une figure).

## Les zéros, ligne par ligne

### Ménages — IR

| Ligne | Verdict | Le zéro | Sens si non nul |
|---|---|---|---|
| IR — barème | conditionnel | Base catégorielle à 100 % TSPR ; fonciers, BIC/BNC, RCM ≡ 0 | **+3,3 points** avec 10 md de fonciers, assez pour sortir de ±10 % |
| IR — recettes nettes | **masquée** | `reductions`/`credits_impot` ≡ 0 (le rapport n'active jamais `impute_niches`) ; PFU absent | Les deux zéros se compensent partiellement, ce qui rend la ligne présentable |
| Salaires déclarés | conditionnel | Chômage imposable (36,1 md) **exclu de la somme comparée** ; art. 62, non-résidents ≡ 0 | **+3,8 points**, assez pour retourner le **signe** |
| Foyers fiscaux | **sain** | Non-résidents seuls ; +0,85 %, un vingtième du résidu | — |
| Foyers imposés | **masquée** | Compte au seul barème déguisé en compte d'imposés | **−6,4 points** à 10,66 md de niches ; les 19,53 md complets sortent de ±10 % |

### Ménages — prestations

| Ligne | Verdict | Le zéro | Sens si non nul |
|---|---|---|---|
| Allocations familiales | conditionnel | `residence_dom` ≡ False malgré 0,90 M de ménages ultramarins (`region` absente des inputs ménage) | +0,79 %, pas de bascule |
| Prime d'activité | **masquée** | `loyer_mensuel` ≡ 0 chez 8,01 M de primo-accédants → forfait logement appliqué à tort | **+22,5 points**, qui font **basculer le statut** de dedans à dehors |
| RSA | **masquée** | `aefa` absent de la ligne ; même `loyer_mensuel` ; aah/asi/ass ≡ 0 en sens inverse | +5,7 pts (`aefa`), +10,6 (mensualité), +16,3 (les deux) ; solde entre trois erreurs connues |
| Aides au logement | **masquée** | Pas de pont (×1,00 implicite) ; `locataire_foyer` inatteignable ; APL accession nulle ; `zone_apl` jamais zone 1 | Deux sens : la lecture imprimée est **la plus flatteuse disponible** |

### Ménages — distribution

| Ligne | Verdict | Le zéro |
|---|---|---|
| Niveau de vie médian | conditionnel | `revenus_nets_du_capital` ≡ 0 ; +5,1 points de résidu à f=10 %, +7,6 à f=15 % |
| D9/D1 | conditionnel | Idem ; +2,9 / +5,5 / +8,4 points à f=5/10/15 % — le sens est net, la bascule n'arrive pas sur la plage testée |
| Ménages | **sain** | Aucun ; les cinq types sont peuplés |
| Masse salariale brute | **masquée** | Le résidu **n'est pas** un résidu de calibration (erreur mesurée : 0,0000 %) ; secteur public non câblé (5,8 M de salariés, `categorie_salarie` = privé pour tous) |
| Pensions et retraites | **masquée** → corrigée | Rentes viagères hors modèle ; comparait un `None` |
| Allocations chômage | **masquée** → corrigée | Chômeurs non indemnisés ≡ 0 des deux côtés ; comparait un `None` |

### Entreprises

| Ligne | Verdict | Le zéro |
|---|---|---|
| Bénéfice imposable total | conditionnel | Report déficitaire, intégration fiscale, résultat négatif tous ≡ 0 |
| Impôt sur les sociétés | conditionnel | Crédits d'impôt (CIR ≈ 7 md) ≡ 0 |
| Taux moyen d'IS | conditionnel | Idem, **zéro apparié** des deux côtés — non signalé jusqu'ici |
| IS — recettes nettes | **masquée** | Crédits d'impôt **et** remboursements/dégrèvements (24,6 md) ≡ 0, empilés du même côté → pousse **vers la cible** |
| Contribution sociale sur l'IS | conditionnel | Section K ≡ 0 ; 614 entreprises exonérées à tort |
| CEBGE | **masquée** | `is_avant_report − impot_societes` ≡ 0 : la moyenne de deux exercices de la LF 2025 art. 48 est arithmétiquement inerte |
| CVAE | **masquée** | Sections A, K, P, Q, S ≡ 0 hors micro → pousse **vers la cible** |
| C3S | **masquée** | Section K ≡ 0,00 exactement |
| Entreprises redevables | **masquée** | `is_share` = 1,0 pour PME/ETI/GE : **la ligne ne peut pas bouger** |
| Part sans bénéfice imposable | **masquée** | Trois composantes nulles, à +3,78 % d'une cible censée être reproduite par construction |

## Ce qui reste ouvert

Par ordre de gravité. Aucun de ces points n'est corrigé ici ; ils sont sur le registre
pour être choisis, pas pour être oubliés.

1. **`loyer_mensuel` ≡ 0 chez 8,01 M de primo-accédants.** `incomes` n'impute un loyer
   qu'aux locataires. C'est un défaut de **population**, pas de rapport : il fausse le
   forfait logement de la PPA et du RSA pour un ménage sur quatre. Corriger la
   population fait **sortir la PPA de sa tolérance** — ce qui est le bon résultat, et la
   raison de le faire délibérément plutôt que par accident.
2. **Sept lignes IS sectorielles jamais balayées** (`reconcile.py:141-186`), dont trois
   hors tolérance — Industrie à +38,3 %.
3. **« Taux effectif moyen » a un numérateur à cinq prélèvements** (IS + contribution
   sociale + CEBGE + CVAE + C3S, 88,5 md) et non l'IS seul. Idem pour l'écart GE−PME,
   mesuré à +0,19 tous prélèvements contre +0,018 en IS seul, face à un publié INSEE
   de −0,071.
4. **`IS_BRUT_BY_SIZE` défini et référencé nulle part.**
5. **Le secteur public n'est pas câblé** — et la ligne qui devrait le détecter est
   structurellement incapable de le faire.
6. **`region` existe au parquet, absente des inputs ménage** : les DOM n'existent pas
   pour openfisca.
7. **`locataire_foyer` et `zone_apl = zone_1` sont inatteignables** par construction de
   `skeleton.py`.
8. **`statut_activite` (dont 69 927 étudiants) n'est jamais câblé** : le régime étudiant
   des AL ne s'applique jamais.

## Les gardes qui restent

`tests/test_zero_masked.py` — les gardes composant-non-nul, estimateur, et
comparaison-effectivement-faite. `tests/test_niche_imputation.py` — la garde de la
ligne barème. Le principe : une ligne qui ne passe que parce qu'une composante est vide
doit **échouer bruyamment** le jour où elle se remplit, jamais dériver en silence.

## Le drapeau qui manquait

Deux lignes masquées — l'IR net et les foyers imposés — n'avaient **aucune autre lecture
disponible** : `cmd_reconcile` ne passait jamais `impute_niches`, et
`docs/B3_IR_NICHES.md` documentait un `--impute-niches` qui n'existait sur aucune
commande. `--impute-niches` existe maintenant sur `population run` et sur
`population reconcile`, à faux par défaut. Mesuré avec le drapeau :

| Ligne | Sans | Avec |
|---|---|---|
| IR — recettes nettes | +22,5 % | **+10,4 %** |
| Foyers imposés | −2,3 % | **−8,8 %** |
| IR — barème | +8,7 % | **+8,7 %** |

La troisième ligne est celle qui compte : le barème **ne bouge pas**, parce que les
niches se retranchent après lui. C'est ce qui dit que la correction est juste et pas
seulement favorable, et c'est le test que `test_the_bareme_line_is_untouched_by_imputation`
tient.

## Post-scriptum — l'échantillonneur (D-074)

Le balayage a été exécuté sur des tirages de 20 000 et 50 000 ménages. L'échec de gate
qu'il a laissé derrière lui a fait découvrir que **le sous-échantillon était biaisé** :
`np.random.choice(replace=False, p=w)` n'est pas un tirage PPS, et le biais **croissait**
avec la taille du tirage. Corrigé par une strate exhaustive plus un PPS systématique.

Deux conséquences pour ce document. D'abord, les résidus cités ici sont désormais ceux de
la **population complète**, qui n'a aucun terme d'échantillonnage. Ensuite, les
**sensibilités mesurées** (les contrefactuels : +22,5 points sur la PPA, +3,3 sur le
barème, etc.) ont été mesurées sur des tirages produits par l'ancien échantillonneur. Ce
sont des *écarts* entre deux passages du même tirage, donc l'essentiel du biais s'y
annule — mais elles n'ont pas été refaites, et c'est écrit ici plutôt que passé sous
silence.

Un chiffre pour situer le bruit : sur quatre graines à n=50 000, la ligne du barème vaut
+6,90 %, +10,23 %, +8,18 %, +9,62 % — moyenne +8,73 % contre +8,8 % en population
complète. Sans biais, mais 1,49 point d'écart-type par tirage, du même ordre que la
tolérance de la ligne.
