# Handoff prompt — F1 preparation (the two pieces before the PLF drops)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are preparing **F1 — PLF 2027 live pricing** for the Impôts project.
Phase 5 and F2 are closed (`12d027e`, `32c4de1`; the gate is green on the
fixed instrument — 1042 passed, pytest's own exit status). The word is given
for the two preparation pieces named at the end of the last report. The PLF
publishes in early October; both pieces exist so that publication week is
execution, not design.

## 1. The coverage triage — decided in advance, committed as a document

`docs/PLF2027_COVERAGE.md`: every plausible fiscal-article category (build
the category list from the PLF 2026's actual article structure, plus the
September press on the 2027 orientations — lettre-plafonds coverage,
announced measures), each mapped to exactly one of:

* **priceable now** — with the knob(s) named, and which layers apply
  (mechanical only / + band / + fan) and which banners will fire
  (narrow-band, zero-base niches, population-level caveats);
* **priceable with a small knob** — the parameter path pre-identified and
  phantom-checked *now*, so publication week only wires it;
* **not priceable, with the reason** — data, structure, or scope.

The refusal list is the point as much as the coverage list: deciding in
advance what the tool cannot price makes "we couldn't price X" a
pre-registered limitation instead of a post-hoc excuse. Close the triage
with the honest headline it implies: the expected share of PLF fiscal
articles the tool can price.

## 2. The grading harness — measurement infrastructure, treated as such

One YAML case per pre-registered chiffrage: the reform JSON (or scenario
ref), population vintage, engine pin, timestamp, the full honesty stack
(mechanical, band + grade, applicable intervals, fan if any), and —
**declared at pre-registration time, never after** — the tolerance the
grade will use. When the évaluation préalable appears, its figure enters
with the full comparator discipline (source, vintage, perimeter, gross/net
of what). Grades: within/outside + direction, report auto-generated, prose
computing its own numbers from the run per the established mechanism.

Because this harness is measurement infrastructure, it gets the full
treatment at birth: the three questions, and a kill test proving it grades
red — a stub case with a known miss must fail before any real case enters.

Pre-registration integrity, internal-grade for now: the commit hash and
dated log line are the record. Note for the owner, no action required: if
external credibility ever matters, an outside-the-repo timestamp
(a public commit, a published hash) would be needed at pre-registration
time — record the option in the D-entry, decide nothing.

## 3. Boundaries

Draft the triage against PLF 2026's structure now; finalise category
assignments the day the 2027 text publishes — do not guess article numbers
before then. Nothing publishes, as ever. Standing rules all bind, the third
question included. ERFS interrupts everything — and its queue is now past
the typical window: the owner checking the Progedo account is worth one
line in your report back.
