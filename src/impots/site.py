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
    rows = "".join(
        f'<dt id="etage-{_slug(key)}"><span class="etage e-{_slug(key)}">'
        f"{html.escape(key)}</span></dt><dd>{html.escape(meaning)}.</dd>"
        for key, meaning in etude.ETAGES.items())
    return ('<section id="etages"><h2>Les étages de confiance</h2>'
            "<p>À côté de chaque nombre, ce sur quoi il repose. Un nombre que l'outil "
            "calcule dit son étage, de L1 à L4 ; un nombre qu'il reprend dit d'où il vient. "
            "Un écart de dette dit l'étage le plus haut qui y entre, et qu'il est "
            "<em>sous hypothèses</em> : celles du cadre nommé en bas de page, et θ.</p>"
            f"<dl>{rows}</dl></section>")


def _page(title: str, main: str) -> str:
    return ("<!doctype html>\n"
            '<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)}</title>\n"
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>\n'
            f'<header><a href="index.html">{html.escape(TITLE)}</a></header>\n'
            f"<main>\n{main}\n{_legend()}\n</main>\n"
            "<footer>Pages construites par <code>impots site construire</code> depuis les "
            "études et leurs seuls rapports commités ; rien n'y est calculé, rien n'y "
            "tourne.</footer>\n</body>\n</html>\n")


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
blockquote { border-left: 3px solid var(--trait); margin: 1rem 0; padding: 0 1rem;
  color: var(--doux); }
p.absent { border-left: 3px solid var(--l3); padding-left: .8rem; }
.nombre { white-space: nowrap; }
.etage { font: 600 .68rem/1 system-ui, sans-serif; padding: .12rem .3rem;
  margin-left: .25rem; border-radius: .25rem; vertical-align: .12em; text-decoration: none;
  color: var(--texte); background: var(--ext); white-space: nowrap; }
.e-l1 { background: var(--l1); } .e-l2 { background: var(--l2); }
.e-l3 { background: var(--l3); } .e-l4 { background: var(--l4); }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .4rem 1rem; }
dd { margin: 0; }
code { font-size: .85em; overflow-wrap: anywhere; }
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
        files[f"{study.nom}.html"] = _page(f"{study.titre} — {TITLE}", body(lines, n))
        commits = [commit for commit, _ in entries[0]["commits"]]
        codes |= set(commits)
        shown = ", ".join(f"<code>{c[:7]}</code>" for c in commits)
        code = (f"sur le commit {shown}" if len(commits) == 1 else
                f"sur les commits {shown}, joints par une passe témoin")
        listed.append(f'<li><h2><a href="{study.nom}.html">{html.escape(study.titre)}</a>'
                      f"</h2>\n<p>Chiffrée le {html.escape(entries[0]['first']['computed'])}, "
                      f"{code}.</p>\n{body(_bref(lines), n)}</li>")
    intro = ("<h1>Les études</h1>\n<p>Chaque étude prend une réforme, ou les articles d'un "
             "texte, et donne trois réponses : ce qu'elle coûte et qui y gagne ; ce qu'elle "
             "coûte une fois les comportements et l'économie pris en compte ; ce qu'elle "
             "fait à la dette dans dix ans. À côté de chaque nombre, son étage de confiance ; "
             "une réponse absente est dite absente, avec sa raison.</p>")
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
    files["index.html"] = _page(TITLE, intro + "\n<ul class=\"etudes\">\n"
                                + "\n".join(listed) + "\n</ul>")
    for name, text in files.items():
        if "<script" in text.lower():
            raise SiteError(f"{name} porte un script : le site se lit sans en exécuter.")
    return files


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
    """`impots site construire|verifier`."""
    import sys

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
