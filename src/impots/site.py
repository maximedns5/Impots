"""Le site des études (but 7, D-304) : des pages HTML lisibles sans rien faire tourner.

    impots site construire     # site/, depuis les études de etudes/ et leurs rapports
    impots site verifier       # le site commité est-il celui des études ?

Une page d'accueil liste les études ; une page par étude dit ses trois réponses, chaque
nombre suivi de son étage de confiance, chaque réponse absente suivie de sa raison. Le
texte est celui de la page de l'étude (`Etude.lines`), ligne pour ligne : le site ne peut
pas dire ce que l'étude ne dit pas, et un nombre sans étage n'y entre pas. Aucun script :
du HTML et une feuille de style, servis tels quels.

LE SITE NE CALCULE RIEN. Il lit les études que `impots etude verifier` dit à jour et refuse
celle dont la page dérive de ses rapports. Une étude préenregistrée dont les passes n'ont
pas tourné est listée comme telle, sans page.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

from impots import etude

SITE = etude.ROOT / "site"
TITLE = "Impôts — les études"
#: The site's settings (D-357): where a reader reports an error. Empty until the owner
#: sets it; empty, the footer says so and `impots site publiable` refuses.
REGLAGES = etude.ROOT / "site_reglages.json"
METHODE = "methode.html"
TEXTES = Path(__file__).resolve().parent / "site_textes"
#: The terms the method page defines, each linked at its first use in a page (D-357):
#: (anchor on the method page, the pattern of its use). Longest first where they overlap.
TERMES: tuple[tuple[str, str], ...] = (
    ("vue", r"vues? vieillies?"), ("vue-figee", r"vues? figées?"),
    ("boite", r"boîte(?: θ| de θ)?"), ("theta", r"θ½|θ"),
    ("monte-carlo", r"Monte-Carlo"), ("verdict", r"verdicts?"),
    ("persistance", r"persistances?"), ("bande", r"bandes? comportementales?|bandes?"),
    ("mecanique", r"mécaniques?"), ("couverture", r"couverture"),
    ("mesange", r"Mésange"), ("point-de-pib", r"points? de PIB"),
    ("miroir", r"en miroir"), ("tolerance", r"tolérances?"),
    ("pont", r"ponts? de non-recours"), ("non-recours", r"non-recours"),
    ("grade", r"dans l(?:'|&#x27;)étendue des estimations"),
    ("en-esperance", r"(?:servie?s? )?en espérance"),
    ("bandeaux", r"bandeaux maladie et famille|bandeaux? (?:maladie|famille)|bandeaux?"),
    ("reduction-generale", r"réductions? générales?"),
    ("preenregistrement", r"préenregistr(?:ée?s?|ements?)"),
    ("grille", r"grilles? de vérification"), ("delta-b", r"Δb"),
    ("decomposition", r"décomposition|recettes induites"),
    # The noun only: « porte » is far more often the verb (« le programme porte… »).
    ("porte", r"portes?(?= de chaque refus| qui l'ouvrir)|(?<=avec leur )porte"
              r"|(?<=avec sa )porte"),
    ("les-juges", r"D-\d{3}"),
)


class SiteError(ValueError):
    """The site would say what the studies do not."""


def _slug(text: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def _inline(text: str) -> str:
    """A Markdown line's inline marks, on escaped text: bold, italics, code."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def _badge(nombre: etude.Nombre) -> str:
    """A number, then what it rests on, linked to the page's legend."""
    label = nombre.etage + (", sous hypothèses" if nombre.conditionnel else "")
    # A figure holds on one line; a quoted passage (a scenario, a citation) wraps.
    kind = "nombre" if len(nombre.texte) <= 32 else "cite"
    return (f'<span class="{kind}">{_inline(nombre.texte)}</span>'
            f'<a class="etage e-{_slug(nombre.etage)}" href="#etage-{_slug(nombre.etage)}" '
            f'title="{html.escape(etude.ETAGES[nombre.etage])}">{html.escape(label)}</a>')


def _text(line: str, n: etude.Nombres) -> str:
    return n.resolve(_inline(line), _badge)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip()[1:-1].split("|")]


def _kind(line: str) -> str:
    """What a Markdown line opens: a table, a list, a quote, or a paragraph."""
    for prefix, kind in (("|", "table"), ("* ", "list"), ("> ", "quote")):
        if line.startswith(prefix):
            return kind
    return "para"


def _plain(line: str) -> bool:
    """A line that belongs to a block: not blank, not a heading, not the comment."""
    return bool(line.strip()) and not line.startswith("<!--") and not re.match(
        r"#{1,3} ", line)


def body(lines: list[str], n: etude.Nombres) -> str:
    """The page's Markdown lines as HTML: headings, tables, lists, quotes, paragraphs.
    The generator's comment stays in the Markdown."""
    out: list[str] = []
    ids: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith("<!--"):
            i += 1
            continue
        heading = re.match(r"(#{1,3}) (.*)", line)
        if heading:
            level = len(heading[1])
            # A volet's sections repeat their titles: each anchor is the page's once.
            anchor = base = _slug(n.resolve(heading[2]))
            while anchor in ids:
                anchor = f"{base}-{sum(a.startswith(base) for a in ids) + 1}"
            ids.add(anchor)
            out.append(f'<h{level} id="{anchor}">{_text(heading[2], n)}</h{level}>')
            i += 1
            continue
        kind = _kind(line)
        block = []
        while i < len(lines) and _plain(lines[i]) and _kind(lines[i]) == kind:
            block.append(lines[i])
            i += 1
        if kind == "table":
            if len(block) < 2 or set(block[1].replace("|", "")) != {"-"}:
                raise SiteError(f"un tableau sans sa ligne d'en-tête : « {block[0][:60]} »")
            head = "".join(f"<th>{_text(c, n)}</th>" for c in _cells(block[0]))
            rows = "".join("<tr>" + "".join(f"<td>{_text(c, n)}</td>" for c in _cells(row))
                           + "</tr>" for row in block[2:])
            out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
        elif kind == "list":
            items = "".join(f"<li>{_text(item[2:], n)}</li>" for item in block)
            out.append(f"<ul>{items}</ul>")
        elif kind == "quote":
            out.append("<blockquote><p>" + " ".join(_text(q[2:], n) for q in block)
                       + "</p></blockquote>")
        else:
            text = " ".join(_text(p, n) for p in block)
            absent = any(p.startswith(("**Bande comportementale : aucune",
                                       "**Éventail macro : refusé")) for p in block)
            out.append(f'<p class="absent">{text}</p>' if absent else f"<p>{text}</p>")
    return "\n".join(out)


def _legend() -> str:
    # L0, the law as the engine codes it, carries no number of a study and so is not in
    # `etude.ETAGES`; the legend names it as the method page does. « vérifié » says there
    # is one population, 2024's, carried back to the other years (seconde relecture).
    meanings = {"L0": "la loi : chaque taux, seuil et barème, tel que l'outil le code ; "
                      "contrôlée en refaisant l'impôt de ménages types avec le simulateur de "
                      "la DGFiP", **etude.ETAGES}
    if "vérifié" in meanings:
        meanings["vérifié"] = ("l'écart d'un total du moteur à son total publié, sur 2022, "
                               "2023 et 2024, avec une seule population, celle de 2024, "
                               "ramenée aux deux autres années : la grille de vérification "
                               "(D-364)")
    rows = "".join(
        f'<dt id="etage-{_slug(key)}"><span class="etage e-{_slug(key)}">'
        f"{html.escape(key)}</span></dt><dd>{html.escape(meaning)}.</dd>"
        for key, meaning in meanings.items())
    return ('<section id="etages"><h2>Les étages de confiance</h2>'
            "<p>À côté de chaque nombre, ce sur quoi il repose. Un nombre que l'outil "
            "calcule dit son étage, de L0 à L4 ; un nombre qu'il reprend dit d'où il vient. "
            "Un écart de dette dit l'étage le plus haut qui y entre, et qu'il est "
            "<em>sous hypothèses</em> : celles du cadre nommé en bas de page, et θ.</p>"
            f"<dl>{rows}</dl></section>")


def reglages() -> dict:
    import json

    if not REGLAGES.exists():
        return {"signaler": None}
    return json.loads(REGLAGES.read_text(encoding="utf-8"))


def _signaler() -> str:
    """Where a reader reports an error, or that the address is not set yet (D-357)."""
    where = reglages().get("signaler")
    if not where:
        return ("L'adresse pour signaler une erreur n'est pas encore fixée : elle le sera "
                "avant la publication.")
    target = html.escape(where)
    href = target if where.startswith(("http://", "https://", "mailto:")) else (
        f"mailto:{target}")
    return (f'Une erreur, un nombre qui paraît faux, une phrase qui se lit mal : '
            f'<a href="{href}">{target}</a>. Chaque signalement reçoit une réponse, et '
            f"chaque correction est datée sur la page.")


def publiable() -> str | None:
    """Why the site may not be published yet, or None (D-357): a page put online that a
    reader cannot get corrected is not published."""
    if not reglages().get("signaler"):
        return (f"{etude._relative(REGLAGES)} ne dit pas où signaler une erreur (clé "
                f"« signaler ») : le site ne se publie pas sans elle (D-357).")
    return None


_SKIP = {"a", "h1", "h2", "h3", "code", "th", "td", "title", "dt", "span", "label",
         "option", "script", "style", "summary"}


def termes(main: str) -> str:
    """Link the first use of each term of the method page in a page's text (D-357): in
    prose only, never inside a link, a heading, a table, a number or code."""
    pieces = re.split(r"(<[^>]+>)", main)
    seen: set[str] = set()
    depth = 0
    for i, piece in enumerate(pieces):
        tag = re.match(r"<(/?)([a-zA-Z0-9]+)", piece)
        if tag:
            if tag[2].lower() in _SKIP and not piece.endswith("/>"):
                depth += -1 if tag[1] else 1
            continue
        if depth or not piece.strip():
            continue
        # The piece as segments, (text, may still take a link).
        segments = [(piece, True)]
        for anchor, pattern in TERMES:
            if anchor in seen:
                continue
            for k, (text, free) in enumerate(segments):
                match = re.search(rf"(?<![\w-])(?:{pattern})(?![\w-])", text) if free else None
                if match is None:
                    continue
                seen.add(anchor)
                link = f'<a class="terme" href="{METHODE}#{anchor}">{match[0]}</a>'
                segments[k:k + 1] = [(text[:match.start()], True), (link, False),
                                     (text[match.end():], True)]
                break
        pieces[i] = "".join(text for text, _ in segments)
    return "".join(pieces)


def _page(title: str, main: str, pied: str = "", liens: bool = True) -> str:
    main = termes(main) if liens else main
    return ("<!doctype html>\n"
            '<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)}</title>\n"
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>\n'
            f'<header><a href="index.html">{html.escape(TITLE)}</a> · '
            f'<a href="{METHODE}">Méthode et limites</a></header>\n'
            f"<main>\n{main}\n{_legend()}\n</main>\n"
            f"<footer>{pied}<p>Pages construites par <code>impots site construire</code> "
            "depuis les études et leurs seuls rapports commités ; rien n'y est calculé, rien "
            f"n'y tourne.</p><p>{_signaler()}</p></footer>\n</body>\n</html>\n")


STYLE = """\
:root { --fond: #fdfcf9; --texte: #1d1d1b; --doux: #5d5a55; --trait: #d9d5cc;
  --l1: #e7eef7; --l2: #dceedd; --l3: #f6ead2; --l4: #f3dfe0; --ext: #ebe7f3; }
@media (prefers-color-scheme: dark) {
  :root { --fond: #1b1a18; --texte: #ece9e2; --doux: #a8a397; --trait: #3c3a35;
    --l1: #24364a; --l2: #23402a; --l3: #4a3d20; --l4: #4b2a2d; --ext: #3a3350; } }
body { margin: 0; background: var(--fond); color: var(--texte);
  font: 17px/1.55 Georgia, "Times New Roman", serif; }
header, main, footer { max-width: 52rem; margin: 0 auto; padding: 0 1rem; }
header { padding-top: 1rem; font-family: system-ui, sans-serif; font-size: .9rem; }
a { color: inherit; text-decoration-color: var(--doux); }
header a { color: var(--doux); }
ul.etudes { list-style: none; padding: 0; }
footer { color: var(--doux); font-size: .85rem; padding: 2rem 1rem; }
h1, h2, h3 { font-family: system-ui, sans-serif; line-height: 1.25; }
table { border-collapse: collapse; margin: 1rem 0; font-size: .92rem; display: block;
  overflow-x: auto; }
th, td { border-bottom: 1px solid var(--trait); padding: .3rem .5rem; text-align: left;
  vertical-align: top; }
td code, th code { overflow-wrap: normal; white-space: nowrap; }
table { background: linear-gradient(to right, var(--fond) 30%, transparent),
  linear-gradient(to left, var(--fond) 30%, transparent) right,
  radial-gradient(farthest-side at 0 50%, rgba(0,0,0,.25), transparent),
  radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.25), transparent) right;
  background-repeat: no-repeat; background-size: 2rem 100%, 2rem 100%, .8rem 100%, .8rem 100%;
  background-attachment: local, local, scroll, scroll; }
blockquote { border-left: 3px solid var(--trait); margin: 1rem 0; padding: 0 1rem;
  color: var(--doux); }
p.absent { border-left: 3px solid var(--l3); padding-left: .8rem; }
.nombre { white-space: nowrap; }
.etage { font: 600 .76rem/1 system-ui, sans-serif; padding: .12rem .3rem;
  margin-left: .25rem; border-radius: .25rem; vertical-align: .12em; text-decoration: none;
  color: var(--texte); background: var(--ext); white-space: nowrap; }
.e-l1 { background: var(--l1); } .e-l2 { background: var(--l2); }
.e-l3 { background: var(--l3); } .e-l4 { background: var(--l4); }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .4rem 1rem; }
dd { margin: 0; }
code { font-size: .85em; overflow-wrap: anywhere; }
a.terme { text-decoration-style: dotted; }
main, p, li, dd { overflow-wrap: break-word; }
.cite { overflow-wrap: anywhere; }
@media (max-width: 560px) {
  body { font-size: 16px; }
  dl { grid-template-columns: 1fr; }
  header, main, footer { padding: 0 1rem; } }
"""


def _bref(lines: list[str]) -> list[str]:
    """The study's « En bref » section: its table and the sentence that reads it."""
    start = lines.index("## En bref")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return lines[start + 1:end]


def build(studies: list[etude.Etude] | None = None) -> dict[str, str]:
    """Every file of the site, by name: the index, the style, a page per run study."""
    studies = etude.definitions() if studies is None else studies
    files: dict[str, str] = {"style.css": STYLE, ".nojekyll": ""}
    methode = (TEXTES / "methode.html").read_text(encoding="utf-8").replace(
        "{signaler}", _signaler())
    files[METHODE] = _page(f"Méthode et limites — {TITLE}", methode, liens=False)
    listed: list[str] = []
    codes: set[str] = set()
    for study in studies:
        why = study.drift()
        if why:
            raise SiteError(f"« {study.nom} » : {why} Le site ne lit qu'une étude à jour.")
        if not study.page.exists():
            listed.append(f'<li><strong>{html.escape(study.titre)}</strong> — '
                          f"préenregistrée ({html.escape(study.preenregistrement)}), ses "
                          f"passes n'ont pas tourné.</li>")
            continue
        entries = study.load()
        lines, n = study.lines(entries)
        commits = [commit for commit, _ in entries[0]["commits"]]
        codes |= set(commits)
        shown = ", ".join(f"<code>{c[:7]}</code>" for c in commits)
        code = (f"sur le commit {shown}" if len(commits) == 1 else
                f"sur les commits {shown}, joints par une passe témoin")
        pied = (f"<p>Étude chiffrée le {html.escape(entries[0]['first']['computed'])}, "
                f"{code}.</p>")
        files[f"{study.nom}.html"] = _page(f"{study.titre} — {TITLE}", body(lines, n), pied)
        listed.append(f'<li><h2><a href="{study.nom}.html">{html.escape(study.titre)}</a>'
                      f"</h2>\n<p>Chiffrée le {html.escape(entries[0]['first']['computed'])}, "
                      f"{code}.</p>\n{body(_bref(lines), n)}</li>")
    intro = ("<h1>Les études</h1>\n<p>Avant de lire un nombre : <a href=\"methode.html\">"
             "la méthode et les limites</a>, ce que veut dire chaque mot des pages et ce que "
             "l'outil ne fait pas.</p>\n<p>Chaque étude prend une réforme, ou les articles d'un "
             "texte, et donne trois réponses : ce qu'elle coûte et qui y gagne ; ce qu'elle "
             "coûte une fois les comportements et l'économie pris en compte ; ce qu'elle "
             "fait à la dette dans dix ans. À côté de chaque nombre, son étage de confiance ; "
             "une réponse absente est dite absente, avec sa raison.</p>")
    if any(study.programme for study in studies):
        # The review of goal 20: the index sets the candidates side by side, and the
        # parcours says what of them does not compare (D-378).
        intro += ("\n<p><strong>Les candidats ne se comparent pas ligne à ligne.</strong> "
                  "Chaque étude ne chiffre qu'une part du programme, dite à côté de chaque "
                  "nombre ; la dette et le verdict dépendent de ce que la boucle macro sait "
                  "lire, qui n'est pas le même d'un candidat à l'autre. Ce qui se compare, "
                  "et comment : <a href=\"parcours-comparer.html\">comparer deux "
                  "candidats</a>.</p>")
    if len(codes) > 1:
        # The studies ran on different code (D-336): a reader is told before comparing.
        intro += (f"\n<p><strong>Les études n'ont pas été chiffrées sur le même code</strong>"
                  f" : {len(codes)} commits, chacun dit sous son étude. Le moteur a changé "
                  f"entre elles : celles du PLF 2027 et du PLFSS 2027 ont tourné avant que "
                  f"la population ne porte les indemnités journalières (D-305 à D-314) et "
                  f"avant les corrections de D-310, celles des programmes après. Le coût "
                  f"d'une page ne se compare donc pas à celui d'une autre.</p>")
    if any(study.programme for study in studies):
        # The 24 declared candidates, each with its coverage and its doors (D-328).
        lines, n = etude.presidentielle(studies)
        files["presidentielle.html"] = _page(f"Les programmes de la présidentielle 2027 — "
                                             f"{TITLE}", body(lines, n))
        intro += ('\n<p><a href="presidentielle.html">Les programmes de la présidentielle '
                  "2027</a> : les 24 candidats déclarés, ce que l'outil chiffre de chacun, et "
                  "pourquoi pas le reste.</p>")
    explorer = _explorer() if EXPLORATEUR_PUBLIE and grille_present() else None
    if explorer is not None:
        files[EXPLORER] = explorer
        intro += ('\n<p><a href="explorer.html">Explorer les études</a> : les boutons des dix '
                  "études sur une grille précalculée, la dette rejouée dans le navigateur, "
                  "chaque nombre dit calculé, interpolé ou tiré d'une étude (but 15, D-344)."
                  "</p>")
    from impots import parcours

    scripted = {EXPLORER}
    if parcours.present():
        pages = parcours.build()
        files.update(pages)
        scripted |= set(pages)
        intro += (f'\n<p><a href="{parcours.PAGES[0][1]}">Refaire le chemin d\'un nombre</a> : '
                  "huit pages, du ménage au verdict, chacune avec sa donnée, le lien de sa "
                  "source et le fichier qui la calcule.</p>")
    files["index.html"] = _page(TITLE, intro + "\n<ul class=\"etudes\">\n"
                                + "\n".join(listed) + "\n</ul>")
    for name, text in files.items():
        # The explorer runs a script by decision (D-343), and the parcours pages that give
        # a cursor (D-375); no other page does.
        if name not in scripted and "<script" in text.lower():
            raise SiteError(f"{name} porte un script : le site se lit sans en exécuter.")
    return files


EXPLORER = "explorer.html"
#: The explorer is withdrawn from the site (D-377): its grid ran on the code of goal 16
#: (3c19f52), before the population of goal 19, and it would show the costs of then
#: (59,91 Md€ at Attal's knob for 66,40 in the series). It comes back with a grid rerun,
#: preregistered. The page's code and its checks stay.
EXPLORATEUR_PUBLIE = False
EXPLORER_JS = Path(__file__).resolve().parent / "site_explorer"


def grille_present() -> bool:
    from impots import grille

    return (grille.RAPPORTS / "paires").exists()


def _explorer(compiled: dict | None = None) -> str:
    """La page « explorer » : ses curseurs, ses témoins, ses crans en HTML, la grille compilée
    et les deux scripts en ligne. La seule page du site qui exécute quelque chose (D-343)."""
    import json

    from impots import grille

    g = compiled if compiled is not None else grille.compiler()
    esc = html.escape
    rows = []
    for c in g["curseurs"]:
        rows.append(
            f'<div class="curseur"><label for="r-{c["id"]}">{esc(c["titre"])}</label>'
            f'<input type="range" id="r-{c["id"]}" min="0" max="1" step="0.001">'
            f'<output id="v-{c["id"]}"></output><small id="p-{c["id"]}"></small></div>')
    options = "".join(f'<option value="{i}">{esc(cr["titre"])}</option>'
                      for i, cr in enumerate(g["crans"]))
    temoins = []
    for c in g["curseurs"]:
        t = c["temoin"]
        dette = ("absente" if t["ecart_dette"] is None else
                 f"{t['ecart_dette'] * 100:+.4f} pt / ± {t['tolerance_dette'] * 100:.4f} — "
                 f"{'tenue' if t['dette_tenue'] else 'manquée'}")
        temoins.append(f"<tr><td>{esc(c['titre'])}</td><td>{t['x']:.6g}</td>"
                       f"<td>{t['ecart_cout'] / 1e6:+.1f} M€ / ± {t['tolerance_cout'] / 1e6:.1f}"
                       f" — {'tenu' if t['cout_tenu'] else 'manqué'}</td><td>{dette}</td></tr>")
    data = json.dumps(g, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    scripts = "".join(f"<script>\n{(EXPLORER_JS / name).read_text(encoding='utf-8')}</script>\n"
                      for name in ("rejeu.js", "explorer.js"))
    commits = ", ".join(f"<code>{c[:7]}</code>" for c in g["commits"])
    main = (
        "<h1>Explorer les études</h1>\n"
        "<p>Chaque curseur fait varier un bouton seul, la loi intacte autour, sur une grille "
        "de points chiffrés d'avance : la première année (2026, population vieillie à elle), "
        "reportée en part de PIB constante, dans le cadre des études (croissance réelle 1 %, "
        "prix 2 %, dépense gelée en volume, taux implicite tenu, persistance lue). La dette, "
        "la boucle macro et la boîte de θ sont rejouées ici, par la même arithmétique que "
        "le moteur. Entre deux points, le nombre est interpolé, et l'écart mesuré au point "
        "témoin est dit à côté. Plusieurs curseurs s'additionnent, sauf sur les paires dont "
        f"le terme croisé est mesuré. Grille préenregistrée ({esc(g['preenregistrement'])}), "
        f"chiffrée sur {commits}.</p>\n"
        '<p><label for="cran">Partir d\'une mesure des études :</label> '
        f'<select id="cran"><option value="">la loi</option>{options}</select></p>\n'
        '<section class="curseurs">' + "".join(rows) + "</section>\n"
        '<p class="theta"><label for="theta">θ des comportements</label> '
        '<input type="range" id="theta" min="0" max="1" step="0.01" value="0.5"> '
        '<output id="theta-v">0.50</output> ; <label for="theta-macro">θ du multiplicateur'
        '</label> <input type="range" id="theta-macro" min="0" max="1" step="0.01" '
        'value="0.5"> <output id="theta-macro-v">0.50</output></p>\n'
        '<section id="resultat"><noscript>Cette page rejoue la dette dans le navigateur : '
        "sans script, les études restent lisibles sur leurs pages.</noscript></section>\n"
        "<h2>Les points témoins</h2>\n<p>Pour chaque curseur, un point hors de la grille, "
        "chiffré à part : l'écart entre l'interpolation et le calcul, contre la tolérance "
        "préenregistrée.</p>\n<table><thead><tr><th>curseur</th><th>témoin</th><th>coût</th>"
        "<th>dette en 2035, θ½</th></tr></thead><tbody>" + "".join(temoins)
        + "</tbody></table>\n"
        f'<script type="application/json" id="grille">{data}</script>\n' + scripts)
    return (_page(f"Explorer les études — {TITLE}", main)
            .replace("</head>", f"<style>{EXPLORER_STYLE}</style>\n</head>", 1)
            .replace("rien n'y est calculé, rien n'y tourne.",
                     "rien n'y est calculé, sauf sur cette page, qui rejoue la dette."))


EXPLORER_STYLE = """
.curseurs{display:grid;gap:.6rem;margin:1rem 0}
.curseur{display:grid;grid-template-columns:minmax(0,1fr) minmax(8rem,14rem) 7rem;gap:.2rem .8rem;align-items:center}
.curseur small{grid-column:1/-1;color:#5a6573}
.curseur input{width:100%}
.cout strong,.dette strong{font-variant-numeric:tabular-nums}
.deciles{list-style:none;padding:0;margin:0;display:grid;gap:.2rem}
.deciles li{display:grid;grid-template-columns:2.5rem minmax(0,1fr) 5rem;gap:.5rem;align-items:center}
.barre{height:.8rem;display:block}.plus{background:#2c7a4b}.moins{background:#a23b3b}
.num{text-align:right;font-variant-numeric:tabular-nums}
.cran{border-left:3px solid #1f4e8c;padding-left:.6rem}
select{max-width:100%}
.absent,.note{color:#5a6573}
@media (max-width:560px){.curseur{grid-template-columns:1fr}}
"""


def write(site: Path | None = None) -> list[Path]:
    site = site or SITE
    files = build()
    site.mkdir(parents=True, exist_ok=True)
    for stale in set(p.name for p in site.iterdir() if p.is_file()) - set(files):
        (site / stale).unlink()
    written = []
    for name, text in files.items():
        (site / name).write_text(text, encoding="utf-8")
        written.append(site / name)
    return written


def drift(site: Path | None = None) -> str | None:
    """Why the committed site is not the studies' build, or None."""
    site = site or SITE
    files = build()
    there = {p.name for p in site.iterdir() if p.is_file()} if site.exists() else set()
    if there != set(files):
        return (f"{etude._relative(site)} porte {sorted(there - set(files))} en trop et "
                f"manque {sorted(set(files) - there)} : `impots site construire`.")
    for name, text in sorted(files.items()):
        where = etude.difference((site / name).read_text(encoding="utf-8"), text)
        if where is not None:
            return f"{etude._relative(site / name)}, {where}."
    return None


def main_args(action: str) -> int:
    """`impots site construire|verifier|publiable`."""
    import sys

    if action == "publiable":
        why = publiable()
        if why:
            print(why, file=sys.stderr)
            return 1
        print("le site peut se publier : il dit où signaler une erreur.")
        return 0
    try:
        if action == "construire":
            for path in write():
                print(f"-> {etude._relative(path)}")
            return 0
        why = drift()
    except (SiteError, etude.EtudeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if why:
        print(why, file=sys.stderr)
        return 1
    print(f"{etude._relative(SITE)} : le site est celui des études.")
    return 0
