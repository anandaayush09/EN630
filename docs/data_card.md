# Data card

Three weather datasets are in the repository: two typical-year tables of 8760 rows and a 19-year hourly series. Loading and validation code: [`../src/en630/weather.py`](../src/en630/weather.py).

## 1. `data/pvgis_tmy_iitb.csv` (used going forward)

| Item | Value |
|------|-------|
| Source | PVGIS typical meteorological year (TMY), European Commission Joint Research Centre |
| Radiation / meteo database | PVGIS-ERA5 / ERA5, years 2005 to 2023 |
| Site | IIT Bombay, Mumbai: 19.15 °N, 72.95 °E (as stated in the performance report and the final report). PVGIS reports a site elevation of 5 m and applies a terrain-horizon correction |
| Retrieved | 2026-11-12, through `en630.weather.fetch_pvgis_tmy` (only the coordinates are sent) |
| Columns | `time_utc`, `ghi`, `dhi`, `dni` (W/m²), `temp_air` (°C), `wind_speed` (m/s), `relative_humidity` (%), `pressure` (Pa) |
| Time index | UTC, hourly. PVGIS builds a TMY from twelve real months, each from a different year, and relabels them to 1990. Each stamp is treated as the **centre** of its hour (see below) |
| Provenance record | `data/pvgis_tmy_iitb.meta.json` lists the source year chosen for every month |
| Terms of use | Data are provided by the European Commission's PVGIS service. Check the current PVGIS terms before reuse and cite the service |
| Validation | Passes every rule in `weather.validate` (row count, hourly spacing, bounds, diffuse no larger than global, no night-time sun, clear-sky index). The DNI artefact check is separate (see Limits) |

**Why it replaces the course file:** it is for the site the reports describe and it includes DNI. A closure check (`GHI` against `DHI + DNI x cos z`) gives a mean residual of -0.2 W/m² over 3816 daytime hours and no hour off by more than 50 W/m² (notebook `01`, section 8), so the three components are mutually consistent. That test is blind to the sunrise artefact below, because the error cancels in it.

**Limits:**
- **Impossible beam values at sunrise.** 50 winter hours (sun 3 to 6° up) have DNI between 1050 and 1271 W/m². `weather.dni_artefact_mask` flags hours whose DNI exceeds 0.75 of the extraterrestrial beam and `clean_dni` sets them to zero; the CSV itself is left as downloaded. Analyses use the cleaned series (annual DNI 2.113 to 2.052 MWh/m²).
- It is a **modelled** series (reanalysis plus satellite products), not a ground measurement. Cloud-dependent beam irradiance, especially in the monsoon, can be biased; no ground data was available to check.
- A TMY represents a typical year. It says nothing about year-to-year variability; the multi-year series is a planned step.
- The centre-of-hour reading of the timestamps is an inference from the data (sunrise and sunset hours, no night-time irradiance), not something the service states in the file.

## 2. `data/weather_file_nsrdb.csv` (course file, kept for comparison)

| Item | Value |
|------|-------|
| Source | NSRDB-format file used in the course. The header says: NSRDB location 20013, **Jodhpur, Rajasthan**, 26.35 °N, 73.05 °E, time zone +5.5 |
| Columns | `Hour` (1 to 8760), `GHI`, `DHI` (W/m²), `Temperature` (°C), `Wind Speed` (m/s). **No DNI column**, although the header declares DNI units |
| Time index | Read as local standard time, label `h` meaning the interval `[h-1, h)`. This is an assumption: the file does not say. The first non-zero GHI of the year is in label 9 and the last of the day in label 18 |
| Status | Content untouched. Internally valid, but the header does not match the study site (see appendix A of [`report.md`](report.md)) |

**Limits:** location unclear; no DNI, so a closure-derived DNI (`dni_from_ghi_dhi`) is used when a beam value is needed. That derivation is a crude baseline.

## Comparison in one line
Annual GHI is 2083 kWh/m² in the course file and 1871 kWh/m² in the PVGIS TMY; annual DHI is 814 against 536 kWh/m². The two series differ most in June to September (notebook `01`, figures in [`figures/`](figures)).

## 3. `data/pvgis_dni_2005_2023_iitb.csv.gz` (year-to-year variability)

| Item | Value |
|------|-------|
| Source | PVGIS-ERA5 hourly series, 2005 to 2023, same site as the typical year |
| Columns | `time_utc`, `dni` (W/m², as downloaded), `temp_air` (°C); 29 February removed so each year has 8760 hours |
| How DNI is obtained | PVGIS does not return beam normal irradiance in its hourly series; for a two-axis tracking surface the "direct" irradiance on the plane is the beam normal irradiance, so that mode was requested (`weather.fetch_pvgis_multiyear`) |
| Time index | UTC, stamps at hh:30, the centre of the hour, as for the typical year |
| Retrieved | 2026-11-12; a re-download gives the same values |
| Size | about 1.1 MB compressed (166,440 rows) |
| Limits | Same modelled-DNI caveats as the typical year, including the sunrise artefact (the same cleaning is applied inside the analysis, not to the file). Annual beam energy of the 19 years: 1876 to 2106 kWh/m² before cleaning |

