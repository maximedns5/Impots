# Impôts — the two test invocations, and the one that has to leave a trace.
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
	 out=$$($(VENV)/python -m pytest -q -m "" 2>&1 | tail -1); \
	 status=$$?; \
	 elapsed=$$(( $$(date +%s) - start )); \
	 counts=$$(printf '%s' "$$out" | sed -E 's/.*?([0-9]+ passed[^,]*(, [0-9]+ [a-z]+)*).*/\1/'); \
	 result=$$( [ $$status -eq 0 ] && echo PASS || echo FAIL ); \
	 printf '| %s | `%s` | %s | %dm%02ds | %s |\n' \
	   "$$(date +%Y-%m-%d)" "$$(git rev-parse --short HEAD)" "$$result" \
	   $$(( elapsed / 60 )) $$(( elapsed % 60 )) "$$counts" >> $(LOG); \
	 tail -1 $(LOG); \
	 exit $$status

report:
	@tail -5 $(LOG)
