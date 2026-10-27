# State of the project, and the directions open — 2026-10-27 (Phase 11, M0 to M6)

The 2026-10-27 update adds D-256, Phase 11's M5: the self-financing of a targeted cut of
employer contributions, as the owner chose for R5. A new row and channel C11 put θ = 0 on
C2's own reading (its jobs, each valued at what a full-time SMIC job brings the public
finances in the year, measured on the engine: 10 032 € in 2026), θ = ½ on the low end of
the Trésor-Éco n° 97's range, 30 %, and θ = 1 on its top, 60 %. C11 opens only on a cut
that is targeted in its year, all of it, and never where Mésange's targeted variant would
have a balance row, which would count the same jobs. The Trésor-Éco's jobs are a medium-
term stock, counted here from the reform's year, and said. One adversarial pass,
SCOPE_PROBLEM, its repairs applied; eighteen hand mutants killed. The curve of D-241 is
replayed with it, preregistered: costs as D-242's to the euro, Δb at θ = ½ 0.70 times
D-242's, the box from 0.40 times to (1 − C2's share) times, and no bundle lowering the
debt at any corner.
The fourth 2026-10-26 update added D-255: C2's gap is explained, and it was the chain's.
`_employer_inputs` took every earner of the whole frame at the frame's weights, with a cost
change only for the households the pass had priced, one in ten on the quick tier: the jobs
near the SMIC came out 5.8 to 6.5 times too low. The earners are now those of the run's
households, each at the weight the subsample gives them. At the study's first bundles the
`t_delta` counts 9 936 jobs per bn (1 555 before), the floor 4 830 (748), the plafond 738
(128); costs and debt do not move, C2 being an index. What is left of the gap with the
CAE is C2's own profile: at −0.5, a cut landing wholly at the SMIC gives 22 480 jobs per
bn, the CAE's figure. At 12 000 € per job, C2 now says 5.8 to 11.9 % self-financing, not
0.9 to 1.9 %; R5 is still the owner's. The study page keeps its passes' C2 figures and says
beside each that they were counted before D-255. Nine hand mutants killed.
The third 2026-10-26 update added D-254: the CVAE has a knob for its whole schedule, and
is priced on the annual path. `cvae_echelle` scales the year's ceiling, brackets and
dégrèvement together, as the law moves them; it is read back against the law, and finds
nothing to scale once the CVAE is abolished in 2030. The carried path — `/predictif/
simulate` and the explorer — now refuses a firm knob whose law moves within its horizon,
the CVAE from 2028, and points to `impots predictif`. Advancing the abolition to 2026
costs 11.1 bn over 2026–2029 and leaves the 2035 debt 0.32 point higher (aged view); the
carry would have said 1.10. Halving the schedule: 5.6 bn, +0.16 point. No loop: the CVAE
has no Mésange variant. The firm layer likely understates the CVAE by about two fifths.
C4 now says an abolition and a year without the tax instead of failing. Sixteen hand
mutants killed.
The second 2026-10-26 update added D-253: the PFU replay has run on its preregistration
commit, `80a7405`, and `docs/PREDICTIF_ETUDE.md` renders it in its own section. With the
wage shift, no PFU bundle lowers the 2035 debt at θ = ½ any more: +0.05 to +0.22 point
under « tenu », against −0.03 to −0.05 in D-251, and +0.16 to +0.61 under « éteint ».
D-251's sign has turned: at one point, the shifted wages take back 0.27 of C10's 0.37 bn.
Only the corners where the multiplier is 1 still fall, 12 or 13 of 32 under « tenu ». At
no shift, the replay gives the wider menu back to the last figure. Every point of D-252's
prognosis held, to the thousandth. Thirteen hand mutants of the page script killed.
So no cut on the study's menu lowers the debt at θ = ½ under these hypotheses.
The first 2026-10-26 update added D-252: C10 now counts the wage the firm owners stop paying
themselves when their dividends rise, and the wider menu's PFU is replayed with it,
preregistered before its pass. The shift is a new row, 0 to 0.519 euro of taxable wage
per euro of dividend, centred on 0.309, read from Table 2B of Bach et al. Each euro
shifted takes back 0.7266 € in 2026: 1.1406 € of levies less the IS on the profit it
becomes, both measured on the engine at six PASS. The verifier first returned WRONG, on
the table's sample (the wealth-tax payers, not the top of the stable income), then
SCOPE_PROBLEM on the repaired row. The prognosis: under « tenu », no PFU bundle lowers the
debt at θ = ½ any more, +0.05 to +0.22 point, and D-251's sign turns; only corners where
the multiplier is 1 still fall. Eighteen hand mutants killed. The replay runs next (D-253).
The sixth 2026-10-25 update added D-251, the second step of M6: the study on the wider
menu has run on its preregistration commit, `ca6288d`, and `docs/PREDICTIF_ETUDE.md`
renders it in its own section. An IS cut lowers the 2035 debt for no θ: 0.30887 point per
billion of first-year cost, +0.26 to +3.39 points, no loop, the GDP effect beside it. A
PFU cut lowers it at θ = ½ under « tenu », at each of its four bundles, by 0.03 to 0.05
point: the first bundle of the whole study to meet the target at θ = ½. None is robust,
only the corners where the multiplier is 1 fall, and the sign rests on what C10 leaves
out: the wage shift would turn it at a cost above 29 % to 10 % of the wages it moves.
Under « éteint », +0.08 to +0.35. The cut goes to the top decile (197 € a household). The
four controls give the study back to the last figure. Every point of D-250's prognosis
held. Fourteen hand mutants of the page script killed.
The fifth 2026-10-25 update added D-250, the first step of Phase 11's M6: the study on
the wider menu is preregistered before any of its passes. Two new instruments, four
bundles each: the IS normal rate, from 25 % down to 21.75 %, and the PFU, from 12.8 %
down to 8.8 %, inside C10's support. The study's four instruments are replayed as they
are, as controls. Left out, with reasons: the CVAE, which the law abolishes in 2030
while the explorer carries the first year's cost ten years, and whose one rate knob
moves the top band only; the t_delta's self-financing, which waits on M5. What the code
got first: the CDHR is now a receipt of the ledger. openfisca takes it out of disposable
income but not out of `ir`, and with imputed capital it takes back 18 % of a one-point
PFU cut in 2026 (0.693 bn against 0.842), so the ledger refused the pass. Its holders'
dividends, 10.2 of 53.1 bn, leave C10's base. This corrects D-249's 2026 row. C8 is read
in the chain for an IS cut. The prognosis: no IS bundle lowers the debt; under « tenu »,
every PFU bundle lowers it by about 0.03 point at θ = ½, only at the corners where the
multiplier is 1, and on a sign the uncounted wage shift could turn. 226 mutations, 225
killed, one equivalent.
The fourth 2026-10-25 update added D-249, Phase 11's M4: the PFU has its knob, read back
(guard 9), a household can declare capital income, and the dividends' response is channel
C10, in the receipts. Its source is Bach et al. (PSE WP 2019-70 v2): elasticities to the
net-of-tax rate of 2.5 (firm owners, 2018) to 3.2 (2013), 0 to 2.4 for the others, and the
firm owners' share of declared dividends, 73.8 to 80.0 % in 2018–2021, read off Figure 2d's
vector drawing and checked against panel (b) and the text's 9 bn. A one-point cut costs
0.79 bn statically; C10 brings back 0.38 to 0.63 bn (θ = 0 to 1), half at θ = ½. Not
counted, and each lowers that: the 0.31 € of wage the owners pay themselves less per euro
of dividend, and the future plus-values. The social levies are measured, 18.6 % from 2026.
The capital is imputed whenever the reform moves the PFU, and ages with the frame on the
wage index. 40 hand mutants killed; the adversarial pass returned three SCOPE_PROBLEMs.
The third 2026-10-25 update added D-248: the owner had F1b built, and capital income is
imputed, opt-in (`impute_capital`, `--impute-capital`). The PFU's base comes from DGFiP n°
41's hors-barème tax by fractile of RFR per part, CEHR stripped, over the law's 12.8 %;
the 2042 boxes split it (62 % dividends, 23 % gains) and their total, 80.69 bn, gives
back the derived 80.63. Every foyer of a band gets the band's base, times France's foyers
per ménage over the population's (×1.17): the population holds 15 % fewer foyers. On the
full population the PFU owed is 10.26 bn against 10.32, the social levies 13.79 bn (a
new receipt), the IR +11.8 bn with the CEHR; benefits fall 0.73 bn on 20 000 ménages. A
foyer under the 61 € collection threshold pays none of its PFU. Refused beside it: another
year (the base is not aged) and the top-tail rake, which would cut wages 5.4 % to make room
for the capital. 28 hand mutants killed.
The second 2026-10-25 update added D-247, Phase 11's M3: it opens no index. Both conditions
M0 fixed were computed or read on the files, and neither holds. The OECD's effective-rate
method (`entreprises/taux_effectifs.py`, parameters read off the annex, France's 2025
rates manifested from the OECD's API) gives back buildings, inventories and software
within a tenth of a point, but not the tangibles, whose five subgroups share one
published allowance: the composite EMTR comes out 15.62 against 14.97, so the national
entry index (Da Rin et al.) is refused. The two gaps stand in the ratio a varying
allowance gives (8.88 against 8.99): the parameters are missing, not the method. The
authors' own EATR needs the EY guide and STAN margins, which the project lacks. The
investment index stays closed: equation (6) sits around reference values the paper does
not print, and figure A E.1 is a picture. Guard 7 is in: the IS's GDP effect plus
investment or entry is refused by name. The sweep holds 219 mutations, 218 killed.
The first 2026-10-25 update added D-246, Phase 11's M2. The IS on growth is a store row
read off Gechert and Heimberger's PDF (θ = 0 at −0.0001, θ = 1 at 0.019, θ = ½ at 0.00945 point a
year per IS point cut), with its rank, countries and years, and the store now refuses an
international row without them or a lower rank beside a higher one. Its index, `pib_is`,
is a ten-year ramp (0.0945 % of GDP at ten years at θ = ½), held outside the debt by
D-218. The elasticity loop is refused by computation: read off DP 098, 0.585 or 0.630,
it misses Mésange's own ratio by more than a quarter at 9 or 8 of the 15 variant-horizon
pairs, the employer contributions and VAT at every horizon. The aged firm view follows
nominal GDP from the 2023 vintage (×1.087 in 2026, ×1.421 in 2035 at 1 % real and 2 %
prices); a vintage without a year is refused. `impots predictif` takes a scenario's
`firm_reform`, by layer: one IS point alone costs 3.10 Md€ frozen and 3.38 aged in 2026,
and leaves the debt 0.75 and 0.93 point higher in 2035, in 24 seconds. The real run found
two defects, fixed: the annual report did not name the firm layer's conventions, and two
closed-channel reasons still denied that the trajectory prices the IS.
The third 2026-10-24 update added D-245, Phase 11's M0: eleven documents manifested and
read on file, `docs/M0_PHASE11.md`, two adversarial passes. Fixed: the IS on growth
(Gechert and Heimberger: θ = 0 at the bias-corrected centre, no effect; θ = 1 at the raw
centre, 0.019 point of growth a year per IS point; a ten-year ramp) and firm entry (Da
Rin et al., 0.043 to 0.356 point per EATR point). Closed, with reasons: the elasticity
loop fails its variant-by-variant cross-check against Mésange at all three horizons, so
the IS has no loop and, by D-218, its GDP effect stays an index outside the debt path; the
investment index opens in M3 only on the OECD's equation (6), once its decomposition is
reproduced for France. Left to the owner: the self-financing of targeted cuts, which
French sources put anywhere from 1 % (C2's jobs) to 60 % (Trésor-Éco n° 97); D-242 holds
until then. C2's job count, fifteen times below the CAE's at a similar elasticity, was
checked on a population pass and was diluted by the subsample (D-255): corrected, C2 says
5.8 to 11.9 %.
The second 2026-10-24 update adds D-244, Phase 11's M1: a firm reform enters the
predictive chain. `/predictif/simulate` takes a `firm_reform`, and `impots exploration` a
`firm_base` and firm knobs in its grid, alone or beside the households' reform. The first
year's cost is the sum of the two layers, each named, and a response whose cost is not
that sum is refused. A firm reform alone runs no population pass; its taxes have no
Mésange variant, so the loop is said absent, not zero; the CIR stays out (D-222). One IS
point, 25 to 24 %, costs 3.10 Md€ in 2026 on the 2023 firm population and 2.73 Md€ from
2027, once the CEBGE has lapsed. Two conventions are named in the note: the firm
population is not aged, so the same figure stands in both views, and the IS is counted by
exercise. The aged firm view and the annual path, `impots predictif`, go to M2. The sweep
holds 179 mutations, 178 killed, 1 equivalent.
The first 2026-10-24 update added D-243 with its spec. The owner asked where the
project stands against the finished product. The answer, in orders of magnitude: about
half way; the biggest hole is half the owner's question, firms and startups, on which
the machine says almost nothing. The owner confirmed the objective (D-213), named the
finished product as both an argued answer and an online tool others use, and allowed
published international ranges where no French estimate exists, under the seven
conditions of the spec's §2. The roadmap is reordered:
- Phase 11 puts firms, startups and capital into the chain: the IS on GDP with a loop,
  investment and creations as national indices, capital income and the PFU, and the
  self-financing of targeted contribution cuts; then the study is asked again.
- Phase 12 tests the chain on past reforms.
- Phase 13 is the online product.
Nothing is built yet; M0 reads seven documents first.
The third 2026-10-23 update added D-242: the answer of the study replayed with the 2026
curve. Both searches ran on the preregistration's commit, `893e4de`: eight bundles,
sixteen passes. No cut of the curve lowers the debt in 2035, for no θ: the floor costs
0.76 to 7.62 Md€ in 2026 and leaves +0.24 to +2.35 points, the `t_delta` 1.00 to
7.01 Md€ and +0.31 to +2.17 points, the same under both persistences, each θ box a
single point. Δb is 0.30887 point per billion of first-year cost, the ceiling's in the
study: nothing but the cost enters, since the loop is absent (no balance row for the
targeted variant) and the jobs do not reach receipts. All six forecast points hold;
per billion, the `t_delta` makes 2.08 times the floor's jobs near the SMIC (C2). The
frozen view prices the `t_delta` 9 % above the aged one. `docs/PREDICTIF_ETUDE.md` has
the section, its loader eight refusals, each seen failing on a mutation.
The second 2026-10-23 update added D-241: the study is replayed with the 2026 curve, and
preregistered first. Two requests under `etude/courbe/`, on the study's frame field for
field: the floor `t_min` from 2 % to 2.1, 2.4, 2.7 and 3 % (0.76 to 7.62 Md€), and the
`t_delta` from 37.81 % to 38.31, 39.31, 40.31 and 41.31 % (about 1 to 7 Md€), committed with
the forecast before any pass. The population carries no firm size, so every employee is in a
firm under 50: the grid walks that `t_delta`, and the one over 50 reaches no one (0 €,
measured). The forecast: no cut lowers the debt in 2035, for no θ, because the shock falls
under Mésange's targeted variant, which has no balance row, and the jobs C2 counts do not
enter receipts; Δb is the cost carried, 0.3089 point per billion as for the ceiling. The
result will be D-242.
The first 2026-10-23 update added D-240: knobs for the 2026 réduction générale's curve, the
floor `allegement_general_t_min` and the two `t_delta` (under and over 50 employees). Each
writes its child of the tree, read back by the engine; before 2026 each is refused by name,
the refusal naming the rates that then govern, and an old rate refused in 2026 now names the
knob that replaced it. One point on the floor costs 7.62 Md€ in 2026, one point on both
`t_delta` 2.00 Md€ (aged view, mechanical). Their shock goes to Mésange's targeted variant,
rightly this time, which prints no balance row: the loop is absent for them, and said so.
The page's employer panel has the two fields.
The fifth 2026-10-21 update added D-239: the réduction générale's ceiling is reclassed. From
the 2026 refonte the ceiling is only the exit threshold of the 2 % floor, so raising it
relieves wages above 3 SMIC, not low wages; from `REFONTE_YEAR`, held against openfisca's
tree, its shock goes to Mésange's uniform variant, which has a balance row, instead of the
targeted one, which has none. Before 2026 and for the bandeaux nothing changes, nor does the
CICE validation (D-227). Replayed outside the preregistration, with the study's request and
costs to the euro: no raise lowers the debt in 2035 at θ = ½, +0.47 to +1.48 points under
« éteint », +0.13 to +0.43 under « tenu », where the corners with the multiplier at 1 go
below zero, as for the other three instruments. The study page carries it in its own
section. The sweep holds 167 mutations, 166 killed.
The fourth 2026-10-21 update added D-237 and D-238, Phase 10's M4: **the study is done**,
its gate (`make full`) the owner's. The question, « quelles baisses d'impôt font baisser la
dette en 2035, et pour quels θ ? », was preregistered before any pass (D-237): four
requests under `etude/`, sixteen bundles of the CSG on earnings, the réduction générale's
ceiling, the décote's rate and the IR scale (`ir_bareme_echelle`, a named transformation),
and a seven-point forecast. The answer (D-238, `docs/PREDICTIF_ETUDE.md`): at θ = ½, no cut
lowers the debt in 2035, under either persistence or view; +0.23 to +2.82 points under
« éteint » with no corner below zero, +0.08 to +1.20 under « tenu », where exactly the
corners with the macro multiplier at 1 go below zero, whatever the other θ. The forecast
held. A finding: the ceiling falls under Mésange's targeted employer variant, which prints
no balance row, so its loop is ABSENT, not zero, and the classing of a 2026 ceiling raise
as a low-wage cut is to be revisited in its own entry. The reports now carry what the
chain lacks; a second round, on `e0c3d7f`, gives the first back figure for figure, the
first kept under `reports/etude_premier_tour/`. The sweep holds 166 mutations, 165 killed.
The third 2026-10-21 update added D-236, Phase 10's M3: `impots predictif` carries
behaviour and the loop (`--behavioural`, `--macro`, `--persistence`). Each year is priced
whole through the simulator's own pass, `_price_first_year`, in both views: its cost, the
channels' inputs and its impulse, so receipts at θ are read year by year and the loop
superposes one Mésange impulse per year. Past three years with no persistence named, both
scenarios stand side by side and the report has no path of its own (D-230). The command
refuses before any pass the « indexe » reference, another sample or vintage than the
simulator's, and a persistence without the loop. A D-228 bug found on the way: the
example snapshot sat under `predictif_*.json`, so `GET /predictif` listed a report its
schema refused and the page, which opened only the first name, showed no annual report;
it is renamed, and the page now draws every report listed. A real run, half a point of
deductible CSG from 2026 to 2029 at θ = ½: 4.41 Md€ in 2026 (the exploration's figure,
to the euro), and the debt gap reaches +0.354 point in 2029 if the macro effect dies,
+0.111 if it holds. Eight passes, fourteen minutes, 6.1 GB. The sweep holds 150
mutations, 149 killed, one equivalent.
The second 2026-10-21 update added D-235, Phase 10's M2: the explorations are read back.
`GET /explorations` and `GET /explorations/{name}` serve the reports, read only, through
`ExplorationReport`, which refuses eight reports a reader would misread (a candidate
without its θ verdict, « none » without the closest bundle, a bundle missing, no commit…)
and answers 500 with the reason rather than show one in part. Each bundle now carries its
first-year mechanical cost in both views: a point of deductible CSG costs 8.81 Md€ in
2026 on the aged population. The page has a panel: the question first, one table per
persistence search, cost, debt gaps, θ box and verdict per bundle, the closest when none
holds, the commit. The sweep holds 134 mutations, 133 killed, one equivalent.
The first 2026-10-21 update added D-233 and D-234: **Phase 10 is open**, to make the owner's
question askable (`docs/PHASE10_SPEC.md`), and its M1 is in. `impots exploration
<request.json>` runs D-224's conditional explorer from a validated request file, pricing
each bundle in both views through `/predictif/simulate`'s own hypotheses and first-year
pass (a test holds the two equal), both persistence scenarios from one pass per bundle and
view, into `reports/exploration_<name>.json`, which names its commit and holds every
bundle evaluated. A first real run, two cuts of the deductible CSG on earnings: neither
lowers the debt in 2035 at θ = ½ (+2.26 and +1.13 points under « éteint », +0.83 and
+0.42 under « tenu »); under « tenu » the sixteen corners with the strongest multiplier
lower it. The guard sweep holds 117 mutations, 116 killed, one equivalent.
The third 2026-10-20 update added D-232: `impots data fetch` now trusts OpenSSL's default
store completed by `certifi`'s, so the two downloads D-231 had to rerun by hand on the
owner's Mac pass on their own. Their roots, GlobalSign Root R46 and Sectigo R46, are in
`certifi` and missing from that store; the failure was reproduced against the real
hosts, word for word, with a store stripped of those two roots. `SSL_CERT_FILE` is still
read, and the check stays whole; four loopback TLS tests hold all three.
The second 2026-10-20 update added D-231: **Phase 9 is closed.** The owner ran `make full`
on `7cce463`, D-230's merge, in a fresh clone: PASS, 2 475 passed, 109 skipped, 102 min
41 s. It is the first whole-suite pass since D-204's commit, so it also covers D-205 to
D-212, the pension recalibration among them. Of the Phase 9 tests, only the two CIR
tests that read the Voies et moyens tome II can have skipped: that file is neither in the
`tests` profile nor among the twelve Phase 9 sources. On macOS 26.2, Homebrew's Python
3.11 is broken (its `pyexpat` needs a newer expat than the system's), so the venv runs on
a uv-managed 3.11.16; that Python reads OpenSSL's certificate store rather than the
keychain, and two downloads were rerun outside it, `fetch` checking both against the
manifest.
The first 2026-10-20 update added D-230: the owner's two choices left open by D-218. Past three
years with the loop and no persistence named, `/predictif/simulate` no longer refuses: it
computes « éteint » and « tenu » from the one population pass and returns them in
`side_by_side`, the response carrying no path of its own so that neither reads as the
lead; the page draws one table per scenario. The `multiplier_by_instrument` row is
reopened: its 1.0 linearity bound is kept, written now as the project's choice (the
document sets no threshold, and folio 108 says « quelques points de PIB »), and box 15
matches the sum of the VAT and employer-contribution variants to one unit of the last
printed digit, not « au centime ». An independent adversarial pass confirmed the first
and found three scope errors in the second, all corrected. The guard sweep has 103
mutations, 102 killed, one equivalent.
The twelfth 2026-10-19 update added D-229, M6's fifth step: the guard sweep.
`scripts/sweep_gardes_phase9.py` reads its catalogue from the code — every `raise` of
`predictif/`, of the two debt scenario modules, of D-224's explorer additions and of the
predictive API and command, plus fourteen guards written by hand (§2.4's guards 1 and 4
to 7, the page) — mutates each guard in turn and runs the tests that must kill it. The
first pass: 98 mutations, 27 survivors, among them a reform's priced years past the
horizon dropped without a word, a macro response of zero for an impulse with no
instrument, six API translations never exercised, and the chain's absences held to no
reason. Each survivor got a kill test seen failing on its mutation, or, once, a named
equivalence; `Trajectoire` now refuses an absence without its reason. The second pass,
on the commit with the tests, kills every mutation but that one, 98 of 99.
`tests/test_gardes_phase9.py` refuses a report that does not name every guard of today's
catalogue, so a guard added later fails until the sweep (`--missing`) has run on it.
The eleventh 2026-10-19 update added D-228, M6's fourth step: §9.4's worked example,
`docs/PREDICTIF_EXEMPLE.md`, which says it illustrates the machinery and recommends
nothing. The first income-tax bracket goes from 11 % to 10 % in 2026, 4.84 bn on the aged
population, 4.80 bn with behaviour at θ = ½. In 2035 the debt gap is +1.30 point of GDP
under frozen spending with the macro effect switched off after three years (box +1.13 to
+1.47), +0.54 with it held (box −0.20 to +1.28: the sign depends on θ) and +1.48 under a
constant spending share, where the loop does not apply; mechanical +1.50 everywhere,
behaviour −0.01. Persistence weighs more than everything else, and at the corner where
the multiplier is one IMK standard deviation above Mésange's centre the held feedback
repays the cut. `scripts/write_predictif_exemple.py` prices the first year once
(`--price`, three minutes, refused on an uncommitted `src/`), runs the chain under each
scenario and at every corner, and renders the page from `reports/exemple_predictif.json`
alone; the tests hold the page to the file everywhere and the file to the chain where the
accounts and Mésange are readable.
The tenth 2026-10-19 update added D-227, M6's third step: §9's coherence and the
preregistered containment. The rule — both Mésange variants of the CICE, jobs at three
years, the θ box must contain 100 000 to 400 000 and θ = ½ fall inside — was committed and
pushed before any number, with the expectation that it might fail. It passes: 31 200 to
443 300 FTE (uniform), 57 700 to 601 800 (targeted), centres 237 300 and 329 700. The
reason is recorded with it: the IMK standard deviation is almost the size of Mésange's
centre, so containment is weak evidence and the centre carries the test.
`predictif/validation.py` refuses a case never committed, one whose first commit already
held its outcome, or one whose rule moved. A null reform is null at every θ with
behaviour and loop, and the loop's GDP and balance come from one Mésange table. The entry
was written as D-225 and took D-227 when D-225 and D-226 reached `main` first.
The ninth 2026-10-19 update added D-225: the page names the fast version's population
view above its table, « vieillie », and shows its `population_note` under it, the
uprating caveat included. The fast version's entry took D-225 at the same time and
becomes D-226, every reference with it.
The eighth 2026-10-19 update added D-226: the fast version of `/predictif/simulate` now
prices its first year on the population aged to that year, « vieillie », the headline
of `impots predictif` and of the conditional explorer, by the owner's choice. It priced
the 2024 population as it is, and did not say so. The request gains a required
`uprating` block, the wage index and its source; prices are the growth scenario's. The
response names the view in `population_view` and carries the uprating caveat in
`population_note`. The EMTR caches now key on the uprating, so that the aged and the
as-built population never serve each other's marginal rates. The first-year cost rises
by roughly the measured gap, 5 to 9 %; the real run is the owner's.
The seventh 2026-10-19 update added D-224, M6's second step: the explorer searches the debt
at a fixed θ (§8). Its allowlist gains `dette_conditionnelle`, the reform's debt gap at
year T under named θ and scenarios, met from below; θ is required for it and refused for
the mechanical target, and no bound may name θ. Each candidate is re-read at the 2^K
corners of its θ box and marked « robuste » or « dépend de θ » with the first corner that
breaks it. `predictif/exploration.py` builds the evaluator from one population pass per
view and bundle. On a grid of CSG rates against −0,30 point of GDP in 2030, three bundles
meet the target at θ = ½ and none is robust: with the multiplier one IMK standard
deviation above Mésange's centre, the debt rises. The sixth 2026-10-19 update added D-223,
M6's first step: §7's indices.
`predictif/indices.py` holds a closed list of thirteen, each with its unit, its stage and
its source, grouped by whom they are for; an unknown index is refused by name and no index
may be added to another, the two employments (C2's persons, Mésange's full-time
equivalents) by their own reason. Three Mésange rows the reader already parsed —
consumption, business investment, real disposable income — enter the macro store after an
adversarial pass (SCOPE_PROBLEM, all 72 values exact); on its advice consumption and
investment follow the multiplier's θ like jobs, and only income, which holds the shock
itself, stays fixed at the centre, a departure from §7 recorded there. `/predictif/simulate`
carries the block and the page shows it; the trajectory gains the interest on the extra
debt. On D-220's CSG rise the indices give −0,23 % of consumption and −6 500 FTE in year
one, and 894 M€ of gross earnings lost to hours. The fifth 2026-10-19 update added D-222,
M5's last step. Two MESR GECIR publications are
now in the manifest, and D-154's gate on the CIR passes: the CIR is priced, with a banner,
on the créance of the 2019 millésime, 30 % below the 100 M€ threshold and 5 % above,
rebuilt from tableau 04 to within 0,09 % of the published 6 785 M€. A créance is not a
year's receipts, so the CIR has its own block in `/entreprises/simulate`, with the Voies
et Moyens dépense fiscale beside it, and stays out of `reform_cost`. §6.4 opens as C9, an
illustrative R&D index on the IPP's report n° 22 (« entre 0.8 et 1.4 »): an adversarial
pass returned SCOPE_PROBLEM, and the multiplier is now applied as a fixed point, since its
denominator already holds the induced créance, with m τ < 1 guarded. A cut of the full
rate to 25 % lowers the créance by 1 114,9 M€ and R&D by about 1,66 Md€. The
trajectory's closed-channel reasons for R&D and for company creations (the latter false
since D-221) now say why both stay out of it. The fourth 2026-10-19 update added D-221, M5's second
step. France Stratégie's 2023 final report on the capital-tax reforms, which M0 could
not reach (its address moved), is
manifested and read: it quantifies nothing for the IS and investment, which stay closed
with that reason. Its commissioned IPP study (report n° 47) does measure how company
creations respond to the taxation of profits, and §6.3 opens as C8: an illustrative
index, never revenue, for the IS normal rate only. The estimate is relative between
sectors and does not separate the IS from the flat tax, so its support is zero and its
range runs down to zero; one point of IS normal rate moves the creation rate by about
0,17 point. A channel's own band now carries the channel's unit rather than euros. The
third 2026-10-19 update added D-220, the first channel of Phase 9's M5: labour supply
reopens as C7, on the cells of Bargain, Orsini and Peichl (IZA DP 6735, now manifested)
that `behavioural/bop.py` reads out of the PDF. Four rows, one per group — women and men
in a couple, women and men alone — each a convention applied to the 1998 and 2001 cells:
own-wage plus cross-wage for a couple, the mean of the two years at the centre, the
envelope of the 95 % intervals widened for rounding. An adversarial pass returned
SCOPE_PROBLEM and its six repairs are in. C7 opens for the CSG on earnings only, on a
household sample the paper's own selection defines. A one-point rise of the deductible CSG
loses 384 M€ of its 8,37 Md€ to hours. The second 2026-10-19 update added D-219, Phase 9's
M4: neither missing multiplier opens.
The transfers rest on two IMK meta-analyses that disagree by a factor 2,5 on the width,
with no horizon profile and no balance row; Mésange 2017 has no corporate-tax variant and
no re-estimation has been published since. Both are shown closed on every trajectory, and
§5's two guards hold any future row: a transfers row loads only at `confidence: low`,
graded illustrative, and an IS delta receives no multiplier. The first 2026-10-19 update
added D-218, Phase 9's M3: the GDP → primary-balance loop read from
Mésange's « Solde primaire des APU » row, which an adversarial pass cleared with its
values exact and its scope repaired. The loop applies only under « Dépenses gelées en
volume », to the uniform fiscal variants, at one to three years, with a named persistence
scenario beyond and none by default. The reform's GDP divides its debt, and the macro
fan slice is computed from the multiplier's θ. The first real run found the shock builder
fed every population total, which had left the population endpoint's macro fan
unavailable for any costed reform; it now reads only the instruments. The sixth
2026-10-16 update added D-217,
Phase 9's M2: every open behavioural row declares
which end of its range θ = 1 designates, θ places each row through its published centre,
a pinned store runs the Phase 3 channels at θ unchanged, and the debt path's behaviour
slice becomes the θ box, read at its corners. No θ has a default — not the endpoint's,
the command's or the page's. The fifth added D-216, Phase 9's M1b: `impots predictif` prices every
year of the horizon on the frozen and the aged population and writes
`reports/predictif_<scenario>.json`, which `GET /predictif` serves; the page gains a
« Et la dette ? » panel whose scenario lists start empty. The fourth added D-215, Phase 9's M1: the chain reform → primary
balance → debt is linked (`predictif/chaine.py`, `dette/reference.py`), the spending rule
finally computes, growth and rate scenarios are named, and `POST /predictif/simulate`
serves the fast version (first projected year priced, later years carried as a share of
GDP, labelled). The third added D-214, Phase 9's reconnaissance (`docs/M0_PHASE9.md`):
Mésange's « Solde primaire des APU » row can carry the GDP → receipts loop, under
`gele_en_volume` only, for the fiscal variants, at one to three years, with the reform's
prices held. The second added D-213: the owner lifts the « no predictive model » rule
in favour of a conditional predictive layer, where every effect is set by a θ in [0, 1]
inside its published range, and `docs/PHASE9_SPEC.md` specifies it. The first added
D-212: with GitHub Actions out of runners and the owner carrying on without it, the
workflow runs on manual dispatch only. The fourth 2026-10-15
update added D-211: at the owner's request, the pension mass is
calibrated on the retirement boxes 1AS-1DS, 374,4 Md€, instead of the 400,4 Md€ of
« pensions et rentes ». The third added D-210: the 400,4 Md€ pension target decomposed box by
box; 26 Md€ of it are not retirement pensions, and without them art. 3 lands 1,8 % above
the annex. The second added D-209, the three candidate sources of the missing pension
foyers, which account for a quarter of art. 3's gap. The first added D-206 to D-208: `grade` refuses a comparator whose sign
contradicts its amount; art. 3's yield lands above the annex because the population's
pension mass sits on too few foyers; and a correction to D-205, whose cache fallback has
not yet run. The 2026-10-14 version it updates added D-204, the owner's full pass and the
three PLF 2027 registrations graded against the annex, and D-205, the CI cache fallback.
The 2026-10-06 version that one updated superseded the 2026-10-05 one, which stopped at
D-194.
D-195 to D-203 added the population skeleton's case T, case 7DG, a lone adult's
situation de famille, the home-help ceiling's increment for members over 65, the
population's case T on N-2 and N-1, the AAH of a pensioner left out of a spouse's ASPA,
alternating residence, adult dependants, and the MVA among a spouse's ASPA resources.
The 2026-10-05 version had superseded the 2026-10-01 one. That one kept its sections on
Phase 8, the CI and the PLF 2027 up to date, but it never described the household
calculator's arc, D-176 to D-194, and it counted 192 entries. It had itself superseded
the 2026-09-22 version, which predated D-158 to D-171. For any next session: read this,
`docs/CHARTER.md`, `docs/PHASE8_SPEC.md`, `docs/PHASE9_SPEC.md`, and the review file's last addenda
(`docs/REVIEW_2026-08-29.md`).

## Where the project stands, whole-arc

Seven weeks from the first audit, the tool prices household taxation exactly
(DGFiP-validated; niches, prestations, allègements as knobs), firms
(IS/CVAE/C3S/CEBGE on real DGFiP-Ésane cells), wealth (IFI exact, ISF revival,
backtested out-of-sample against IPP's 2017 tables), taxe foncière from the REI
at commune resolution, behavioural effects as bands on adversarially-verified
evidence, and a macro fan that refuses to be a number.

Phase 8 added the **policy laboratory** on top of that: a debt-dynamics spine
that refuses to draw a path without a named spending scenario, an aggregate
instrument engine for taxes with no population behind them, an auditable
coverage claim over the instrument universe, an objective explorer that hands
back candidates rather than an optimum, and a reindustrialization panel whose
defining feature is what it will not answer.

**Phase 8 is on `main`** since 2026-10-01: merge commit `1e12460` (PR #2), which
carries PR #1's 33 commits and `aa869dd`. Merged rather than squashed, so every
hash cited in this document, in `DECISIONS.md` and in the pass log is reachable
from `main`.

**Since 2026-10-02 the work has gone to the household calculator** (D-176 to D-203):
what a household can declare, and twenty-one places where this project corrects
openfisca's reading of the law. It has its own section below.

**2 584 tests at the last logged full pass** (`7cce463`, D-230's merge, run on
2026-10-20): 2 475 passed and 109 skipped, the skips being tests whose source files a
fresh clone does not fetch (D-204, D-231). It covers everything on `main`, Phase 9 and
D-205 to D-212 included. The CI `fast` job counted 1 781 passed,
120 skipped and 223 deselected on `50932a7` (D-200), and D-201 to D-203 add 98 tests. D-198 to D-203 ran
their own tests only, at the owner's request, and the CI `fast` job ran the suite on each
PR. The project also has fourteen replayable `verify_*.py` gate scripts and **257 decision
entries**, D-000 to D-256, recording every error in both directions.

## The household calculator, D-176 to D-203

**What a household can declare** (`api/schemas.py`):
- **per adult:**
  - the gross salary and the birth year;
  - the declared retirement pension (box 1AS, D-175, D-176);
  - the gross unemployment benefit (D-183);
  - a CDAPH incapacity rate and the RSDAE (D-184);
  - the invalidity card (D-188);
  - « fin de droits » for the ASS (D-189);
  - the declared invalidity pension (box 1AZ, D-190).
- **per child:** the birth year, and a disability: rate, establishment or care, AEEH
  complement category and card (D-191); alternating residence (D-201). From 20, a child
  at 80 % or more draws their own AAH, in a famille of their own (D-202).
- **per household:** besides the couple's status and case T, a lone adult's situation de
  famille, célibataire, divorcé ou veuf (D-197). A widowed parent gets the married parts
  and never case T. The persons in case R, card holders living under the roof (D-202).

The page sends every one of them (D-186, then each entry's own page change). Each entry
refuses, with a 422 naming the article, the combinations the engine would price wrong.
The builder also writes what the law derives from them: case 7DG, the home-help credit's
20 000 € ceiling, for a card or an AEEH complement in the household (D-196).

**Twenty-one corrections to openfisca** (`engine.corrections`). Each has a legal citation,
a measured defect, and a kill test that fails the day openfisca changes its mind.

| # | What | Law | Entry |
|---|---|---|---|
| 1 | the minimum deduction may not eat a pension | CGI art. 83, 3° | D-180 |
| 2 | the MVA goes to a full AAH, or to one beside a pension | CSS art. L. 821-1-2 | D-184 |
| 3 | the age of 62 for AAH holders | CSS art. L. 821-2 and L. 351-1-5 | D-185 |
| 4 | the AAH without the ASPA | CSS art. L. 821-1 | D-185 |
| 5 | the high-rent taper spares an AAH beneficiary | CCH art. D. 823-16 | D-187 |
| 6 | the art. 157 bis abatement doubled for a couple | CGI art. 157 bis | D-188 |
| 7 | the same abatement in the benefits' resources | CCH art. R. 822-4 | D-188 |
| 8 | the ASS counts the spouse's unemployment benefit | C. trav. art. R. 5423-2 | D-189 |
| 9 | the invalidity pension bears a pension's levies | CSS art. L. 136-8 and L. 137-41 | D-190 |
| 10 | the ASI of a lone beneficiary in a couple | CSS art. D. 815-19, 2° b | D-190 |
| 11 | each AEEH complement at its own category's rate | CSS art. D. 541-2 | D-191 |
| 12 | the ASS taxed as a salary | C. trav. art. L. 5428-1 | D-192 |
| 13 | the ASI beside a spouse at the ASPA | CSS art. D. 815-19, 2° c | D-194 |
| 14 | the ASPA beside a spouse at the ASI | CSS art. D. 815-1 | D-194 |
| 15 | the home-help ceiling raised for each member over 65 | CGI art. 199 sexdecies, 3 | D-198 |
| 16 | the AAH of a pensioner left out of a spouse's ASPA or ASI | CSS art. R. 815-22 | D-200 |
| 17 | the home-help increment halved for a shared child, not taken off | CGI art. 199 sexdecies, 3 | D-201 |
| 18 | the quotient caps beside a child in alternating residence | CGI art. 197, I, 2 | D-201 |
| 19 | no ASF for a child in alternating residence | CSS art. L. 523-1, I, 3° | D-201 |
| 20 | the first child's ceiling only beside a child | CGI art. 197, I, 2 | D-202 |
| 21 | the AAH's compléments counted as the AAH in a spouse's minimum | CSS art. R. 815-22 | D-203 |

D-193 found openfisca right: case T and the card's half-part stack, each under its own
ceiling. Fourteen tests pin it to the DGFiP's own figures. D-200 settled D-185's couple
question: without a pension, a spouse's AAH counts in the ASPA's resources, and D-185's
couple keeps its 18 943,38 €.

**What the owner has to know.**
- **`to_openfisca.WIRING` is « D-199 ».** Three changes move the population.
  - **D-188.** Correction 6 doubles the abatement for every couple whose two spouses
    are over 65, not only for card holders: on the fixture, 6 of 439 foyers lose
    1 398 € of RFR.
  - **D-195.** The skeleton no longer gives case T to a declarant who lives in a couple.
    On the full EEC, 444 such declarants lose a half-part: +47,1 M€ of income tax,
    weighted, and 10 773 more taxable foyers.
  - **D-199.** The population writes case T on N-2 and N-1 too, where the CSG rate on a
    pension or an unemployment benefit reads the parts: on the fixture, two pensioners'
    disposable income rises, by 839,58 € and 104,64 €. This one needs no rebuild.
  - **The population was rebuilt on 2026-10-14**, on the owner's machine, before the
    full pass and the PLF 2027 registrations (D-204). Nothing keys
    `population_2024.parquet` on the skeleton, so any older checkout still needs
    `impots population build`.
  - Corrections 2 to 5, 8 to 14 and 16 to 21 cannot reach the population: it declares
    no disability, no ASS, no invalidity pension, no alternating residence and no case R.
    Correction 15 reaches it only under a reform: its imputed home-help bases, 3 759,31 €
    at most, stay under the 12 000 € ceiling (D-198).
  - D-203 also pins the housing-aid amount the MVA reads, in the history both paths
    build. The fixture prices the same; a renting couple beside an AAH holder costs about
    5 s more at the full tier.
- **`PENSION_INVALIDITE_MINIMUM`** (correction 10) stops at January 2026. It needs a row
  every January from the Cnav circular, or correction 10 keeps the last amount.
- **Correction 14 rests on CSS art. D. 815-1 as the CNRACL applies it.** No Cnav text
  says how the ASPA is paid beside a spouse at the ASI (D-194).
- **Correction 16 applies the Cnav's list as published** (D-200), an owner's call. The
  first euro of a retirement pension takes an AAH holder's AAH out of the spouse's ASPA
  resources: 29 202,83 € of disposable income with 100 € of pension, 18 943,38 € without.
  Read narrowly, the ministerial letter of 1982 tied the exclusion to the AAH holder
  claiming the allocation supplémentaire.
- **Claiming the ASPA beside an AAH holder** (D-203), an owner's call. The engine never
  claims it (correction 4). From the generation born in 1955 the claim is the household's;
  for D-185's couple it would give about 5 000 € more, and less with a pension. Whether to
  show both figures is a product choice. A holder born before 1955 had to claim, which the
  engine does not model.
- **`aspa`, `ass` and `aeeh` are not in `STATE_TRANSFERS`** (D-186, D-189, D-191). That
  is to decide on a `make full`.
- **D-195's contradictory dwellings**, an owner's call: 89 foyers in a dwelling typed
  « famille monoparentale » whose reference answers « en couple ». Case T stays as it
  was, and a test pins the choice.
- **The upstream dossier** gains the openfisca-france defects these entries correct, the
  widowed parent's case T (D-193, D-197), the NaN tax of a `jeune_veuf` (D-197), the
  home-help increment of a case R dependant (D-198), and the RSA's at-charge test beside a
  child's AAH and the housing aid's strict 80 % (D-202).

## Verification, as it stands

* **Last logged full pass: `7cce463`, 2026-10-20 — PASS, 2 475 passed, 109 skipped,
  102 min 41 s**, on the owner's machine in a fresh clone, with the twelve Phase 9
  sources fetched on top of `make data` (D-231). The skips are data-absent skips; the
  Phase 9 tests that can skip there are the two CIR ones reading the Voies et moyens
  tome II. The two lines before it, `5b1ec10` and `05cc944` (D-204), had 116 skips; the
  `a9ea26f` one on 2026-09-25 had 3, on a machine holding every manifested file.
  Every line since the red `3101fff` one is green.
* **CI on `main`, run 36882194476 on `1e12460` — the full suite has still never
  finished on a runner.** `fast` passed (1 388 passed, 120 skipped, 221 deselected,
  11 min 23 s), and so did `perf` and `no-data-committed`. The full `pytest` job
  fetched, built and preflighted cleanly, then ran 73 min of tests until the
  runner received a shutdown signal (16:25:36 UTC), at about 63 % of the suite;
  the job is marked failed. **Up to that point it had printed only passes and
  skips — no test had failed or errored.** It is the second full job to die
  before its summary on a runner: `f1e5837`'s was SIGTERMed (D-160). The cause is
  not established. It is not the concurrency group, since `cancel-in-progress` is
  off on `main`, and not a timeout, since none is set. At the observed rate the
  suite needs about two hours there, against one locally.
* **GitHub Actions has been unavailable since 2026-10-15, 13:56 UTC** — no job gets a
  runner, the shape of an exhausted minutes quota (D-161) — and the owner decided to
  carry on without it (D-211). Until that changes, nothing below runs on its own: a PR
  is verified by its own targeted tests and by the owner's `make full`, which is now the
  only whole-suite check. Since 2026-10-16 the workflow runs on manual dispatch only
  (D-212), so a push no longer leaves a red cross that checked nothing; the comment
  under `on:` in `.github/workflows/test.yml` says how to restore the two triggers.
* **Automatic CI**, when restored — every PR and every push to `main` — runs `fast`,
  `perf` and `no-data-committed`; `fast` also carries the two engine-assumption scripts.
  **The full suite is out of automatic CI since 2026-10-02 (D-172)**, by the
  owner's decision: it runs only when the workflow is dispatched by hand, and
  `make full` is the full verification. `fast` was green on `aa869dd`: 1 388
  passed, 120 skipped, 10 min 57 s.
* **The raw-sources cache falls back on the previous one** when the manifest changes
  (D-205), so a PR that adds an entry outside the `tests` profile no longer contacts
  any source server. A restored file is kept only if it matches the manifest, and
  `donnees.elaguer_cache` drops what the manifest no longer sources. The first PR after
  it found no cache at all (D-208); the fallback first ran on D-209's PR, restoring the
  previous key and downloading nothing (D-210).
* **pytest is started two ways.** `make gate` and `make full` run
  `python -m pytest`, which puts the repo root on `sys.path`; CI and
  `make ci-local` run bare `pytest`, which does not. Five tests passed on the
  first route and failed on the second (D-171). The import guard now reports a
  `scripts` package import on either route, and `ci_local` is pinned to the
  workflow's command; the Makefile keeps its route.
* **`make ci-deps`** (≈ 15 s) and **`make ci-local`** replay CI in a throwaway
  worktree with a venv rebuilt from `pyproject.toml` alone (D-165). It is the
  check that `make full` cannot make, because `make full` runs in the owner's
  environment.

## The data chain (D-158 to D-160)

`impots data check | fetch | prepare`, `make data`, and a preflight that stops
`make full` in a second rather than an hour. The `tests` profile is declared
explicitly and checked against the readers' own constants by introspection
(D-160). Fetches go through the production manifest loader, refuse quarantined
entries, and keep a file only if its size **and** digest match. They trust OpenSSL's
default store completed by `certifi`'s, never replaced by it (D-232).

Two EconStor PDFs are re-stamped by the publisher on every request, so their
entries carry `normalization: pdf-stamp-v1` and are judged on a normalised digest
(D-159); the other 144 keep the raw comparison.

**146 files manifested: 70 sourced, 76 in D-028 quarantine.**

## Phase 8 — milestones

| | | |
|---|---|---|
| M0 | Recon (§1) | done |
| M1 | Debt closure (§3) | **done — closed 2026-09-25**, §6.1 graded (D-167, D-168) |
| M2 | Aggregate engine + produits (§2.2–2.3.1) | **partial, and frozen by instruction** — engine + 9 instruments (D-153); the anchor list verified and corrected (D-166, D-169) |
| M3 | Entreprises + personnes (§2.3.2–3) | **partial** — coverage claim (D-154); CIR and TH/TF gates blocked on files |
| M4 | Objective explorer (§4) | done — D-155 |
| M5 | Reindustrialization panel (§5) | done — D-156 |
| M6 | Consolidation | done — D-157; its « `make full` green, pass logged » item met since `f1e5837` |

**Thirty instruments, sixteen priced — 53 %.** The number that matters is the
other one: **six lines are classified without being priced**, and counting them
would inflate the claim to 73 %. `COVERAGE_INSTRUMENTS.md` renders both, every
figure computed and none typed; nothing has touched it since D-154.

### M1 — §6.1, and what its scope is

* **The SFA is built from its published components**, `F_ASS + ORADJ + K61 + KX +
  YA3` from Eurostat `gov_10dd_edpt3` (`eurostat_gov_10dd_edpt3_fr_sfa.json`,
  manifested). Both dataset codes first announced were wrong: `gov_10dd_sfa` is a
  404 and `gov_10dd_edpt1` has no stock-flow item (D-163).
* **Window 2021→2025, one vintage** (D-167). The notifications carrying 2019–2020
  are on another vintage: the 2019 adjustment changes sign between them.
* **Tolerance ±0.10 pt of GDP, pre-registered at `c6c5db4` before any residual.**
* **Result: five years in the band, largest residual +0.039 pt (2022)** (D-168).
  2025's +0.001 pt is two errors cancelling: an own-year error of −0.031 pt
  against the +0.031 pt carried from 2024. The vintage term, measured apart, is
  +0.031 pt too.
* **Out of scope, stated:** 2019 and 2020, so the +69 md€ Covid adjustment.
  Reopening them needs a current-vintage source that neither Eurostat nor the two
  notifications examined provide.
* **The snowball hinge** (D-170): the 2025 carry factor is 0.9998, so the backtest
  window never left the damping regime that §3 projects beyond. Two tests on
  constructed paths cover both sides of the hinge and the `r = g` limit.

### M2 — the anchors, verified rather than assumed

Of the nine receipts-scaling instruments, **three have a line in the Voies et
moyens tome I**: TSN (line 1430, 785 M€, exécution 2024), TTF (1797, 1 332 M€) and
TGAP (1756, 1 150 M€); TVA nette and the accises énergies are there as aggregates
(D-166). **Six are not, by construction**: taxe sur les salaires and forfait social
go to the Sécurité sociale, taxe d'apprentissage to France compétences, versement
mobilité, DMTO and TASCOM to local authorities.

The CCSS report (`ccss_mai2026_comptes_secu_resultats2025.pdf`) is **sourced**, not
quarantined (D-169, correcting D-166). It gives a usable net series for the forfait
social; the taxe sur les salaires and the tabacs and alcools accises sit in tables
that need a parse. That parse is M2 work, and M2 is frozen by instruction
(D-166, D-169). `docs/M2_ANCHORS.md` carries the corrected table and the revised
download list.

### What Phase 8 refuses, and where each refusal lives

* **A debt path without a named spending scenario** — `dette/path.py`.
* **A distributional output from an aggregate instrument** — `agregats/engine.py`.
* **A banded objective or constraint** — `explorer.py`.
* **A structural-transformation outcome** — `reindustrialisation.py`.
* **A receipts anchor from memory** — `agregats/anchors.py`. The euros live in a
  generated table, never in code.

## Blocked on downloads

| what | for | state |
|---|---|---|
| COICOP consumption split (R5) | TVA per-rate base | not manifested |
| CCTN / DGEC / DGDDI / OFDT volumes | the accises' bases | not manifested |
| **Eurostat `gov_10a_taxag`** | **M5's benchmark** | **not manifested** |
| GECIR / MESR publications | the CIR gate | not manifested |
| DGFiP / DGCL local-tax statements | versement mobilité, DMTO, TASCOM anchors | no candidate in the manifest (D-166) |
| `ccss_mai2026_comptes_secu_resultats2025.pdf` | taxe sur les salaires, tabacs, alcools | **sourced** — needs a table parse, M2 work |
| `rei_2025.zip` | TH RS / TF recon | sourced |

## Owner calls, on the record and not to be chased

* **The reviewer's verdict on Phase 8** is not in the review file, whose last
  addendum is 2026-09-17. Its recommendations reached the work — D-162 cites « A »
  (the PLF dry run first), D-166 cites « D » (the M2 anchor list), D-163 the SFA
  route — but nothing is appended.
* **The §2.4 coverage threshold.** §9 expects it in the decision log; it is in
  neither `M0_PHASE8.md` nor `DECISIONS.md`. Without it there is no universe, so
  `COVERAGE_INSTRUMENTS.md` counts **lines** and says so.
* **Skip versus fail for the data-dependent tests.** No longer a CI blocker: the
  chain fetches and builds what they read before the suite runs. Without the
  files, some still **fail** — `test_accuracy`, `test_top_tail` and
  `test_trajectoires` among them — each naming the command that produces its
  file; the population tests skip. Which
  of the two is right stays the owner's call.
* **`population/calibrate.py`, fenced to Phase 7 (§8).** A margin cell whose
  published target is **zero** is skipped by both `_apply_margin` and `_fit`, so it
  is never measured: a four-household rake with a zero target keeps 2.0 households
  there, converges, and D-150's own guard accepts it (D-157). Whether any published
  target is zero has not been checked.
* **ERFS documentation location** (D-135): left in the delivery with its digests
  recorded, rather than copied under `data/raw/`. Defensible either way; the
  reviewer's to rule.

## Armed and waiting

* **PLF 2027 — registered and graded (D-204).** Published 2026-10-01 (AN text 3210);
  the 33 fiscal articles triaged, 3 priceable (D-174, D-175). On 2026-10-14 the owner
  ran the full pass and the three registrations, one commit each (`be5b5f6`,
  `e449490`, `25b2a61`). The annex was then manifested and the cases graded: **art. 3
  within (−17,7 %), art. 15 within (−28,3 %), art. 2 outside (−30,3 % against 20 %)**.
  Art. 2's published figure is a first-year budget effect (2027 notices plus PAS),
  against our one income year; art. 15's grade rests on counting the 0,5 Md€ of shifted
  closings in 2028. Both are written up in D-204, with what remains. Since 2026-10-15
  `grade` refuses a comparator whose sign contradicts its amount (D-206). Art. 3 lands
  17,7 % above the annex although its tolerance declared only downward biases: the
  population puts the 400,4 Md€ of declared pensions on 12,24 M foyers, against 15,09 M
  beneficiaries of the 10 % abatement in the Voies et moyens, and the whole abatement
  costs 11 % too much against that independent line (D-207,
  `scripts/verify_pensions_art3.py`). The three leads D-207 named — retirees in
  institutions, the age rule for pensions, cohabiting couples in one foyer — are
  measured in D-209 (`scripts/verify_pensions_foyers.py`): together they bring the
  pension foyers to 12,83 M and take 3,7 % off what art. 3 removes, a quarter of the gap.
  The rest is the level (D-210, `scripts/verify_pensions_masse.py`): the target mixes
  374,4 Md€ of retirement pensions (boxes 1AS-1DS) with 26 Md€ of invalidity, alimony,
  foreign pensions, capital and annuities, all drawn onto retirees. Scaled to the
  retirement boxes, art. 3 lands at 1,119 Md€, +1,8 %. Since D-211 the population is
  calibrated on those boxes: on a 20 000-household sample the IR barème line moves from
  +11,0 % to +6,7 % of the DGFiP, and foyers imposés from −1,6 % to −4,5 %. The
  registered chiffrages keep their commit and their grades.
* **ERFS 2022 (FPR, lil-1696) — the interrupt ran, E3 is « nothing ».** E0 rails
  (D-134), E1 inventory (D-135), E2 validation table (D-137), and the two
  re-examination gates (D-141) are done. No recalibration is drawn; the E2 table
  goes to the reviewer. A3 is not measured, because it is the one level-sensitive
  axis and its deflation choice must be pre-registered. ERFS bytes and row-derived
  outputs never transit the cloud (addendum 2026-09-17). *The 2026-09-22 version
  of this document called ERFS « dormant »; it was not.*
* **L2, the take-up layer**: dormant. Both DREES non-recours files sit in D-026
  quarantine. Wakes on a sourced, manifested take-up file.

## Directions open — the owner picks

* **Lift M2's freeze**, and the anchors in hand become rows: TSN, TTF and TGAP from
  the Voies et moyens, the forfait social from the CCSS report. Then the CCSS table
  parse for three more, and the local-tax statements for the last three.
* **Finish M3** the day the files land: the CIR verdict and the TH/TF recon.
* **TVA per-rate and the accises' bases**, blocked on COICOP and the volume series.
* **§6.1 beyond 2021**, if a current-vintage source for 2019–2020 appears.
* **F1b's build: the RCM imputation.** Built (D-248), opt-in, and imputed by itself for
  a PFU reform, aged on the wage index after 2024 (D-249); the CDHR it reaches is a
  receipt since D-250. Left: the top-tail rake beside it, which needs capital and
  earnings raked apart.
* **F7 — succession/DMTG.** Gate only, never past it without the owner.
* **F8 — aggregate VAT.** Still waiting on Budget de Famille 2026 (~2027-28).
* **The CAF cross-check.** 30 minutes at a browser, owner-only. **No reCAPTCHA
  circumvention under any circumstances.**
* **The household calculator's open items**, each in its entry's « Ce qui reste »:
  - claiming the ASPA beside an AAH holder: both figures, and the claim owed by a holder
    born before 1955 (D-203);
  - `aspa`, `ass` and `aeeh` in `STATE_TRANSFERS`, on a `make full`;
  - a rented dwelling beside a child at the AAH or a person in case R, refused for now;
    a case R person's own incomes; a child of 20 or more at 50 to 79 % (D-202);
  - alternating residence's benefit side: the allocataire, the housing aid and the RSA
    (D-201);
  - case 7DG for a third-category invalidity pensioner without the card, whose category
    the format does not carry (D-196);
  - case L, for a parent who raised a now-adult child alone for five years, and the year
    of the death (D-197);
  - the N-3 RFR, which also keeps the 3.8 % CSG rate (CSS art. L. 136-8, III, 2°) and
    openfisca does not read (D-199);
  - the population's widowed parent, who keeps case T because the population carries no
    situation de famille (D-195).
* **The upstream dossier** and **all publication and deployment**: owner's,
  deferred. The input-hardening pass the reviewer made a precondition is done for
  strings, paths and reform JSON (D-173). What it leaves is the owner's, at deployment
  time: the open CORS policy (it is what lets `ui/index.html` open from disk),
  authentication, rate limiting, and a concurrency cap on `POST /population/simulate`.

## What the next session does if nobody says otherwise

1. **The PLF 2027 is graded** (D-204), the sign guard is in (D-206), art. 3's direction
   is explained (D-207), its candidate causes measured (D-209), the pension target
   decomposed (D-210) and the population recalibrated on the retirement boxes (D-211).
   The full pass is done: the owner's `make full` on `7cce463` covers D-210 and D-211
   (D-231). What it leaves: the reports regenerated on the owner's machine, the first
   since the pension target moved; the report's direction line, which counts signs; and
   art. 2's outside grade.
2. **Phase 9, M5** (`docs/PHASE9_SPEC.md` §6): the new channels one by one. Labour
   supply is done (D-220, C7, CSG on earnings only) and company creations opened as an
   illustrative index (D-221, C8, IS normal rate only); investment stays closed for the
   IS (D-221). R&D opened as an illustrative index (D-222, C9, CIR rates only), and the
   CIR is priced on the créance flow with its banner. Dividends (§6.5) stay closed. Every
   §6 channel has its verdict. M6 is under way: §7's indices (D-223), the explorer at a
   fixed θ (§8, D-224), §9.1's coherence and §9.2's preregistered containment (D-227),
   §9.4's worked example (D-228) and the guard sweep (D-229) are in, and M6's gate is
   met: the owner's `make full` on `7cce463` is green, and **Phase 9 is closed**
   (D-231). Left for C9: the take-up margin, new entrants, the carried-forward stock,
   and the CNEPI's 2021 evaluation (IPP report n° 33), not manifested. M1 to M4 are done (D-215 to D-219); M4 left
   the transfers and the IS closed. The two
   choices M3 left to the owner are made (D-230): both persistence scenarios side by
   side when none is named, and the `multiplier_by_instrument` row reopened, its bound
   kept as the project's choice. `impots predictif` carries behaviour and the loop (D-236). A full ten-year
   run is about an hour on the owner's machine, and takes `--theta`. Still open from M0: the HCFP note (its host
   refuses this container), and the AFT outstanding, which www.aft.gouv.fr
   refuses here too (403): the `marche` rate scenario needs it.
3. **Phase 10** (`docs/PHASE10_SPEC.md`): M1 to M4 are done (D-234 to D-238); its gate is
   the owner's `make full`. The ceiling is reclassed and replayed (D-239), and the 2026
   curve has its knobs (D-240), and the study is replayed with it (D-241, D-242): no
   cut of the curve lowers the debt, and what a targeted cut would give back is
   missing, said so. Left: a balance row for the targeted variant, or the jobs'
   receipts in the chain; the study on the annual path; other θ.
4. **Phase 11** (`docs/PHASE11_SPEC.md`, D-243): firms, startups and capital in the
   chain, on published ranges, international where France has none. M0 first: manifest
   and re-read Gechert and Heimberger (2022), the OECD's Hanappi, Millot and Turban
   (2023), Da Rin, Di Giacomo and Sembenelli (2011), the EC's DP 098 (2019), Trésor-Éco
   n° 97, the Bozio and Wasmer report (2024) and the IPP's PFU evaluation; fix each θ
   mapping before any pass. M0 is done (D-245): the IS's growth ramp and firm entry
   fixed, the IS loop and the investment index closed with their reasons, the
   self-financing of targeted cuts left to the owner. M1 is done (D-244): a firm reform
   in `/predictif/simulate` and the explorer. M2 is done (D-246): the IS's GDP effect as
   an index outside the debt path, the computed cross-check that refuses the elasticity
   loop, the aged firm view and the annual path by layer. M3 is done (D-247) and opens
   nothing: national entry is refused, the OECD's method missing France's composite EMTR
   for want of the tangible subgroups' allowances, and investment stays closed on
   reference values the paper does not print; C8 remains the entry index. The capital
   income is imputed (D-248). M4 is done (D-249): the PFU knob, read back, and the
   dividends' response C10 in the receipts; the wage shift it leaves out is the next
   number that could turn a PFU cut's answer. M5 is under way (D-256): the owner chose
   R5's range once C2 was corrected (D-255), C11 prices it, and the curve's replay with it
   is preregistered. M6 is
   done (D-250, D-251): the study on the wider menu. No IS cut lowers the debt; a PFU cut
   does under « tenu » at θ = ½, by a few hundredths of a point, on a sign the wage shift
   could turn. Its gate is the owner's `make full`. The wage shift is in C10 (D-252), and
   the PFU replayed with it turns that sign (D-253): no cut on the menu lowers the debt at
   θ = ½. The CVAE is priced on the annual path with a knob for its whole schedule, and
   the carry refuses it (D-254). The page's predictive panel does not send a firm reform yet. Then Phase 12, the past, and
   Phase 13, the online product.
5. **Otherwise, nothing new.** M2 is frozen, and the reviewer's verdicts on Phase 8
   and on the ERFS E2 table are pending. Maintenance per `docs/CHARTER.md`: pin
   bumps, vintage refreshes on the nine-source calendar, full passes, and each
   January a row in `engine.corrections.PENSION_INVALIDITE_MINIMUM` (D-190).

`docs/OPUS_HANDOFF_DATA_CHAIN.md` is a completed brief, kept for its record: its
mission closed with D-159 and D-160.

## Standing, unchanged

ERFS microdata is not redistributable; only aggregates leave it. `data/` is
committed by allowlist only. Do not fabricate the numbers. Calibration inputs via
files only (D-026); a figure from memory is a recollection. Banded or absent,
never confidently wrong. The review file's addenda, all of them, including the
five standing questions and « reality beats every spec, on the record ».
