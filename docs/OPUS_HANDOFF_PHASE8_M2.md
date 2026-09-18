# Handoff — Phase 8, état au 2026-09-18, et ce qui reste

**Pour qui ce document est écrit.** Pour l'agent qui reprend le développement sans avoir vu
la session précédente. Il suppose `docs/PHASE8_SPEC.md` lu, et `docs/DECISIONS.md` D-140 à
D-148 lues — elles portent les raisons, ce document porte l'état et l'ordre de marche.

---

## 0. L'avertissement en premier, parce qu'il conditionne tout le reste

**`make full` n'a pas tourné depuis la correction du manifeste (`238907b`).** La dernière
passe complète, sur `46bc81f`, est ROUGE au journal :

```
| 2026-09-18 | `46bc81f` | FAIL | 69m53s | 8 failed, 1393 passed, 4 skipped, 10 warnings |
```

Ces 8 échecs sont corrigés (voir §3), et vérifiés par des runs ciblés — mais **l'arbre
entier n'a pas été revalidé**. Le propriétaire a demandé d'arrêter les passes longues
(« you have to stop with the big tests, don't do that »), donc tout le travail depuis se
vérifie par des runs ciblés. **Ne pas lancer `make full` sans le lui demander.** Quand il
l'autorisera, c'est la première chose à faire, et la ligne du journal doit être reportée.

Corollaire opérationnel appris à la dure : la cible `full` estampille sa ligne avec
`git rev-parse HEAD` **à la fin**. Committer pendant qu'elle tourne attribue le résultat à
un arbre qu'elle n'a jamais testé. Ne pas committer pendant une passe.

---

## 1. La discipline, en cinq lignes non négociables

Tout est dans `DECISIONS.md`, mais ces cinq-là expliquent la forme de presque tout le code
écrit cette session :

1. **Toute garde livre son test de mise à mort, et on l'a VUE échouer.** Une garde jamais
   vue échouer n'est pas une garde.
2. **Tout contrôle doit nommer l'implémentation qui le ferait tomber.** Si on ne peut pas
   la nommer, le contrôle ne contrôle rien.
3. **Forme D-044** : un contrôle dérivé de la chose qu'il contrôle ne peut pas échouer
   quand cette chose est fausse. Elle est réapparue trois fois cette session.
4. **Bandé ou absent, jamais faussement assuré.** Un zéro affiché est une affirmation.
5. **Codes, jamais libellés.** L'incident `"IS" in label` est au dossier.

Et une règle de méthode qui a payé trois fois cette session : **quand un test de mise à
mort échoue, suspecter le test d'abord.** Trois « gardes inertes » se sont révélées être
des tests mal posés (injection Python invalide, `hasattr` aveugle aux champs de dataclass,
fixture utilisant la valeur correcte en la nommant « mal lue »).

---

## 2. Ce qui est construit — carte des modules

```
src/impots/dette/
    path.py          §3.1 identité de dette + §6.1 backtest        24 tests
    maturite.py      §3.2 taux implicite sur le Bloc 1 AFT          9 tests
    decomposition.py §3.6 affichage décomposé de l'éventail        16 tests
    comptes.py       §6.1 assemblage des entrées réalisées         14 tests
src/impots/agregats/
    engine.py        §2.2 moteur d'instruments agrégés (seau B)    24 tests
```

87 tests, lint propre. Tous passent en ciblé.

### `dette/path.py`
`step`, `project`, `backtest`. `project` REFUSE sans scénario de dépense nommé.
`PROBABILITY_WORDS` interdit le vocabulaire de vraisemblance. `HORIZON_CAP_YEARS = 10`.

`backtest` prend des `RealizedYear` dont **`sfa` n'a pas de défaut** — la garde est portée
par le type, pas par un contrôle qu'on peut oublier. Il refuse aussi une série de SFA
identiquement nulle, et **enchaîne sur le ratio MODÉLISÉ**, jamais sur le publié : repartir
du publié chaque année transformerait un backtest de sept ans en sept transitions d'un an
isolées, qui passeraient toujours.

### `dette/comptes.py`
Assemble `r`, `g`, `p`, `published_ratio` depuis trois fichiers manifestés. Deux pièges des
fichiers publics y sont épinglés par des contrôles (voir §5). **`sfa` est obligatoire et
refusé s'il est dérivé** (`ImpliedSfa`, voir §4).

### `dette/decomposition.py`
Quatre tranches nommées, **aucune enveloppe combinée, aucun `total`**. Une tranche non
calculée ne porte AUCUNE valeur, `width_at` rend `None` et non `0.0`, et `dominant_source`
refuse de désigner un vainqueur tant qu'une tranche manque.

### `agregats/engine.py`
Ancre de recettes lue DEPUIS le manifeste, surface de refus par liste blanche (aucune
sortie distributionnelle, jamais), ventilation d'assiette qui doit reproduire l'ancre,
élasticité absente dite et non affichée à zéro.

---

## 3. Ce qui a été réparé cette session, à ne pas re-casser

**D-142 — le manifeste ne se chargeait plus.** 18 entrées écrites À LA MAIN portaient
`retrieved` là où le générateur écrit `downloaded`. `load_manifest()` levait une
`TypeError`, donc `require_sourced()` ne faisait plus respecter D-028 depuis des jours. Il
échouait FERMÉ, seule chance de l'affaire.

*Pourquoi rien ne l'a vu* : toutes les assertions de `test_provenance.py` lisent
`MANIFEST.json` en JSON brut ; **aucune ne construisait de `ManifestEntry`**. Le garde
manquant a été ajouté (`test_the_real_manifest_loads_through_the_loader_production_uses`)
et vu échouer sur l'ancien manifeste.

**Règle qui en sort : ne jamais ajouter une entrée de manifeste à la main sans lancer ce
test.** `capture` et `provenance` sont désormais des champs légitimes de `ManifestEntry` —
`provenance` sert aux sources sans URL stable (exports Eurostat personnalisés, livraisons).

**D-143 — le module affirmait faire respecter une garde inexistante.** `path.py` écrivait
« `backtest` prend sfa sans défaut […] appliqué, pas documenté » alors que `backtest`
n'existait pas. Corrigé en écrivant la fonction.

---

## 4. M1 — où ça en est exactement

### Fait
- §3.1 identité + refus (24 tests), §3.2 taux implicite sur le Bloc 1 (9 tests), §3.6
  décomposition (16 tests).
- `comptes.py` assemble les entrées réalisées et les valeurs sont **recoupées contre
  Eurostat** : mon B9/PIB contre `gov_10dd_edpt1`, accord à ≤ 0,04 pt sur sept ans (simple
  arrondi à une décimale d'Eurostat). Cela valide d'un coup l'indice de ligne B9,
  l'alignement des colonnes d'années, la conversion ×1e9 et le dénominateur PIB.

### Le seul blocage : l'ajustement flux-stocks
**§6.1 n'est PAS noté et ne peut pas l'être.** Il manque une seule entrée : le SFA publié,
France, annuel, 2019→2025.

Vérifié exhaustivement : **aucune source de SFA dans le dépôt**, ni parmi les 68 fichiers
sourcés ni parmi les 76 en quarantaine, ni PDF ni tableur. Ne pas recommencer cette
recherche.

Où le prendre : Eurostat `gov_10dd_edpt1`, indicateur *stock-flow adjustment* (le
propriétaire a déjà exporté ce dataset, mais filtré sur `capacité/besoin de financement` —
il faut changer la dimension `na_item`) ; ou les tableaux de notification EDP de l'INSEE.

**Le piège, et c'est le point le plus important de cette section.** Le SFA se DÉRIVE en une
ligne comme résidu `Δdette − déficit`, et les deux termes sont au dépôt. **Ne le faites
pas.** L'identité se refermerait par construction et le backtest rendrait un score parfait
en ne mesurant rien — mesuré : **moins de 0,022 point de PIB d'erreur sur sept ans**. La
garde est mécanique : `sfa_implied_by_identity()` rend des `ImpliedSfa` (sous-classe de
`float`) que `realized_years` refuse par `isinstance`. Elle porte sur la PROVENANCE, pas
sur la valeur — un test jumeau vérifie que les mêmes nombres dépouillés de leur type
passent.

La dérivation sert à **recouper** la série publiée quand elle arrivera. Valeurs attendues
(md€) : 2019 ≈ +8, **2020 ≈ +69**, 2021 ≈ 0, 2022 ≈ +1, 2023 ≈ −4, 2024 ≈ +34, 2025 ≈ +3.
Le pic 2020 est la signature.

### Quand le fichier arrivera — la marche à suivre
1. Lire l'URL d'origine dans les métadonnées macOS (`xattr -p com.apple.metadata:kMDItemWhereFroms`)
   plutôt que la faire retaper.
2. **Vérifier l'empreinte avant tout usage.** Un même nom de fichier sur deux millésimes est
   la façon la plus simple de certifier des octets que personne n'a téléchargés — c'est
   exactement ce qui s'est produit avec la 7.301 (le fichier déposé était le millésime 2025,
   pas celui du dépôt).
3. Manifester. Pour un export Eurostat personnalisé, **l'URL n'est pas stable** (elle pointe
   un UUID de session) : enregistrer le code du dataset et la requête dans `provenance`,
   pas faire semblant que le lien est reproductible.
4. Recouper contre la dérivation. Accord ⇒ l'extraction est validée. Désaccord ⇒ différence
   de périmètre à localiser — les deux sont des constats.
5. **Préenregistrer la tolérance par commit AVANT de calculer le premier résidu.** §6.1
   ajoute : le résidu est attendu quasi nul puisque l'identité est arithmétique, donc la
   règle du résidu dangereux s'applique — un petit résidu doit être DÉCOMPOSÉ (périmètre,
   millésime, comptabilisation du SFA) avant d'être fêté. Échec = une année hors bande sans
   cause mécanique nommée.
6. Puis seulement : noter §6.1, et M1 est clos.

---

## 5. Les deux pièges des fichiers INSEE, déjà payés

À ne pas redécouvrir, et à garder en tête pour tout nouveau fichier :

1. **`D41` apparaît DEUX FOIS** dans la table 7.301 — ressources et emplois. Les APU paient
   ET reçoivent des intérêts ; l'identité veut le NET. Lire la seule ligne d'emplois
   surestime de 8 % et l'erreur atterrit entière sur `r`. `apu_account` exige deux lignes et
   refuse s'il n'en trouve qu'une.
2. **Le stock de dette est en MILLIONS quand tout ce qui l'entoure est en milliards.**
   2019T4 se lit 2 387 398,96 = 2 387,4 md€. `check_units` divise le stock par le PIB et
   exige de retrouver le ratio PUBLIÉ : lue en milliards, la série échoue d'un facteur
   mille. **L'unité n'est jamais affirmée en commentaire** — c'est la classe de l'en-tête
   menteur, qui compte déjà quatre instances au dossier.

---

## 6. M2 — où ça en est

### Fait
- **Le moteur** (`agregats/engine.py`, 24 tests) : ancre depuis le manifeste, liste blanche
  de sorties, contrôle de ventilation, élasticité absente dite.
- **La DoD partie double** : `guards.sector_balance` prend désormais `aggregate_deltas`,
  testée contre un grand-livre cassé exprès, **et montrée indépendante du chiffre annoncé**
  (retirer le seul argument agrégé d'un scénario équilibré doit casser l'identité — sinon
  l'extension reconstruirait son côté depuis `reform_cost`, défaut exact de la première
  version de cette garde). Un instrument présent des deux côtés est refusé comme double
  compte. Rétrocompatibilité mesurée : les sept scénarios existants rejoués, comportement
  identique.

### Reste à faire — les instruments du §2.3.1
Aucun instrument n'est encore construit. Chacun a besoin d'une **ancre de recettes
manifestée** ; ce sont des téléchargements, et c'est le vrai coût de M2 :

| Instrument | Ce qu'il faut |
|---|---|
| TVA (20 / 10 / 5,5 / 2,1) | ventilation d'assiette par taux depuis la CN COICOP (ancre R5). **Sans R5 au niveau COICOP, le sous-bouton « restructuration d'assiette » est D** — la spec le dit. Bannière permanente : aucune distribution avant Budget de Famille (~2027-28). |
| Accise énergies (ex-TICPE) | taux/volume × volumes CCTN/DGEC + bande élasticité carburants (court vs long terme à énoncer). |
| Accise tabacs | volumes OFDT + bande d'élasticité-prix. **C'est le cas noté de §6.2.** |
| Accise alcools | volumes DGDDI/OFDT. |
| Accise électricité / gaz | historique de taux turbulent post-2022 (bouclier tarifaire) : discipline de millésime, ancrer sur la dernière année close. |
| TSN | mise à l'échelle de recettes seulement ; grade d'avertissement « base très mobile » sur toute bande. |
| TTF | idem ; littérature contestée sur la fuite d'assiette — bande large ou absente. |

Et §6.2 : l'épisode tabac 2018-2020 (trajectoire à 10 €/paquet), à noter comme le CICE.
**Préenregistrer** que le mécanique seul SURESTIME les recettes (la demande a baissé) — la
grandeur notée est la bande, pas le point.

---

## 7. Ordre de marche suggéré

1. **Si le SFA est arrivé** : finir §6.1 selon la marche à suivre du §4. C'est le chemin le
   plus court vers un jalon clos.
2. **Sinon, M2** : commencer par l'instrument dont l'ancre est déjà manifestée, s'il y en a
   un — vérifier avec `load_manifest()` plutôt que supposer. Sinon, produire au propriétaire
   une liste de téléchargements aussi précise que celle du SFA (quantité exacte, millésime,
   comment reconnaître le bon document, valeurs attendues pour vérification au coup d'œil).
   Cette précision est ce qui a fait aboutir la 7.301 en deux essais.
3. **Ne pas** ouvrir M3-M6 avant que M2 soit clos.

---

## 8. Ce qui est REFUSÉ et ne se rouvre pas sans décision du propriétaire

- **La CDHR reste refusée** (D-141). La clé ERFS a été essayée et n'ouvre pas : la CDHR vit
  tout entière dans le dernier centile, qu'une enquête auprès des ménages sous-compte par
  son PLAN DE SONDAGE. La serrure est renommée « source qui voit le sommet » (échantillon
  lourd DGFiP, POTE). `plf_coverage.py` le dit, et un test empêche de re-nommer l'ERFS.
- **La couche PFU s'ouvre par la route PUBLIÉE, pas par l'ERFS** (D-141) : 44,7 % de
  l'assiette capital de l'ERFS est IMPUTÉE par l'INSEE, et bâtir dessus dépenserait le seul
  comparateur indépendant qui reste.
- **E3 reste « rien »** : aucune recalibration sur l'ERFS.
- **Aucune sortie distributionnelle sur un instrument agrégé**, jamais.
- Les refus de la phase 4 tiennent : pas de prévision, pas de DSGE/CGE/HANK/ABM, pas de
  politique monétaire, pas d'horizon au-delà de trois ans côté comportement, jamais
  d'estimation ponctuelle là où une bande est due.

---

## 9. Divers, mais qui coûte du temps si on l'ignore

- `data/raw/` est gitignoré sauf liste blanche (`.gitkeep`, `MANIFEST.json`,
  `data/processed/baseline_*.json`). Les fichiers de données n'entrent JAMAIS dans git ;
  `scripts/check_no_data_committed.py` le vérifie et refuse (exit 1) sur un fichier
  STAGÉ — un fichier non suivi ne le déclenche pas, c'est normal, il garde ce qui est
  commité.
- Les fichiers non sourcés vivent dans `data/raw/_unsourced/` (D-028), **ils ne sont pas
  supprimés**. Une recherche qui conclut « 76 fichiers manquants » cherche au mauvais
  endroit.
- Les années sont stockées en TEXTE dans ces classeurs INSEE ; un repérage d'en-tête qui
  teste `isinstance(c, int)` ne trouve rien et lève un `StopIteration` opaque.
- `$?` après un pipe lit le statut du DERNIER maillon. Cette erreur a été commise trois
  fois cette session, dont deux fois pour « prouver » qu'une garde marchait.
- `x or DÉFAUT` n'est pas `x if x is None else DÉFAUT` : un tuple vide est falsy, et c'est
  exactement le cas que les gardes sont censées attraper.
