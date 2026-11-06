# Solar thermal cooking for IIT Bombay Hostel-17

Course project work for **EN 630 — Utilisation of Solar Thermal Energy** (Department of Energy Science and Engineering, IIT Bombay, 2023-2 semester). Group 05 studied whether Scheffler-dish solar steam generation can replace part of the LPG used to cook for the roughly 1300 students of Hostel-17.

Author of this repository: Aayush M Anand (Group 05). The other authors are listed in the reports.

> This repository contains reports, figures and one weather data file. It has **no executable code**: the calculations were done by hand/Excel, with SAM and with a Python script that is hosted online and is not in this folder (see [`FUTURE_SCOPE.md`](FUTURE_SCOPE.md)).

## The problem in brief
According to the reports, the hostel mess uses 9 LPG cylinders (14.2 kg each) a day, about **5900 MJ/day**, for cooking. The group sized a field of Scheffler dishes (single-axis tracking, water/steam at 150–200 °C, 3–7 bar) to supply the steam-cookable part of that load, then assessed energy, CO₂ and cost savings.

## Headline results (as stated in the final report, CP5)
| Quantity | Value |
|----------|-------|
| Steam heat to be supplied | 1435.89 MJ/day |
| Design DNI | 665 W/m² |
| Optical / receiver / overall efficiency | 0.607 / 0.868 / 0.528 |
| Reflector aperture per dish used for sizing | 11.65 m² |
| Number of dishes | 14 |
| Simple payback / ROI | 4.269 years / 23.42 % |
| Benefit–cost ratio / IRR / NPV | 1.556 / 20.116 % / ₹3,591,518 |
| CO₂ avoided | 41.5 t per year |
| Main limitation | No thermal storage, so no cooking at night or in low-sun periods |

The earlier CP4 report gives different economics (different cost and LPG-price assumptions); both sets are compared in [`docs/agent/Flow.md`](docs/agent/Flow.md), together with several inconsistencies found while reading the reports. **Treat the numbers as the group's coursework estimates, not verified design values.**

## Course projects
| CP | Content | Document in this repo |
|----|---------|-----------------------|
| CP1 | Application, demand, choice of Scheffler dish, system description | [`reports/CP1_G05.pdf`](reports/CP1_G05.pdf) |
| CP2–CP3 | Plant model and sizing: radiation model, DNI, efficiencies, number of dishes (inferred from the wording of CP4/CP5) | Own-group reports not in the folder; only [`reports/figures/cp2_screenshot.png`](reports/figures/cp2_screenshot.png) |
| CP4 | Annual performance and techno-economics | [`reports/CP4_G05.pdf`](reports/CP4_G05.pdf), [`reports/CP4_G05_presentation.pptx`](reports/CP4_G05_presentation.pptx) |
| CP5 | Final consolidated report | [`reports/CP5_final_report.docx`](reports/CP5_final_report.docx) |

System schematic: [`reports/figures/system_schematic.png`](reports/figures/system_schematic.png).

## Repository map
```
README.md            this file
FUTURE_SCOPE.md      open issues and future work (starts with a Python re-implementation)
CLAUDE.md, AGENTS.md pointers for AI coding agents
data/                weather_file_nsrdb.csv  (hourly GHI, DHI, temperature, wind; 8760 rows)
reports/             CP1, CP4 (+ presentation), CP5 final report, figures
docs/agent/          workflow and engineering documentation (Flow, Decisions, Handover, ...)
```
Not tracked in git (listed in `.gitignore`, kept on the author's PC): `drafts/` (earlier versions of the reports), `references/` (papers), `course-material/` (instructor slides, tutorials, textbook), `_review/` (files set aside for review: another group's reports, the SAM installer, lock/temp files).

## Data note
`data/weather_file_nsrdb.csv` is an NSRDB-format file whose header names **Jodhpur, Rajasthan (26.35° N, 73.05° E)**, while the reports describe the data as being for IIT Bombay (19.15° N, 72.95° E). Please resolve this before relying on the file; details in [`docs/agent/Flow.md`](docs/agent/Flow.md) §4.

## Where to start
- Methodology flow, step table and report-to-report comparison: [`docs/agent/Flow.md`](docs/agent/Flow.md)
- Current status and next steps: [`docs/agent/Handover.md`](docs/agent/Handover.md)
- Why files are organised this way: [`docs/agent/Decisions.md`](docs/agent/Decisions.md)
