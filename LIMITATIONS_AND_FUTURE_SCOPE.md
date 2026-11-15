# Limitations and future scope

## Limitations today

- **The cost of the steam store is a placeholder.** I used INR 1000 per MJ (range 500 to 2000) from a rough estimate of a pressurised hot-water tank. I have no quotation. The positive economic case needs a store, so it depends on this number.
- **I assumed when meals are cooked.** The final report gives the energy of each meal but not the hours. Without a store this decides the result: the solar share is 34 % with my timetable and 56 % if all cooking were done between 10:00 and 15:00. With a store it hardly matters.
- **Store losses are assumptions.** Efficiencies of 0.95 in and out and a loss of 0.5 % of the stored heat per hour.
- **The weather is modelled, not measured.** PVGIS beam sunlight comes from a model. I could not compare it with ground data, and the monsoon months are where I would trust it least. 66 low-sun hours with very high beam values pass my cleaning rule and I could not tell whether they are real.
- **Deriving beam sunlight from global sunlight is poor.** Two standard models recover only 1637 and 1507 kWh/m2 of the 2052 in the PVGIS series. Anything built on a derived value carries a spread of about 10 % or more.
- **The dish is an idealised sun-following mirror.** The changing mirror shape of a real Scheffler dish, and its receiver, are not modelled.
- **The LPG saving is counted the way the final report counts it** (steam heat over 654.6 MJ per cylinder and a stove efficiency of 0.6). That ignores the 0.72 pot efficiency used on the steam side.
- **The best design is best for one set of inputs.** I did not search for a design that is robust across all the uncertain inputs.
- **Some things stay unexplained:** the hour angle printed in the final report, the 20 MJ snack-milk line in its load table, the origin of its 665 W/m2 design value, and the 194.6 MWh annual heat in the performance report, which my simulation (173 MWh) does not reproduce.
- **Two submissions are missing.** The two between the proposal and the performance report are not in the repository.

## What I would do with more data

| Data | What it would let me do |
|------|-------------------------|
| Measured beam irradiance for Mumbai (a ground station, or an independent satellite product) | Measure the bias of PVGIS, especially from June to September, and decide whether the low-sun hours are real |
| A quotation, or a price list, for a steam accumulator of 750 to 1500 MJ | Replace the placeholder store cost; this is the most valuable single input |
| The mess timetable and a log of gas use | Replace the assumed meal hours and the 365 identical days with the real demand, including holidays |
| Actual cylinder prices over the last years | Replace the 0 to 8 % price-rise range with a history |
| The two missing submissions | Settle the open questions about the final report |

## What I could not do yet, but would like to

- **Model a real Scheffler dish:** mirror shape, intercept loss and a receiver loss that follows the water temperature.
- **Choose a design that is robust:** best expected NPV, or best tenth percentile, instead of best at one set of inputs.
- **Forecast the sun to schedule LPG backup:** compare simple baselines (yesterday, the monthly average) with a learned model on the 19-year series.
- **Run a larger sensitivity study.** 64 base samples give wide confidence intervals; more samples would separate the lower-ranked inputs.
- **Cross-check with SAM or PySAM** for the same site and load, and compare with other collector types (parabolic trough, linear Fresnel).
- **Work out the layout:** roof or land area and shading for the chosen number of dishes, and hybrid operation with the existing LPG supply on cloudy days.

## Housekeeping

- Confirm that the final report included here is the group's final version, and that the co-authors are happy for their names to appear in the reports.
