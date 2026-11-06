# Future scope and open issues

Ordered by value. Section 1 is the main piece of future work; section 2 lists problems found in the existing material; section 3 covers the repository itself.

## 1. Re-implement the model in Python (first priority)
Today the model exists only as reports, hand calculations and a script hosted on an online IDE that is not in this folder. A reproducible implementation would let anyone rerun and challenge the numbers.

1. **Recover the original script.** CP5 links to it (online IDE). Save a copy into the repo as the reference implementation before rewriting anything.
2. **Weather input.** Parse `data/weather_file_nsrdb.csv` (header block, then Hour, GHI, DHI, Temperature, Wind Speed for 8760 hours). First settle the Jodhpur-versus-IIT Bombay question (see Flow.md §4) by getting the correct NSRDB/SAM file for 19.15° N, 72.95° E.
3. **Solar geometry and radiation.** Implement the equations listed in CP5: declination, equation of time, local apparent time, hour angle, zenith and incidence angles, the beam/diffuse/reflected factors and the HDKR tilted-surface model; derive DNI from GHI and DHI.
4. **Design DNI.** Hourly means → monthly hourly means → daily energy per month → yearly average, with and without the 200 W/m² threshold.
5. **Dish model.** Optical efficiency (cosine, reflectivity, absorptivity), receiver convective and radiative losses, overall efficiency; make every assumption an explicit parameter.
6. **Load and sizing.** Per-dish cooking loads, safety factor, pot efficiency, number of dishes.
7. **Annual performance.** Replace the single-day efficiency (computed for 17 May, 12:30) with an hour-by-hour simulation over the year, and compare against the demand profile.
8. **Techno-economics.** NPV, benefit–cost ratio, IRR and payback with sensitivity to dish cost, LPG price, discount rate and LPG price escalation.
9. **Validation.** Reproduce the reports' numbers first (efficiencies 0.607 / 0.868, 14 dishes, SPP, ROI, IRR), then compare with a SAM run.
10. **Layout when code exists:** a `scheffler_model/` package, `tests/` with the reports' numbers as regression targets, a CLI, and `docs/agent/Architecture.md`, `Bug.md` and `Feature.md` as the protocol requires once there is software.

## 2. Issues in the existing material
See [`docs/agent/Flow.md`](docs/agent/Flow.md) §4 for details. In short:
- Weather-file header does not match the stated site.
- Reflectivity 0.9 in the text versus 0.92 in the calculation; receiver efficiency 0.8626 versus 0.8687; an unlabelled factor 7 in the sizing formula.
- 11.65 m² (sizing) versus 16 m² (energy and cost) per dish.
- CP5 NPV formula line shows stale CP4 numbers; the 56 lakh total appears to omit the retrofit allowance.
- CP4 and CP5 give different CO₂ savings (57.06 t versus 41.5 t) and fuel-saving assumptions without an explanation of the change.
- No thermal storage; the system covers daytime cooking only.

## 3. Technical extensions of the study
- Add **thermal energy storage** (steam accumulator or other) and size it for evening/morning meals.
- Hybrid operation with the existing LPG supply; control strategy for cloudy days.
- Land/roof area and shading layout for 14 dishes of 16 m².
- Supplier quotes instead of per-m² cost assumptions; financing options.
- Compare with other technologies covered in the course (parabolic trough, linear Fresnel, CPC) for the same load.

## 4. Repository housekeeping
- Obtain the group's own CP2 and CP3 reports (they are not in the folder) and add them under `reports/`.
- Decide with the co-authors whether names and roll numbers in the reports may be published before making the repository public.
- Add a LICENSE and an academic-integrity note appropriate to the course.
- Optionally export the reports to PDF so they render on GitHub (the CP5 report is a .docx).
- Keep `docs/agent/Handover.md` updated at the end of each session.
