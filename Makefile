# Impôts — the two test invocations, and the one that has to leave a trace.
#
# TWO BUGS LIVED IN `full` UNTIL 2026-09-08, and the second one mattered.
#
#   * `sed -E 's/.*?(...)'` — BSD sed's ERE has no lazy `.*?`, so it errored out on every
#     run and the log's `tests` column was silently empty. Cosmetic.
#   * `out=$$(... | tail -1); status=$$?` captured the exit status of `tail`, which always
#     succeeds. So `result` was ALWAYS PASS and `exit $$status` always 0. The file this
#     comment calls "the only record that the full suite is green" was structurally
#     incapable of recording anything else, and it swallowed pytest's summary line on the
#     way — a failing full run printed nothing and logged PASS.
#
# pytest now writes to a file, its status is read directly, and a failure prints its last
# forty lines. Verified both ways by forcing a failure (D-094).
#
# `make gate` is what you run while working: everything except the tests that need a
# full population pass, about 1 min 45. `make full` is the whole suite, and it appends
# a line to reports/full_pass_log.md — because CI cannot run those tests (it has no
# population, by design), so the full pass runs only on a machine with the data and its
# greenness is otherwise invisible and decays silently.
#
# The rule that goes with it: no review handoff goes out without a full-pass line newer
# than the work it reports.
#
# `make data` is the bootstrap: it downloads every raw source the suite reads BY ITS
# MANIFEST ENTRY (URL, size, sha256 — a byte off and nothing is written), builds the two
# derived artefacts (the population, the firm cell table), then runs the preflight.
# `make full` runs that PREFLIGHT FIRST and stops in about a second if a dependency is
# missing — it used to find out one file at a time, 47 minutes in, on whichever file each
# failing test happened to open first. A full pass that cannot be green is not started,
# and so is not logged: the log records passes, not aborted attempts.

VENV ?= .venv/bin
LOG  := reports/full_pass_log.md
DURATIONS := reports/full_pass_durations.md

.PHONY: gate full impact lint report data data-check ci-local ci-deps

gate:
	$(VENV)/ruff check src tests scripts
	$(VENV)/python -m pytest -q

lint:
	$(VENV)/ruff check src tests scripts

data:
	$(VENV)/impots data prepare --profile tests

data-check:
	@$(VENV)/impots data check --profile tests

# LA VÉRIFICATION QUE `make full` NE PEUT PAS FAIRE. Elle tourne dans l'environnement du
# propriétaire, donc elle ne voit pas ce que cet environnement porte par accident : `pypdf`
# a survécu à quinze passes vertes tout en étant cassé sur chaque runner (D-161). Ces deux
# cibles rejouent la CI dans un arbre et un venv NEUFS, sans une minute d'Actions.
ci-deps:
	$(VENV)/python scripts/ci_local.py --deps

ci-local:
	$(VENV)/python scripts/ci_local.py

full: data-check
	@mkdir -p reports
	@test -f $(LOG) || printf '# Full-pass log\n\nOne line per `make full`. CI cannot run the population tests — it has no\npopulation, by design — so this file is the only record that the full suite is\ngreen. No review handoff goes out without a line newer than the work it reports.\n\n| date | commit | result | duration | tests |\n|---|---|---|---|---|\n' > $(LOG)
	@$(VENV)/ruff check src tests scripts
	@start=$$(date +%s); \
	 out=$$(mktemp); \
	 $(VENV)/python -m pytest -q -m "" --durations=15 > $$out 2>&1; \
	 status=$$?; \
	 elapsed=$$(( $$(date +%s) - start )); \
	 summary=$$(grep -E '[0-9]+ (passed|failed|error)' $$out | tail -1); \
	 counts=$$(printf '%s' "$$summary" | sed -E 's/ in [0-9].*$$//'); \
	 : "pytest IMPRIME sa propre durée et le grep ci-dessus la jetait. elapsed est un"; \
	 : "écart de date +%s, donc de l'horloge murale : il compte le temps où la machine"; \
	 : "DORT. Une passe de 58m16s a été journalisée « 359m55s ». D-123."; \
	 worked=$$(printf '%s' "$$summary" | sed -nE 's/.* in ([0-9]+)\.[0-9]+s.*/\1/p'); \
	 : "un run TUÉ (SIGINT 130, SIGTERM 143) n'est PAS un échec de la suite, et"; \
	 : "les deux se lisaient FAIL avec des points de progression en guise de"; \
	 : "comptes — indiscernables dans le journal. D-113."; \
	 if [ $$status -eq 0 ]; then result=PASS; \
	 elif [ $$status -ge 128 ] || [ $$status -eq 2 ]; then result=TUÉ; \
	   counts="$${counts:-interrompu, aucun résumé produit}"; \
	 else result=FAIL; fi; \
	 [ "$$result" = FAIL ] && tail -40 $$out; \
	 : "--durations écrit son bloc dans \$$out, que seul tail -1 lisait avant"; \
	 : "de le supprimer : le drapeau était INERTE en cas de succès. D-117."; \
	 awk "/slowest .* durations/,0" $$out > $(DURATIONS).tmp; \
	 { printf "# Où passe la passe complète\n\n"; \
	   printf "%s · \`%s\` · %s\n\n\`\`\`\n" \
	     "$$(date +%Y-%m-%d)" "$$(git rev-parse --short HEAD)" "$$counts"; \
	   cat $(DURATIONS).tmp; printf "\`\`\`\n"; } > $(DURATIONS); \
	 rm -f $(DURATIONS).tmp; \
	 tail -1 $$out; \
	 rm -f $$out; \
	 : "La colonne durée porte le temps TRAVAILLÉ ; l'horloge murale ne la suit que"; \
	 : "quand elle en diverge de plus de 20 %, et alors elle est nommée comme telle."; \
	 dur="$$(( $${worked:-$$elapsed} / 60 ))m$$(printf '%02d' $$(( $${worked:-$$elapsed} % 60 )))s"; \
	 if [ -n "$$worked" ] && [ $$elapsed -gt $$(( worked * 12 / 10 )) ]; then \
	   dur="$$dur (horloge $$(( elapsed / 60 ))m, machine en veille)"; \
	 fi; \
	 printf '| %s | `%s` | %s | %s | %s |\n' \
	   "$$(date +%Y-%m-%d)" "$$(git rev-parse --short HEAD)" "$$result" \
	   "$$dur" "$$counts" >> $(LOG); \
	 tail -1 $(LOG); \
	 exit $$status

report:
	@tail -5 $(LOG)

# CE QUI A CHANGÉ, ET SEULEMENT ÇA (D-309). `--impact` (tests/impact_fichiers.py) ne
# rejoue un test vert que si un fichier qu'il importe, même indirectement, ou qu'il lit
# (D-entrées, cas, scénarios, data/) a changé depuis ; jamais vert, rouge ou sauté, il est
# rejoué. Les lents compris (`-m ""` moins les chronomètres) : c'est la sélection qui les
# rend abordables. En parallèle sur JOBS workers ; les tests de tests/lourds.txt sur un
# seul d'entre eux. Les chronomètres tournent ensuite seuls. La première fois, TOUT tourne.
# Ce n'est pas `make full` : il ne journalise rien, et ne remplace pas la passe complète
# qu'une revue demande. pytest-testmon a été essayé et écarté : sa couverture ne voit pas
# ce qu'un cache de processus n'exécute qu'une fois, et il laissait passer le bug de D-306.
JOBS ?= 4

impact:
	$(VENV)/ruff check src tests scripts
	$(VENV)/python -m pytest -q -m "not chrono" -n $(JOBS) --dist loadgroup --impact
	$(VENV)/python -m pytest -q -m "chrono" --impact
