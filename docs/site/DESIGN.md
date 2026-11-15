# Le système visuel du site (but 25, D-450)

Le site se lit comme un média de données : sobre, peu de texte, des schémas, des nombres
qui s'ouvrent sur leur source. Tout ce qui suit vit dans deux fichiers, que chaque volet
reprend plutôt que d'écrire son propre habillage :

* `src/impots/site_textes/style.css` — la feuille commune (publiée en `site/style.css`) ;
* `src/impots/site_composants.py` — les composants, de petites fonctions qui rendent du
  HTML ; aucune ne demande de script.

Le gabarit commun est `site._page(titre, main, pied="", liens=True, large=False)` : l'en-tête
et sa navigation, le contenu, la légende des étages (repliée), le pied. `large=True` ouvre
la page à 72rem pour les schémas ; le texte courant reste à 42rem.

## Les jetons

Couleurs, définies sur `:root`, redéfinies en sombre (`prefers-color-scheme`, et
`:root[data-theme="dark"]`, `[data-theme="light"]` pour forcer) :

| jeton | rôle |
|---|---|
| `--papier`, `--surface`, `--surface-2` | fond de page, fond des cartes, fond doux |
| `--encre`, `--encre-2`, `--encre-3` | texte, texte secondaire, légendes |
| `--trait`, `--trait-fort` | filets et bordures |
| `--accent` (bleu encre), `--accent-doux` | liens, chiffres sourcés, focus |
| `--ocre`, `--vert`, `--rouge`, `--violet` (et `-doux`) | mises en garde, gain, perte, verdict |
| `--serie-1` à `--serie-4`, `--gain`, `--perte` | les séries d'un graphique, dans cet ordre |
| `--famille-donnees`, `-calcul`, `-economie`, `-verdict` | la couleur d'une étape du chemin |

Les anciens noms (`--fond`, `--texte`, `--doux`, `--l1` à `--l4`, `--ext`) restent des
alias : une page d'avant se lit encore.

Typographie : titres en serif (`--serif` : Charter, Iowan, Cambria, Georgia), texte et
interface en sans (`--sans` : la police du système), code en `--mono`. Les nombres sont en
chiffres tabulaires. Aucune police téléchargée : le site marche sans réseau tiers.

Espacements : `--e1` (0,25rem) à `--e8` (4,5rem). Rayons : `--rayon` (10px),
`--rayon-petit` (6px). Une ombre : `--ombre`.

## Les composants

| fonction | rendu | quand |
|---|---|---|
| `carte(titre, texte, href, surtitre, pied)` dans `cartes(...)` | `article.carte` en grille | une entrée vers une page, un choix |
| `etape(n, titre, texte, href, famille, source, ici)` dans `etapes(...)` | `ol.etapes > li.etape` | un parcours numéroté |
| `flux(entre, fait, sort, legende)` | `figure.flux` : trois colonnes et deux flèches, une pile au téléphone | le schéma d'une étape : ce qui entre, ce qui est fait, ce qui sort |
| `chiffre(valeur, Provenance(...), cle)` | `button.chiffre-v` qui ouvre un `popover` | **tout nombre affiché hors d'une page d'étude** |
| `stat(valeur, legende, provenance)` dans `chiffres(...)` | `div.stat` : un grand nombre et sa légende | les deux ou trois nombres d'une page |
| `curseur(id, libelle, mini, maxi, pas, valeur, change, ne_change_pas, plage, …)` | `div.curseur-bloc` : la piste, la plage publiée dessinée dessous, ce qu'il change et ce qu'il ne change pas | tout curseur ; le script écrit dans `output#{id}-v` |
| `note_source(html)` | `p.note-source` | sous un tableau, un schéma, un graphique |
| `garde(titre, html)` | `aside.garde` | ce qu'un lecteur pourrait conclure à tort |
| `detail(titre, corps, ouvert, note)` | `details.detail` | le détail qui se lit si on veut, pas avant |

`Provenance(quoi, rapport, champ, commit, source=(texte, url), calcul, etage, autres)` :
ce que mesure le nombre, le rapport commité et le champ qui le portent, le commit qui l'a
calculé, la source publique, comment il est tiré du rapport s'il n'y est pas tel quel. Le
popover s'ouvre au clic et au clavier, se ferme par Échap ; sans prise en charge, la
provenance s'affiche en ligne. Un même nombre deux fois sur une page prend une `cle`.

Un lien vers une page d'un autre volet qui n'existe peut-être pas encore :
`<span class="si-page" data-page="x.html">…</span>` ; `site.build` le retire tant que la
page n'est pas construite. La navigation (`site.NAV`) fait de même : une entrée n'est
montrée que si sa page est construite. Les volets `population` et `mesure` y sont déjà
(`population.html`, `mesure.html`) ; un autre nom se change là.

## Les règles

* Peu de texte en tête : un titre qui est une question, un chapeau de deux phrases, puis
  le schéma et les nombres. Le reste se replie (`detail`).
* Chaque nombre dit sa source : un badge d'étage sur une page d'étude, `chiffre` ailleurs.
* Chaque curseur dit sa portée : ce qu'il change, ce qu'il ne change pas, et la plage
  publiée.
* Accessible : contraste AA dans les deux thèmes, focus visible, cibles de 44px au
  téléphone pour les boutons, `aria-current` sur la page et l'étape.
* Au téléphone (390px) : pas de défilement horizontal de la page ; un tableau large défile
  dans son cadre.
