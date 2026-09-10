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

VENV ?= .venv/bin
LOG  := reports/full_pass_log.md

.PHONY: gate full lint report

gate:
	$(VENV)/ruff check src tests scripts
	$(VENV)/python -m pytest -q

lint:
	$(VENV)/ruff check src tests scripts

full:
	@mkdir -p reports
	@test -f $(LOG) || printf '# Full-pass log\n\nOne line per `make full`. CI cannot run the population tests — it has no\npopulation, by design — so this file is the only record that the full suite is\ngreen. No review handoff goes out without a line newer than the work it reports.\n\n| date | commit | result | duration | tests |\n|---|---|---|---|---|\n' > $(LOG)
	@$(VENV)/ruff check src tests scripts
	@start=$$(date +%s); \
	 out=$$(mktemp); \
	 $(VENV)/python -m pytest -q -m "" --durations=15 > $$out 2>&1; \
	 status=$$?; \
	 elapsed=$$(( $$(date +%s) - start )); \
	 counts=$$(grep -E '[0-9]+ (passed|failed|error)' $$out | tail -1 \
	   | sed -E 's/ in [0-9].*$$//'); \
	 : "un run TUÉ (SIGINT 130, SIGTERM 143) n'est PAS un échec de la suite, et"; \
	 : "les deux se lisaient FAIL avec des points de progression en guise de"; \
	 : "comptes — indiscernables dans le journal. D-113."; \
	 if [ $$status -eq 0 ]; then result=PASS; \
	 elif [ $$status -ge 128 ] || [ $$status -eq 2 ]; then result=TUÉ; \
	   counts="$${counts:-interrompu, aucun résumé produit}"; \
	 else result=FAIL; fi; \
	 [ "$$result" = FAIL ] && tail -40 $$out; \
	 tail -1 $$out; \
	 rm -f $$out; \
	 printf '| %s | `%s` | %s | %dm%02ds | %s |\n' \
	   "$$(date +%Y-%m-%d)" "$$(git rev-parse --short HEAD)" "$$result" \
	   $$(( elapsed / 60 )) $$(( elapsed % 60 )) "$$counts" >> $(LOG); \
	 tail -1 $(LOG); \
	 exit $$status

report:
	@tail -5 $(LOG)
