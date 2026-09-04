# Phantom parameter `impot_revenu.credits_impots.aide_a_domicile` — draft d'issue amont + décisions à prendre

## 1. BOTTOM LINE

**Oui, cela mérite d'être signalé, et dans `openfisca/openfisca-france` uniquement — une seule issue, en français.** Les trois faits qui portent le rapport sont mesurés de première main dans cette session : (a) aucun `.py` du paquet ne lit `aide_a_domicile` — `grep -rn "aide_a_domicile"` sur le paquet installé ne renvoie **qu'une** ligne, `parameters/impot_revenu/credits_impots/index.yaml:21`, la liste `order:` cosmétique du parent, et `gh api search/code q='aide_a_domicile repo:openfisca/openfisca-france extension:py'` renvoie `total_count = 0` ; (b) une réforme qui écrit dans ce nœud relit correctement la valeur écrite et ne déplace aucun crédit (`ci_saldom = 5000.0` avant comme après), alors que la même écriture sur le nœud jumeau vivant le fait passer à `9000.0` ; (c) le sous-arbre est toujours présent sur `master` amont au 2026-08-24 (`gh api .../contents/.../credits_impots/aide_a_domicile` → `index.yaml`, `plafond`, `taux.yaml`) et la version épinglée 176.0.8 **est** la dernière publiée (PyPI `info.version = 176.0.8`, 2026-08-24T14:05:16Z). Rien n'indique que le problème ait déjà été rapporté : `gh api search/issues q='aide_a_domicile'` sur **tout** GitHub renvoie `total_count = 2`, les deux étant des PR de rafraîchissement en masse de `last_value_still_valid_on` (#2428, #2294) qui *entretiennent* le nœud mort sans le signaler. Ne **pas** ouvrir d'issue dans `openfisca-core` : l'écriture est bien formée, le nœud existe réellement, et core ne peut pas savoir quels paramètres les formules d'un paquet-pays lisent sans les exécuter — il n'y a rien à y corriger sans interdire une opération légitime (les réformes ajoutent couramment des paramètres que seules leurs propres formules lisent). Le seul point discutable côté core est une *suggestion* d'outillage, à formuler au mieux dans la même issue france, pas comme un bug.

---

## 2. L'ISSUE (format du template amont `.github/ISSUE_TEMPLATE.md`, en français)

> **Titre proposé :**
> `Paramètre fantôme : credits_impots.aide_a_domicile duplique credits_impots.emploi_salarie_domicile et n'est lu par aucune formule — une réforme qui l'écrit est un no-op silencieux`

---

Hello hello !

Je suis le fan numéro un d'OpenFisca, mais je viens de rencontrer un problème.

### Qu'ai-je fait ?

J'ai écrit une réforme du crédit d'impôt pour l'emploi d'un salarié à domicile (art. 199 sexdecies du CGI). Pour trouver le paramètre à modifier, j'ai parcouru `impot_revenu.credits_impots` et j'y ai trouvé `aide_a_domicile` :

- il se résout, non nul, au 2024-01-01 ;
- sa `description` est « Crédit d'impôt pour l'aide à domicile » ;
- sa `documentation` cite explicitement « CGI - art 199. sexdecies » ;
- ses sept feuilles portent, au 2024-01-01, exactement les mêmes valeurs que celles du nœud voisin `emploi_salarie_domicile` (taux 0,5 ; plafond invalides 20 000 ; majoration 1 500 ; plafonds 15 000 / 12 000 ; plafonds max 18 000 / 15 000), à des noms et à une imbrication près ;
- les deux nœuds sont frères sous le même parent et figurent dans la même liste `order:` de `parameters/impot_revenu/credits_impots/index.yaml` (lignes 21 et 24).

J'ai donc écrit ma réforme sur `impot_revenu.credits_impots.aide_a_domicile`.

### À quoi m'attendais-je ?

Soit que la réforme modifie le crédit calculé, soit qu'OpenFisca m'avertisse que ce paramètre n'est lu par personne.

### Que s'est-il passé en réalité ?

La réforme s'applique sans erreur. La relecture du paramètre renvoie bien la valeur que je viens d'écrire (0,9). Et le crédit calculé ne bouge pas d'un centime.

`aide_a_domicile` n'est lu par **aucune formule** du paquet. C'est un sous-arbre mort qui se fait passer pour vivant, et la relecture ne peut pas le détecter, puisqu'il répond les mêmes valeurs que le nœud vivant.

- `grep -rn "aide_a_domicile"` sur le paquet installé (`openfisca_france/`) : **une seule** occurrence, `parameters/impot_revenu/credits_impots/index.yaml:21`, c'est-à-dire la liste `order:` du parent. Zéro occurrence dans un `.py`.
- Sur le dépôt : `gh api search/code -f q='aide_a_domicile repo:openfisca/openfisca-france extension:py'` → `total_count = 0`.
- Par contraste, `emploi_salarie_domicile` est lu dans `model/prelevements_obligatoires/impot_revenu/credits_impot.py` aux lignes **3035, 3056, 3085, 3118** (et le nœud homonyme sous `calcul_reductions_impots` dans `reductions_impot_plafonnees.py:4982, 4996, 5015, 5036, 5067`).

### Voici des informations qui peuvent aider à reproduire le problème

Versions : `openfisca-france 176.0.8`, `openfisca-core 44.7.0`, Python 3.12. Le script ci-dessous est autonome (aucune dépendance hors OpenFisca) et s'exécute tel quel en quelques secondes.

```python
"""openfisca-france 176.0.8 / openfisca-core 44.7.0 / Python 3.12."""
from openfisca_core.periods import instant
from openfisca_core.reforms import Reform
from openfisca_core.simulations import SimulationBuilder
from openfisca_france import FranceTaxBenefitSystem

MORT = 'impot_revenu.credits_impots.aide_a_domicile'
VIVANT = 'impot_revenu.credits_impots.emploi_salarie_domicile'
PERIODE = '2024'

CAS = {
    'individus': {'Michel': {'salaire_imposable': {PERIODE: 40000}}},
    'familles': {'f1': {'parents': ['Michel']}},
    'foyers_fiscaux': {'ff1': {'declarants': ['Michel'], 'f7db': {PERIODE: 10000}}},
    'menages': {'m1': {'personne_de_reference': ['Michel']}},
    }


def noeud(racine, chemin):
    n = racine
    for p in chemin.split('.'):
        n = n.children[p]
    return n


def ci_saldom(tbs):
    sim = SimulationBuilder().build_from_entities(tbs, CAS)
    return float(sim.calculate('ci_saldom', PERIODE)[0])


def reforme_taux(chemin_feuille, valeur):
    def modifie(parameters):
        noeud(parameters, chemin_feuille).update(start=instant('2017-01-01'), value=valeur)
        return parameters

    return type('R', (Reform,), {
        'apply': lambda self: self.modify_parameters(modifier_function=modifie)})


tbs = FranceTaxBenefitSystem()

# 1. Le noeud mort se resout, et il est documente comme l'art. 199 sexdecies.
p = tbs.get_parameters_at_instant('2024-01-01')
mort = p.impot_revenu.credits_impots.aide_a_domicile
print('1. aide_a_domicile @2024-01-01 vaut None ?', mort is None)
print('   description :', noeud(tbs.parameters, MORT).description)
print('   documentation cite 199 sexdecies ?',
      '199. sexdecies' in noeud(tbs.parameters, MORT).documentation)

# 2. Memes sept valeurs que le noeud vivant, renommees et re-imbriquees.
vivant = p.impot_revenu.credits_impots.emploi_salarie_domicile
paires = [
    ('taux', mort.taux, 'taux', vivant.taux),
    ('plafond.plafond_base.plafond_annee_supp', mort.plafond.plafond_base.plafond_annee_supp, 'plafond', vivant.plafond),
    ('plafond.plafond_base.plafond_annee_1', mort.plafond.plafond_base.plafond_annee_1, 'plafond_1ere_annee', vivant.plafond_1ere_annee),
    ('plafond.plafond_max.plaf_max_annee_supp', mort.plafond.plafond_max.plaf_max_annee_supp, 'plafond_maximum', vivant.plafond_maximum),
    ('plafond.plafond_max.plaf_max_annee_1', mort.plafond.plafond_max.plaf_max_annee_1, 'plafond_maximum_1ere_annee', vivant.plafond_maximum_1ere_annee),
    ('plafond.plafond_invalide', mort.plafond.plafond_invalide, 'plafond_invalides', vivant.plafond_invalides),
    ('plafond.plafond_additionnel', mort.plafond.plafond_additionnel, 'increment_plafond', vivant.increment_plafond),
    ]
print('\n2. Comparaison feuille a feuille au 2024-01-01 (appariees par role) :')
for nm, vm, nv, vv in paires:
    print(f'   {nm:<42}{vm:>8}  |  {nv:<28}{vv:>8}   egal={vm == vv}')

# 3. Ecrire dans le noeud mort ne change rien ; le noeud vivant, si.
base = ci_saldom(tbs)
print(f'\n3. ci_saldom de reference                                  = {base}')
for chemin in (MORT + '.taux', VIVANT + '.taux'):
    reforme = reforme_taux(chemin, 0.9)(tbs)
    relu = reforme.get_parameters_at_instant('2024-01-01')
    for part in chemin.split('.'):
        relu = getattr(relu, part)
    print(f'   reforme sur {chemin}')
    print(f'      relecture du taux ecrit = {relu}   ci_saldom = {ci_saldom(reforme)}')
```

Sortie littérale :

```
1. aide_a_domicile @2024-01-01 vaut None ? False
   description : Crédit d'impôt pour l'aide à domicile
   documentation cite 199 sexdecies ? True

2. Comparaison feuille a feuille au 2024-01-01 (appariees par role) :
   taux                                           0.5  |  taux                             0.5   egal=True
   plafond.plafond_base.plafond_annee_supp      12000  |  plafond                        12000   egal=True
   plafond.plafond_base.plafond_annee_1         15000  |  plafond_1ere_annee             15000   egal=True
   plafond.plafond_max.plaf_max_annee_supp      15000  |  plafond_maximum                15000   egal=True
   plafond.plafond_max.plaf_max_annee_1         18000  |  plafond_maximum_1ere_annee     18000   egal=True
   plafond.plafond_invalide                     20000  |  plafond_invalides              20000   egal=True
   plafond.plafond_additionnel                   1500  |  increment_plafond               1500   egal=True

3. ci_saldom de reference                                  = 5000.0
   reforme sur impot_revenu.credits_impots.aide_a_domicile.taux
      relecture du taux ecrit = 0.9   ci_saldom = 5000.0
   reforme sur impot_revenu.credits_impots.emploi_salarie_domicile.taux
      relecture du taux ecrit = 0.9   ci_saldom = 9000.0
```

**Le contraste tient en une ligne :** même réforme, même valeur écrite, même relecture réussie — `5000.0` d'un côté, `9000.0` de l'autre. C'est ce qui fait de ce doublon un piège et non une simple curiosité : rien, côté utilisateur, ne distingue le nœud mort du nœud vivant avant le résultat de la simulation.

**Précision temporelle importante (mesurée) :** l'identité des sept feuilles vaut à partir du 2017-01-01 (vérifiée au 2017-01-01, 2020-01-01, 2024-01-01, 2026-01-01 : 7/7). Avant 2017, `aide_a_domicile` n'a **aucune** valeur — un accès au 2015-01-01 lève `ParameterNotFoundError: The parameter 'impot_revenu.credits_impots.aide_a_domicile[taux]' was not found in the 2015-01-01 tax and benefit system` — alors que le nœud vivant, lui, est renseigné. Les valeurs de `aide_a_domicile` démarrent toutes au 2017-01-01, ce qui correspond au basculement réduction → crédit de la LF 2017.

### Comment il est arrivé là (historique, pour aider au diagnostic)

Reconstitué avec l'API commits de GitHub :

- `gh api "repos/openfisca/openfisca-france/commits?path=openfisca_france/parameters/impot_revenu/calcul_credits_impots/aide_a_domicile/taux.yaml"` → le plus ancien commit est **ec4033b5** (2022-11-16, « Ajoute et harmonise 'aide_a_domicile' »), puis **704444f2** (2022-12-02, lint), puis **f12db1c1** (2023-01-23, « Refactor credits impots - interets emprunt ») qui déplace le dossier sous `credits_impots/` — c'est à ce moment qu'il devient frère du futur nœud vivant.
- Le nœud vivant, lui, est **postérieur** : `gh api "…commits?path=…/credits_impots/emploi_salarie_domicile/taux.yaml"` ne renvoie que deux commits, le plus ancien étant **a72ac419** (2024-11-14, « Crée un nouveau dossier emploi_salarie_domicile dans les crédits d'impôts et éteind les paramètres du dossier réductions > emploi_salarie_domicile en 2017 »), et le plus récent **552d15a8** (2025-02-24, « last_value_still_valid_on »).

Autrement dit : `aide_a_domicile` est arrivé en premier (import des barèmes IPP — chaque feuille porte encore un `ipp_csv_id` de la famille `plafond_credit_aide_*` / `taux_aide_credit_impot`), sans jamais être branché à une formule ; le dossier réellement câblé a été créé deux ans plus tard, à côté, sans que l'ancien soit référencé ni retiré. Il continue d'être entretenu comme s'il était vivant : `aide_a_domicile/plafond/plafond_additionnel.yaml` porte `last_value_still_valid_on: "2025-02-24"`.

### Est-ce plus large qu'un cas isolé ?

Nous avons passé l'arbre complet au crible avec un script maison (analyse AST de tous les `.py` du paquet, résolution des chemins de paramètres contre l'arbre réel, avec suivi des liaisons de préfixe `P = parameters(period).a.b`, et marquage « opaque » de tout accès non traçable), puis validé le résultat par une sonde dynamique qui calcule toutes les variables sur quatre millésimes. Chiffres obtenus (au 2024-01-01, `openfisca-france` 176.0.8) :

- 4 645 chemins dans l'arbre chargé, 3 432 non nuls à cet instant ;
- **715 chemins non nuls lus par aucune formule**, dont 490 feuilles, regroupés en **131 racines** (129 entièrement mortes, 2 partielles qui sont des alias `cotsoc`) ;
- sonde dynamique : 12 266 calculs de variables réussis, 2 030 lectures d'exécution rattachables à un chemin statique, **zéro** d'entre elles dans l'ensemble mort ;
- répartition des racines mortes : `prelevements_sociaux` 53, `impot_revenu` 42, `taxation_capital` 19, `chomage` 10, autres 5.

Ces 715 sont une **borne basse** (tout accès non traçable est compté comme lisant tout son
sous-arbre), et ce chiffre inclut sûrement des paramètres délibérément conservés pour un
usage externe. Nous ne demandons rien à son sujet.

Ce qui nous paraît mériter votre attention, ce sont les nœuds morts qui portent **les mêmes
valeurs qu'un jumeau vivant**, parce que ce sont eux qui piègent. En voici six, chacun
vérifié à la main : valeurs relevées au 2024-01-01 des deux côtés, et zéro occurrence du
nom mort dans `model/`.

| Nœud mort (0 lecture) | Jumeau vivant | Valeurs au 2024-01-01 |
|---|---|---|
| `impot_revenu.credits_impots.aide_a_domicile` | `…credits_impots.emploi_salarie_domicile` | 7 feuilles sur 7 identiques |
| `…csg.remplacement.allocations_chomage.abattement` | `…csg.activite.abattement` | barème identique : taux [0,0175 ; 0], seuils [0 ; 4] |
| `…csg.activite.taux_global` | `…csg.activite.deductible` + `.imposable` | 0,092 = 0,068 + 0,024 |
| `…ifi_partir_2018.reduc_impot.plafond_somme_reduction_pme_fcip_fip_pme` | `…plafond_somme_trois_reductions_pme_fcip_fip_pme_dons` | 50 000 des deux côtés |
| `taxation_capital…csg.taux_deductible.produits_de_placement` | `…taux_deductible.revenus_du_patrimoine` | 0,068 des deux côtés |
| `…prelevement_forfaitaire.liberatoire_taux_fixe.produits_dans_etats_non_cooperatifs` | `…liberatoire_assurance_vie.bons_contrats_placements.produits_vers_etats_non_cooperatifs` | 0,75 des deux côtés |

Deux d'entre eux méritent un mot parce qu'ils ne sont pas de simples renommages.

**`csg.activite.taux_global` n'est pas un doublon, c'est un agrégat dérivé.** Il vaut
exactement la somme des deux composantes que les formules lisent réellement. Et c'est le
pire nom du lot : « le taux de CSG sur les revenus d'activité » est exactement ce qu'on
cherche. Une réforme qui l'écrit ne fait rien.

**`allocations_chomage.abattement` est au bon endroit dans l'arbre et c'est le voisin qui
est lu.** Les formules CSG/CRDS sur le chômage vont chercher `csg.activite.abattement`
« de côté » (`model/…/prelevements_sociaux/contributions_sociales/remplacement.py`), alors
qu'un nœud `abattement` existe sous la branche chômage, décrit pour cela, avec les mêmes
valeurs. Quiconque veut réformer l'abattement de CSG sur le chômage écrira dans le nœud
mort.

**Un mot sur la détection**, parce que nous nous y sommes cassé les dents avant vous : une
règle par recherche de nom ne suffit pas. `taux_global` apparaît bien dans `model/`, mais
sous `csg.remplacement.allocations_chomage.taux_global` et sous
`taxation_capital…csg.taux_global.produits_de_placement` — jamais sous `csg.activite`. Un
grep sur la feuille conclut « utilisé » et se trompe. Il faut résoudre le chemin complet
contre l'arbre réel, ou vérifier par l'exécution.

### Ce que nous proposons — plusieurs options, à vous de trancher

1. **Supprimer le sous-arbre `impot_revenu/credits_impots/aide_a_domicile`.** Le plus propre : il n'y a rien à préserver, la même législation est déjà décrite par `emploi_salarie_domicile`. Réserve : la suppression d'un chemin de paramètre est un changement cassant au sens de votre politique de version, et une réforme tierce qui écrit aujourd'hui dans ce chemin lèverait alors une erreur — ce qui est précisément le comportement souhaitable, mais qui doit passer par un bump majeur. Précédent : #2200 → #2204 (`reduction_loyer_solidarite/limite_plafond_ressources`) a suivi exactement cette voie.
2. **Le conserver mais le neutraliser** : ajouter dans sa `documentation` une ligne explicite (« paramètre non utilisé par les formules ; le dispositif est calculé à partir de `impot_revenu.credits_impots.emploi_salarie_domicile` ») et/ou clore ses valeurs. Non cassant, mais le piège reste ouvert pour qui lit l'arbre par le code plutôt que par les YAML.
3. **Un mécanisme d'alias**, pour que le nom naturel pointe vers le nœud vivant. À notre connaissance il n'en existe pas aujourd'hui (aucune occurrence de « alias » dans `openfisca_core/parameters/*.py` en 44.7.0) ; ce serait donc une évolution de core, à peser à part.
4. **Un garde-fou en CI** : un test qui échoue si un paramètre non nul n'est lu par aucune formule (ou, moins strict, qui gèle la liste actuelle et refuse les *nouvelles* entrées). C'est la seule option qui empêche la récidive ; nous avons le prototype si l'idée vous intéresse.

Nous n'avons pas d'attente sur laquelle vous retenez — le plus utile pour nous serait déjà que le cas soit tranché explicitement.

### Ce que nous n'affirmons PAS

- **Aucun résultat de simulation n'est faux à cause de ça.** Le nœud n'étant lu par personne, il n'affecte aucun calcul d'OpenFisca France. C'est un piège pour l'auteur de réformes, pas une erreur de législation.
- **Nous n'affirmons pas que les valeurs de `aide_a_domicile` sont incorrectes.** Elles semblent au contraire correctes — c'est bien ce qui rend le doublon crédible.
- **Nous n'affirmons pas qu'`openfisca-core` a un bug ici.** L'écriture est bien formée, le nœud existe, la relecture est juste ; core ne peut pas savoir sans exécution quels paramètres un paquet-pays lit. Rien à corriger de ce côté, sauf à ajouter un outillage (option 4).
- **Nous n'affirmons pas que les 715 chemins morts doivent tous disparaître.** Le chiffre est une borne basse produite par notre propre outil, non validée par vous, et certains de ces paramètres sont peut-être maintenus à dessein.
- **Nous n'affirmons pas que l'identité des valeurs vaut sur tout l'historique** : elle est vérifiée à partir du 2017-01-01 ; avant, le nœud fantôme n'a tout simplement pas de valeurs.

### Méthode

Par transparence : le balayage de l'arbre des paramètres et la vérification contradictoire
des affirmations ci-dessus ont été menés avec l'assistance d'un agent. Tout ce qui est
chiffré dans cette issue a ensuite été **remesuré à la main** avant publication — le script
de reproduction ci-dessus a été exécuté tel qu'il est écrit, et les six doublons du tableau
ont été relus un par un dans l'arbre chargé. Si quelque chose ne se reproduit pas chez
vous, dites-le : je préfère retirer une affirmation que la défendre.

### Contexte

Je m'identifie plus en tant que :

- [ ] Contributeur·e : je contribue à OpenFisca France.
- [x] Développeur·e : je crée des outils qui utilisent OpenFisca France.
- [ ] Économiste : je réalise des simulations avec des données.
- [ ] Mainteneur·e : j'intègre les contributions à OpenFisca France.
- [ ] Autre.

---

## 3. OPEN QUESTIONS FOR THE REPO OWNER

Décisions humaines requises avant toute publication. Rien n'a été posté.

1. **Publier ou non.** Le défaut est réel et reproductible, mais son impact est nul sur les résultats publiés : il ne mord que sur l'auteur de réformes. Est-ce que cela vaut le coût d'une issue amont et du fil qui suivra ?
2. **Quel compte GitHub poste.** L'issue est rédigée à la première personne du singulier (« je »), conforme au template. Elle doit être postée depuis un compte qui assume l'enquête. À décider aussi : signer ou non en mentionnant qu'une partie du travail est assistée par un agent.
3. **Une issue ou deux.** Recommandation : **une seule**, dans `openfisca-france`. Confirmer que vous ne voulez pas d'issue séparée dans `openfisca-core` pour l'option 4 (garde-fou / avertissement). Si vous en voulez une, elle doit être formulée comme *feature request*, jamais comme bug.
4. **Proposer ou non une PR.** Le correctif de l'option 1 est trivial (suppression de 11 fichiers + retrait de la ligne 21 de `credits_impots/index.yaml`), mais il touche leur politique de version. Offrir la PR d'emblée, ou attendre qu'un mainteneur choisisse l'option ?
5. **Joindre ou non le script de balayage.** Il produit le chiffre 715, qui n'a pas été audité par les mainteneurs. Les **six doublons** du tableau, eux, ont été vérifiés à la main un par un et ne dépendent pas du script — ils tiennent seuls. Option : garder le tableau, retirer le 715 et le script, et ne pas ouvrir le débat de méthode.

   *(Note : le premier jet de ce draft n'annonçait qu'UN doublon de valeurs. C'était faux — vérification directe : six, dont l'agrégat dérivé de la CSG et l'abattement chômage, qui sont les deux plus piégeux du lot. La section a été corrigée sur mesure.)*
6. **Nommer ou non le projet aval.** Le draft ne mentionne nulle part le simulateur privé du dépôt `Impots` ni D-064. Le nommer donne du contexte d'usage ; s'en abstenir garde l'issue purement technique. Statu quo actuel : **non nommé**.
7. **Point réellement incertain à assumer.** Nous ne savons pas si `aide_a_domicile` est conservé **volontairement** (par exemple parce que des utilisateurs IPP le lisent hors du paquet, ou parce qu'un chantier de rapprochement des barèmes IPP est en cours). Le CHANGELOG de la PR d'import de 2022 annonçait explicitement un travail ultérieur de rapprochement. Si un mainteneur répond « c'est voulu », l'issue doit se replier proprement sur l'option 2 (documenter) plutôt qu'insister sur la suppression — à décider avant de poster que c'est une position acceptable.
8. **Ton sur les PR #2428 / #2294.** Le draft signale que ces PR entretiennent le nœud mort à côté de son jumeau vivant. C'est un fait mesuré et c'est l'argument le plus fort que personne ne l'a remarqué, mais cela peut être lu comme un reproche adressé à des contributeurs nommés. Garder, atténuer, ou retirer ?

Fichiers écrits (scratchpad uniquement, dépôt et venv non modifiés) : `/private/tmp/claude-501/-Users-maximedenis-Dev-Impots/f8cc999f-08b2-47a9-8f09-17ad9122c0bc/scratchpad/issue_repro.py` (le script de l'issue, exécuté), `/private/tmp/claude-501/-Users-maximedenis-Dev-Impots/f8cc999f-08b2-47a9-8f09-17ad9122c0bc/scratchpad/dates.py` (comparaison des feuilles par date).
