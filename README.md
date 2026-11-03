# Predicting major metro service interruptions

Toboggan Labs technical challenge, using STM's open data on metro incidents (January 2019 to
September 2025) and planned metro kilometres (January 2019 to September 2023).

## Summary

- **What to predict.** Not "will this incident be major?" at the moment it is reported, but
  **"this train delay has lasted 5 minutes: will it reach 30 minutes?"** How long a delay has
  lasted is the strongest signal the control room has in real time; 5 and 30 minutes are STM's own
  thresholds (its definition of an interruption, and its longest duration category); and when the
  alert is right, at least 25 minutes of disruption are still to come, so there is time to act.
- **How well it works.** On 2024 to 2025, a logistic regression ranks these delays 3.6 times
  better than chance (PR-AUC 0.299 against a base rate of 0.084) and clearly better than a rule
  based on the symptom alone. But it falls short of the success criterion: with at least 1 alert
  in 3 right, it catches 34% of the 30-minute interruptions, against a bar of 50%. For delays of
  15 minutes or more it just meets the bar (52%). It can support the control room's judgment, not
  replace it.
- **The obvious framing does not work.** Predicting 10-minute delays at the moment an incident is
  reported catches only 14% under the same bar.
- **Simple triggers do much of the work.** About half of the fire, smoke or odour incidents still
  delaying service at minute 5 reach 30 minutes, and so do about half of all delays still running
  at minute 15.
- **Service volume does not explain the trend.** Interruptions per million planned km were stable
  from 2019 to 2022 (9.5 to 10.3), then rose to 13.0 in 2023, while planned km fell. The data cannot
  say whether that is a drop in reliability or a change in recording. Per km, the green and blue
  lines have about 50% more interruptions than the orange line.
- **The largest gap is in the data on escalation itself.** The only response recorded is calling
  the metro emergency team, without a time. So no model built on this data can show that
  escalating earlier reduces disruption. Recording every escalation, and when it happened, is the
  first recommendation.

## Repository and how to run

| File | Contents |
|---|---|
| [`clean_data.py`](clean_data.py) | Reads the two raw files, cleans them and writes `data/incidents_clean.csv` and `data/planned_km_clean.csv`. Every cleaning decision is documented in [Data dictionary and cleaning](#data-dictionary-and-cleaning) below |
| [`modelling.ipynb`](modelling.ipynb) | The analysis: target, features, validation, models, robustness checks, reliability per km and conclusions. Saved with its outputs, so it can be read without running it |
| [`EDA.ipynb`](EDA.ipynb) | First look at the raw incidents file with a profiling report ([`incident_data_report.html`](incident_data_report.html)) |
| [`requirements.txt`](requirements.txt) | Package versions (Python 3.14) |

To run the analysis:

1. Install the packages: `python -m venv .venv`, `source .venv/bin/activate`,
   `pip install -r requirements.txt`.
2. Download the two datasets from the Ville de Montréal open data portal
   ([incidents](https://donnees.montreal.ca/dataset/incidents-du-reseau-du-metro),
   [planned km](https://donnees.montreal.ca/en/dataset/stm-kilometrage-metro-des-periodes-de-service))
   into a folder named `STM challenge Data Scientist/` at the root of the repository, as
   `Incidents métro_20260707.xls` and `Kilométrage métro planifé_20260707.xls`. Despite the `.xls`
   extension, both are text (CSV) files. This analysis uses the files downloaded on 2026-07-07; the
   incidents file is updated every month, so a newer download will give slightly different counts.
3. Run `python clean_data.py` to write the cleaned files, or run
   [`modelling.ipynb`](modelling.ipynb) from top to bottom: it cleans the raw files itself, through
   `clean_incidents()` and `clean_planned_km()`.

**Use of AI.** The code, the notebook and this README were produced with Claude (Anthropic's AI
assistant, used through Claude Code), working with me through each decision. Every number comes
from running the code on the raw files.

## Analytical strategy

### Target

**Train incidents only.** The documentation says station incidents do not affect metro service, so
they cannot be service interruptions.

**Why not predict escalation itself?** Escalation is what STM wants to improve, but it is not
recorded. The only response in the data, calling the metro emergency team, is a specialised
response: among delays of 30 minutes or more, it was called for 84% of those with a rolling-stock
symptom but only 13% of those with fire or smoke. Predicting it would reproduce current practice,
not improve on it. So the target is what escalation is meant to prevent, a long interruption,
predicted while there is still time to act.

The notebook tries two framings, in order:

| | Part 1 | Part 2 (recommended) |
|---|---|---|
| Question | When a train incident is reported, will the delay reach 10 minutes? | When a train delay has lasted 5 minutes, will it reach 30 minutes? |
| Population | All train incidents | Train delays that reached 5 minutes (STM's definition of an interruption) |
| Major (test years) | 7.7% (625 of 8,109) | 8.4% (156 of 1,857) |
| Disruption still to come when a correct alert fires | At least 10 minutes | At least 25 minutes |

The target uses STM's own duration category (`Incident en minutes`) rather than our calculation
from the start and end times. The two agree for about 98% of train incidents.

### Features

Only information known when the prediction is made: the symptom (assigned at the moment of the
incident, per the documentation), the station, the line and type of location, the hour of the
service day, the weekday and month, the emergency-brake and door flags, and whether a train car or
run number is recorded.

Columns that look useful but are not available in time are left out:

- the primary and secondary causes and the type of rolling stock blamed, which are decided after
  analysis, sometimes weeks later;
- calling the metro emergency team, which is itself a response;
- the traction power cut, evacuation and material damage flags, because when they are set is not
  documented. Adding them roughly doubles PR-AUC, a sign that they largely describe the response
  to a long incident.

### Validation

- **Split by time:** the models are fit on 2019 to 2023 (21,057 train incidents) and evaluated on
  January 2024 to September 2025 (8,109). This mimics real use: trained on the past, applied to the
  future. A random split would let the model learn from incidents that happen after the ones it is
  tested on.
- **Model choice on a validation year:** the two models are compared on 2023 (fit on 2019 to
  2022), so the test years are not used to choose between them.
- **Bootstrap intervals** for the differences between methods, resampling the same test incidents
  for both methods.

### Success metrics

- **PR-AUC**, always read against the base rate (a random ranking scores the base rate). Major
  interruptions are rare, so accuracy is meaningless. ROC-AUC is reported for reference.
- **Success criterion, set before seeing the results:** an alert threshold that catches at least
  half of the major interruptions while at least 1 alert in 3 is right. Below that, the control
  room would either miss most major interruptions or learn to ignore the alerts. The 50% and 1-in-3
  levels are an operational assumption to discuss with STM.
- **Alert tables** (if the control room escalated the riskiest X%, how many major incidents would
  it catch?) and a **calibration** check (can the probabilities be read as probabilities?).
- **Two baselines:** the base rate, and a symptom rule that gives each incident its symptom's past
  rate of major delays. It is what a controller could do without a model.

### Models

Logistic regression is the main model: simple and interpretable. Gradient
boosting is fit as a check that a more flexible model would not do much better; it does not.
Neither model is tuned.

### Alternatives considered

- **A survival model of delay duration**, giving the risk of reaching 30 minutes at *any* elapsed
  time, not just at minute 5. Part 2 is one slice of it; this is the natural next step.
- **Forecasting the number of incidents per line and day.** That answers a planning question, not
  the escalation question, so it was not pursued.
- **Using every column as a feature.** Rejected: it gives much better scores, but with information
  that is not available when the decision has to be made.

## Findings

Test years (January 2024 to September 2025):

| | Part 1: at report, 10+ minutes | Part 2: at minute 5, 30+ minutes |
|---|---|---|
| Base rate | 0.077 | 0.084 |
| PR-AUC, symptom rule | 0.118 | 0.213 |
| PR-AUC, logistic regression | **0.262** (3.4 times the base rate) | **0.299** (3.6 times) |
| PR-AUC, gradient boosting | 0.267 | 0.264 |
| Major incidents caught with at least 1 alert in 3 right (bar: 50%) | 14% (244 alerts, about 12 a month) | 34% (154 alerts, about 7 a month) |

- **Part 1 finds real signal but cannot be acted on.** Logistic regression clearly beats the
  symptom rule (bootstrap interval for the PR-AUC difference: 0.12 to 0.17), but it is far from
  the bar. And its alerts fire when the delay has just started: in the training years, 46% of
  10-minute delays were over before 15 minutes, often too soon for a response to make a difference.
- **Elapsed time does most of the work.** In the training years, 1.7% of train incidents reach
  30 minutes; among delays that have lasted 5 minutes, 8.1%; 10 minutes, 26%; 15 minutes, 48%.
- **The model adds to the symptom in Part 2** (PR-AUC difference 0.05 to 0.13). Fire, smoke or
  odour still delaying service at minute 5 is the clearest single signal: 51% of these incidents
  reached 30 minutes in the test years (40 of 79), a quarter of all 30-minute interruptions. The
  model already puts 78 of these 79 incidents in its riskiest 10%.
- **With a 15-minute target the model just meets the bar:** it catches 52% of the delays that
  reach 15 minutes with 1 alert in 3 right (530 alerts, about 25 a month). This is partly because
  15-minute delays are more than twice as common.
- **The probabilities are reasonably calibrated:** 9.0% predicted on average against 8.4%
  observed. The highest-risk group is overestimated (about 27% predicted against 20% observed).
- **Robustness:** Part 2 does not depend on the features whose timing is assumed (PR-AUC 0.291 to
  0.296 when each group is removed). On the 2023 validation year, the two models are close
  (Part 2: 0.258 for logistic regression against 0.271 for gradient boosting), so the simpler one
  is kept.
- **The emergency team is a specialised response, not escalation in general.** It was called for
  479 incidents, only 17% of all 10-minute delays.
- **Reliability per km** (January to September of each year, so that years compare fairly):

  | | 2019 | 2020 | 2021 | 2022 | 2023 |
  |---|---|---|---|---|---|
  | Interruptions of 5+ minutes per million planned km | 9.72 | 9.53 | 9.56 | 10.31 | 12.98 |
  | Interruptions of 30+ minutes per million planned km | 0.60 | 0.74 | 0.76 | 0.90 | 0.75 |

  In 2023, planned km was 8% below 2019, but interruptions were 23% above. Interruptions of
  30 minutes or more are too few (40 to 57 a year) to separate a trend from year-to-year
  variation. By line (2019 to September 2023), per million km: green 12.8, blue 12.1, yellow 9.1,
  orange 8.2. The green and orange lines have similar raw counts, but the orange line runs about a
  third more service.

## Recommendations

### How STM should measure reliability

- Count **interruptions of 5 minutes or more per million km actually run**, by line and month.
  Raw counts mislead when comparing lines or years.
- Track **interruptions of 30 minutes or more separately, with their uncertainty**: they are rare,
  so year-to-year changes are hard to tell from noise.
- Keep **station incidents separate**: they do not affect service.
- **Check whether recording changed in 2023**, before reading the 2023 rise as a drop in
  reliability.

### How to prioritise action

**VP Operations (earlier escalation, reduced disruption).**

- Use **elapsed time as the main trigger**, sharpened by the symptom and the model. At minute 5,
  escalate the model's riskiest 10% of delays (about 9 a month in the test years), which already
  includes nearly all fire, smoke or odour incidents.
- Without a model: escalate every fire, smoke or odour incident still delaying service at
  minute 5, and expect about half of the delays still running at minute 15 to reach 30 minutes.
- **Record every escalation and its time**, so that the effect of escalating earlier can be
  measured. Today it cannot be.

**CFO (prioritisation, confidence, financial burden).**

- **Prioritise lines by rate, not count:** per million km, the green and blue lines have about 50%
  more interruptions than the orange line, for both 5- and 30-minute interruptions.
- **Confidence:** the model is better than a simple rule but misses the success bar, and the test
  years contain only 156 interruptions of 30 minutes or more. Its probabilities are reasonably
  calibrated and can be used to rank incidents; the top scores overstate the risk somewhat.
- The **financial burden cannot be measured** with this data: there is no cost data and no count
  of affected riders. Delay minutes could stand in for impact, with stated assumptions.

**Public Affairs and Safety (user impact, communication risk, rare severe events).**

- **Fire, smoke or odour is the clearest early warning** of a long interruption, and a safety issue
  in itself: the natural trigger for early public communication.
- The model is better suited to responses worth triggering for a 15-minute delay, such as informing
  the public, than to those only worth triggering for 30 minutes or more.
- Interruptions of 30 minutes or more are rare (1.7% of train incidents in the training years,
  about 7 a month in the test years), so every estimate about them is uncertain.
- User impact cannot be measured without ridership by line and time of day.

### How to improve data collection

The full list is in [Recommended data improvements](#recommended-data-improvements). The most
important:

1. **Record every escalation**: which team or action, and when.
2. **Record the full timeline** of train incidents (start, detection, escalation, service
   resumed), not only the delay to customers.
3. **Record when each response flag is set** (traction power cut, evacuation, damage), so that the
   ones known early can be used.
4. **Publish actual km, ridership and cost data** for the same period as the incidents.

## Assumptions

- **Prediction time.** For train incidents, the recorded start is the start of the delay to
  customers, so "at report time" means minute 0 of the delay, and Part 2 predicts 5 minutes after
  it.
- **Features known in time.** The symptom is assigned at the moment of the incident (documented).
  The location, line, flags and whether a car or run number is recorded are assumed to be known by
  the prediction time (not documented). Part 2 does not depend on this assumption (section 4.2 of
  the notebook).
- **The success bar** (50% caught, 1 alert in 3 right) is an operational choice, not something the
  data provides.
- **STM's duration category is the truth** for the target.
- **The service day runs from 2 a.m. to 2 a.m.** This is inferred from the data, not documented
  (see [Data dictionary and cleaning](#data-dictionary-and-cleaning)).
- **Undocumented codes are interpreted from the data**, for example `Non affecté` in `Ligne` as
  "not on a line" (see the data dictionary).
- **The planned km file's dates are service days**, like the incidents.

## Limitations

- **Escalation is not recorded**, and every outcome reflects STM's current response. The data
  cannot say what would happen under a different escalation policy.
- **Few severe events:** 156 interruptions of 30 minutes or more in the test years, so all figures
  carry real uncertainty.
- **The prediction time is approximate:** the data has no time for detection or escalation.
- **Neither model was tuned.** Tuning on the validation year could improve the results slightly.
- **Change over time:** the training years include the COVID period (2020 to 2021), the latest
  months of incidents may still be revised, and 2025 is partial. The 2023 rise in interruptions per km
  is unexplained.
- **Data quality:** the duration category disagrees with the start and end times for about 2% of
  train incidents; several fields contradict each other or are not documented (see the data
  dictionary).
- **Rates per km use planned, not actual, km**, and stop in September 2023, so 2024 and 2025 cannot
  be turned into rates.
- **No ridership or cost data**, so user impact and the financial burden cannot be measured.

## Data dictionary and cleaning

The cleaning is done in [`clean_data.py`](clean_data.py). The tables below compare, for every column:
what the official documentation says, which codes it says mark missing values, which codes actually
mark missing values in the data, and what the cleaning does. Counts are from the raw files
(45,561 incidents).

"—" means the documentation does not say anything. "None" means the column has no missing-value code.

In the tables, "→ missing" means the value is replaced with pandas' missing marker:
`NaN` (`np.nan`) in text columns, and `<NA>` (`pd.NA`) in whole-number and true/false columns
(`run_number`, `vehicle`, `number_of_lines`, `number_of_doors`, `bucket_matches_times`), because
those column types cannot hold `NaN`. Both are empty cells in the CSV. Test for them with
`pd.isna()`, not `== None`. `0` in the yes/no flag columns (`CAT`, `KFS`...) means "no", not missing.

**Service day.** STM records incidents by *service day*: trips after midnight belong to the previous
day, so times can go past 24:00 (e.g. `25:10:00` = 1:10 a.m. the next morning). The year, month,
day-of-month and weekday columns describe the service day, and so does the incident number
(`T06122317` = service day 06-12-23, incident 17). This convention is not documented.

The cleaned data keeps both kinds of day:

| Column | Day it describes | Example: `25:10` on service day 2022-01-01 |
|---|---|---|
| `service_date`, `year`, `month`, `weekday` | Service day | 2022-01-01 (Saturday) |
| `start_service_hour` | Hour of the service day | 25 |
| `start_datetime`, `end_datetime` | Real clock time | 2022-01-02 01:10 |

The date part of `start_datetime` equals the original `Jour calendaire` for every incident.
An incident belongs to the service day in which it *starts*. In this data, start times run from
`02:00` to `25:59` (2 a.m. to 2 a.m. the next morning). End times keep counting on the same
service-day clock, so an incident that starts at 1:30 a.m. (`25:30`) and ends at 5 a.m. is written
`29:00`: raw end times go up to 29:xx. The 2 a.m. boundary is inferred from the data, not documented.

Use the service day for daily counts and weekday effects, and
`start_service_hour` for time of day: unlike the clock hour, it keeps late-night service together
(23:50 → 23, 00:10 → 24).

### Metro incidents

| Raw column → clean column | Definition (documentation) | Missing-value code (documentation) | Missing-value code in the data (rows) | Other findings in the data | Cleaning |
|---|---|---|---|---|---|
| `Numero d'incident` → `incident_id` | Unique number identifying each incident (numeric) | — | None | All unique. Not numeric: T or S, then the service day as DDMMYY, then a sequence number (e.g. `T01082509` = train, 01-08-25, incident 09). The date matches the service date for every incident | Kept as text |
| `Type d'incident` → `incident_type` | T = train, S = station | — | None | 29,167 train, 16,394 station | None |
| `Cause primaire` → `primary_cause` | Primary cause, decided after analysis of the incident | Left empty for station incidents (no code given). Train analysis can take more than 30 days | `Autres`: all 16,394 station incidents. `#N/A`: 482 train incidents, spread over all years | `Autres` is also a real category for train incidents (1,688) | Station `Autres` → missing. `#N/A` → missing. Only known after analysis: not used to predict |
| `Cause secondaire` → `secondary_cause` | Secondary cause, decided after analysis | Same as primary cause | `Autres`: all 16,394 station incidents (never used for trains). `#N/A`: the same 482 train incidents as primary cause | `Véhicules de travaux` (20) is spelled differently from the dictionary. `Matériel roulant` (5) is not in the dictionary | Station `Autres` → missing. `#N/A` → missing. Spelling changed to `Véhicule de travaux`. Not used to predict |
| `Symptome` → `symptom` | Initial cause, assigned at the moment of the incident. For stations, the symptom is also the cause | — | `#N/A`: 377 (294 station, 83 train), rising from about 10 a year (2019) to about 100 a year (2023 on) | 2 values not in the dictionary: `Exploitation stations` (5,176) and `Divers` (136) | `#N/A` → missing |
| `Ligne` → `line`, `lines_involved`, `number_of_lines` | Line of the incident: 1 green, 2 orange, 4 yellow, 5 blue | — | `Non affecté`: 103, all at workshops or the control centre, so it means "not on a line", not "unknown". `02-avr`: 1, a value Excel turned into a date | 378 incidents on several lines, with the same lines in different orders (`Ligne 1, 2` and `Ligne 2, 1`) | Single lines keep their colour name (matches the planned km file). Several lines → `Plusieurs lignes`, with sorted numbers in `lines_involved`. `Non affecté` kept as a category (`number_of_lines` = 0). `02-avr` → missing |
| `Numéro de tournée` → `run_number` | Run number of the train involved | `#` = no run associated | `#`: 21,846 (all station incidents and 5,452 train incidents) | — | `#` → missing (means "no run"). Converted to a number |
| `Date du jour (Alpha)` | Calendar day of the incident | — | — | **Not in the file** | — |
| `Heure de l'incident` → `start_datetime` | Trains: start of the delay to customers, *not* the start of the incident. Stations: start of the incident | — | None. But 60 incidents have exactly `02:00` with a calendar date one day after the service date: probably a placeholder time | Two formats (`HH:MM` and `HH:MM:SS`). 2,316 times are past 24:00 (service day). The 60 `02:00` incidents write after-midnight times as `02:00` instead of `26:00` | Converted to a date-time: service date + time. The 60 `02:00` incidents are moved forward one day to match their calendar date, and flagged in `suspect_start_time`. The original time text (e.g. `25:10:00`) is not kept: the service date stays in `service_date` and the service-day hour in `start_service_hour` |
| `Heure de reprise` → `end_datetime` | Trains: end of the delay to customers, *not* the end of the incident. Stations: end of the incident | — | None | Two formats. 3,268 times are past 24:00 (up to 29:xx). No end time after midnight is written as a normal clock time, except in the 60 `02:00` incidents | Converted to a date-time: service date + time (moved forward one day for the 60 `02:00` incidents). The original time text is not kept: the service date stays in `service_date` |
| `Incident en minutes` → `duration_bucket` | **Not in the documentation** | — | None | 8 buckets, from `02 min et moins` (2 min or less) to `30 min et plus` (30 min or more). Measures the delay to train service: every station incident is in the lowest bucket, whatever its real duration. For trains, disagrees with the start and end times in 646 incidents | Kept. Added `bucket_min_minutes` and `bucket_matches_times` (see below) |
| `Jour du mois` → `service_date` | Day of the month of the incident | — | None | Day of the *service* day, not the calendar day. Differs from `Jour calendaire` in 2,376 incidents after midnight | Combined with `Année civile` and `Mois calendrier` into `service_date` (a full date). The separate day-of-month column is not kept, since `service_date` contains it |
| `Véhicule` → `vehicle` | Number of the train car involved | `#` = no car involved | `#`: 33,964 (all station incidents and 17,570 train incidents) | — | `#` → missing (means "no car"). Converted to a number |
| `Porte de voiture` → `car_doors`, `number_of_doors` | Door number(s) involved: 1 to 8, or `toutes` (all) | `#` = no door involved | `#`: 42,766. But 1,335 incidents flagged as door incidents (`Porte` = 1) have `#`, so `#` also means "not recorded" | Several doors written as `1;3;`. `toutes` never appears. 1,219 incidents with a door number have `Porte` = 0 | `#` → missing, meaning "door number not recorded" (not "no door"). Added `number_of_doors` |
| `Type de Matériel` → `rolling_stock_at_fault` | Type of rolling stock: 73 = MR-73, 10 = MPM-10 | — | `Non affecté`: 41,416. Not a missing value: the column is filled **only** when the secondary cause is MR-73 (2,915) or MPM-10 (1,226), plus 4 incidents marked `10` whose cause is `#N/A`. So it means "the train was not the cause" | It is the type of train *blamed after analysis*, not the type of train involved | Renamed. `Non affecté` kept as a category. Only known after analysis: not used to predict |
| `CAT` → `traction_power_cut` | Traction power cut (1 yes / 0 no) | — | None | 7,045 yes | Converted to an integer. When it is set is not documented, so it may be a consequence of the incident |
| `Dommage matériel` → `material_damage` | Possible damage to the train (1 yes / 0 no) | — | None | 353 yes | Converted to an integer. Same timing caveat as `CAT` |
| `KFS` → `emergency_brake` | Emergency brake used by a customer (1 yes / 0 no) | — | None | 1,054 yes | Converted to an integer |
| `Porte` → `door_involved` | A door was involved (1 yes / 0 no) | — | None | 2,911 yes. Contradicts `Porte de voiture` (see above) | Converted to an integer |
| `Urgence métro` → `metro_emergency` | Metro emergency team called in by the control room (1 yes / 0 no) | — | None | 479 yes. This is itself an escalation decision | Converted to an integer. Treated as an outcome, not a feature |
| `Code de lieu` → `location`, `location_type`, `affected_station` | Location of the incident (free text) | — | None | Mixes stations, track between two stations (`Atwater/Guy-Concordia`), other sites such as workshops, garages and power stations (`Faillon PR`, `GARAGE MONTMORENCY`), and whole lines (`Ligne 2`, `Réseau`). Some interchange stations carry a line suffix, with the lines in different orders (`Lionel-Groulx - Ligne 1, 2` and `Lionel-Groulx - Ligne 2, 1`). `Berri L-2` (1,124) is Berri-UQAM's orange-line platform in a different format: all its incidents are on line 2, and plain `Berri-UQAM` is never used for line 2 | Line suffix kept, with the line numbers sorted (`Ligne 2, 1` → `Ligne 1, 2`), also for whole-line locations. `Berri L-2` → `Berri-UQAM - Ligne 2`. Added `location_type`, and `affected_station` (station name without the line suffix). This gives 76 distinct station locations, which are exactly the 68 stations of the network in `affected_station` |
| `Évacuation` → `evacuation` | Evacuation of a car, a train, a station, or a station and a train | `#` = no evacuation | `#`: 44,190 | Other values match the dictionary: `Train`, `Train et Station`, `Voiture`, `Station` | `#` → `Aucune` (none), kept as a category. Same timing caveat as `CAT` |
| `Année civile` → `year` | Year of the incident | — | None | Year of the service day. Data runs from 2019-01-01 to 2025-09-30 (2025 is partial) | Converted to an integer |
| `Année civile/mois` → *(dropped)* | Year/month of the incident | — | None | Text such as `janv-19`; repeats year and month | Dropped |
| `Mois calendrier` → `month` | Month of the incident | — | None | Month of the service day | Converted to an integer |
| `Jour de la semaine` → `weekday` | Day of the week of the incident | — | None | 1 = Monday … 7 = Sunday (not documented), of the service day | Converted to an integer |
| `Jour calendaire` → *(not kept; = date part of `start_datetime`)* | Calendar day of the incident | — | None | The real date: one day after the service date for incidents after midnight (2,376) | Used to find the 60 `02:00` incidents. Not kept as a separate column because it equals the date part of `start_datetime` for every incident (`start_datetime.dt.date`) |

### Values merged during cleaning

Incidents that affect several lines list the line numbers in no fixed order: the same lines can be
written `Ligne 1, 2` or `Ligne 2, 1`. The cleaning sorts the numbers in ascending order, so each
combination of lines has one value. The order is not documented, and we found no meaning for it
(79% of values already list the lowest number first), so we assume it carries none.

**`Ligne`.** The merged value is in `lines_involved`; `line` is `Plusieurs lignes` (several lines)
for all of these.

| Merged value (`lines_involved`) | Raw spellings (rows) |
|---|---|
| `1, 2` | `Ligne 1, 2` (121), `Ligne 2, 1` (43) |
| `1, 2, 4` | `Ligne 1, 2, 4` (88), `Ligne 2, 1, 4` (7), `Ligne 4, 1, 2` (3), `Ligne 4, 2, 1` (3) |
| `1, 2, 5` | `Ligne 1, 2, 5` (6), `Ligne 2, 1, 5` (4) |
| `1, 4` | `Ligne 1, 4` (3), `Ligne 4, 1` (2) |
| `1, 5` | `Ligne 1, 5` (1), `Ligne 5, 1` (1) |
| `2, 5` | `Ligne 2, 5` (48), `Ligne 5, 2` (15) |

`Ligne 1, 2, 4, 5` (28) and `Ligne 2, 4` (5) only appear in one order, so nothing was merged.

**`Code de lieu`.** The same sorting is applied to the line suffix of interchange stations and to
whole-line locations. `Berri L-2` is also merged: it is the same location written in a different
format (see the `Code de lieu` row above).

| Merged value (`location`) | Raw spellings (rows) |
|---|---|
| `Berri-UQAM - Ligne 1, 2` | `Berri-UQAM - Ligne 1, 2` (17), `Berri-UQAM - Ligne 2, 1` (8) |
| `Berri-UQAM - Ligne 1, 2, 4` | `Berri-UQAM - Ligne 1, 2, 4` (66), `Berri-UQAM - Ligne 2, 1, 4` (7), `Berri-UQAM - Ligne 4, 1, 2` (2) |
| `Berri-UQAM - Ligne 1, 4` | `Berri-UQAM - Ligne 1, 4` (2), `Berri-UQAM - Ligne 4, 1` (2) |
| `Berri-UQAM - Ligne 2` | `Berri L-2` (1,124) |
| `Jean-Talon - Ligne 2, 5` | `Jean-Talon - Ligne 2, 5` (19), `Jean-Talon - Ligne 5, 2` (3) |
| `Lionel-Groulx - Ligne 1, 2` | `Lionel-Groulx - Ligne 1, 2` (75), `Lionel-Groulx - Ligne 2, 1` (30) |
| `Snowdon - Ligne 2, 5` | `Snowdon - Ligne 2, 5` (14), `Snowdon - Ligne 5, 2` (5) |
| `Ligne 1, 2` | `Ligne 1, 2` (29), `Ligne 2, 1` (5) |
| `Ligne 1, 2, 4` | `Ligne 1, 2, 4` (22), `Ligne 2, 1, 4` (3), `Ligne 4, 1, 2` (1) |
| `Ligne 1, 2, 5` | `Ligne 1, 2, 5` (6), `Ligne 2, 1, 5` (4) |
| `Ligne 1, 5` | `Ligne 1, 5` (1), `Ligne 5, 1` (1) |
| `Ligne 2, 5` | `Ligne 2, 5` (15), `Ligne 5, 2` (7) |

### Columns added during cleaning

Counts in this table are for the cleaned data (45,556 incidents).

| Column | Meaning |
|---|---|
| `service_date` | Service day, built from `year`, `month` and `Jour du mois`. Use it for daily counts and weekday effects |
| `start_datetime`, `end_datetime` | Real clock time: service date + time, so times past 24:00 fall on the next calendar day |
| `start_service_hour` | Hour of the service day at the start of the incident: 2 to 25, or 26 for the 60 shifted `02:00` incidents. Use it for time-of-day features |
| `duration_minutes` | Calculated duration: `end_datetime` − `start_datetime`, in minutes. For trains: the delay to customers. For stations: how long the incident lasted. Unlike `duration_bucket`, it is meaningful for station incidents too |
| `suspect_start_time` | True for the 60 incidents with a start time of exactly `02:00` but a calendar date one day after the service date. Their times were moved forward one day; the `02:00` start is probably a placeholder |
| `bucket_min_minutes` | Lower limit of `duration_bucket`, in minutes (e.g. `10 à 14 min` → 10) |
| `bucket_matches_times` | Train incidents only: does `duration_minutes` fall inside `duration_bucket`? False for 646 incidents. Empty for station incidents |
| `lines_involved` | All line numbers, sorted (e.g. `1, 2`) |
| `number_of_lines` | Number of lines affected (0 = not on a line) |
| `location_type` | `station` (including stations with a line suffix), `between stations`, `other site` or `line or network` |
| `affected_station` | Station name without the line suffix (`Lionel-Groulx - Ligne 1, 2` → `Lionel-Groulx`), for grouping all incidents at one station. Only filled when `location_type` is `station` (41,379 incidents, 68 stations); missing for track between stations, other sites and whole lines |
| `number_of_doors` | Number of doors in `car_doors`. Empty when not recorded |

### Rows removed

| What | Rows | Why |
|---|---|---|
| Duplicates | 5 | Identical in every column except the incident number, which is consecutive or nearly so (e.g. `T28102213` and `T28102214`; `S01042203` and `S01042205`). Probably the same incident entered twice. The first of each pair is kept |

The cleaned file has 45,556 incidents.

### Planned metro kilometres

| Raw column → clean column | Definition (documentation) | Missing-value code (documentation) | Missing-value code in the data (rows) | Other findings in the data | Cleaning |
|---|---|---|---|---|---|
| `Ligne` → `line` | Name of the line | — | None | 4 lines, same colour names as the incidents file | Kept (used to join the two files) |
| `Jour calendaire` → `date` | Calendar day | — | None | Runs from 2019-01-01 to **2023-09-30 only**; incidents run to 2025-09-30 | Converted to a date |
| `KM planifié` → `planned_km` | Planned km after the year's budget adjustments | — | `0`: 1,536, the empty half of each pair of placeholder rows (see next row) | Written with a French decimal comma (`16315,92`). Planned, not actually run | Converted to a number. Summed per line and day |
| `Période Exploitation`, `Type de Jour` | Service period and day type | — | `#` (`Période Exploitation`) and `Non affecté` (`Type de Jour`): 1,536 rows. On 384 days between 2019-01-01 and 2020-06-14, each line has a second row with these codes | Exactly one row in each pair has kilometres, and it is not always the normal row (868 times it is the `#` row), so the `#` rows cannot simply be dropped | The two rows are added together, then these columns are dropped |
| `Tournée` | Run number: 001, 050, 060, 066 or 999 | — | None | Always `001` | Dropped |
| `Année civile`, `Année civile/mois`, `Année civile/semaine`, `Jour de la semaine`, `Mois calendrier` | Date parts | — | None | Repeat `Jour calendaire` | Dropped; `year` and `month` rebuilt from `date` |

The cleaned file has one row per line per day (6,936 rows). It is used in section 5 of
[`modelling.ipynb`](modelling.ipynb) to calculate interruptions per million planned km, by year
and by line. Only incidents on a single line, up to September 2023, can be matched to it.

### Recommended data improvements

What STM could change in how the data is recorded and published, based on the issues above and
on the modelling in [`modelling.ipynb`](modelling.ipynb). The first two limit the analysis most.

| Issue | Effect on this analysis | Recommendation |
|---|---|---|
| **Escalation is not recorded.** The only response recorded is calling the metro emergency team (`Urgence métro`), with no time. It is a specialised response: among delays of 30 minutes or more, it was called for 84% of those with a rolling-stock symptom, but only 13% of those with fire or smoke | It is impossible to measure whether escalating earlier reduces disruption, or to evaluate any escalation model | Record **every** escalation: which team or action (emergency team, other teams, replacement buses, public communication) and when |
| **For train incidents, the times are the start and end of the delay to customers**, not of the incident | No way to measure how long detection or escalation takes; the prediction time in the model is approximate | Also record when the incident started, was detected, was escalated, and when service resumed |
| **When the response flags are set is not recorded** (`CAT`, `Évacuation`, `Dommage matériel`) | They had to be left out of the models, though adding them doubles PR-AUC: it is unknown whether they are known early or are consequences of a long incident | Record the time each flag is set |
| **`Incident en minutes` is not documented**, and disagrees with the start and end times for 646 train incidents | Two competing sources of truth for the target | Document it, and derive it automatically from the times |
| **Missing values are coded several ways** (`#N/A`, `#`, `Non affecté`), and station causes are filled with `Autres` instead of being left empty | Easy to misread: `Autres` looks like 40% of all causes | Use empty values, and document any code that is kept |
| **The service-day convention is not documented**, and 60 incidents break it (`02:00`) | Timestamps had to be rebuilt and checked by hand | Document it, or publish full date-times |
| **`Ligne` and `Code de lieu` are free text**: lines in different orders, one value corrupted by Excel (`02-avr`), two formats for Berri-UQAM's orange line | Values had to be merged by hand | Store the lines as a structured list of line numbers |
| **Some fields contradict each other or mean something other than documented**: `Porte` and `Porte de voiture` disagree in about 2,550 incidents; `Type de matériel` is only filled when a train is blamed | Features that look usable are unreliable or leak the outcome | Document what each field means, and check consistency when incidents are entered |
| **Missing `Symptome` values are rising** (about 10 a year in 2019, about 100 a year from 2023) | A change in reporting practice can look like a change in reliability | Make the symptom mandatory |
| **Planned km stops in September 2023**, and is planned, not actually run | Incident rates per km cannot be calculated for 2024 to 2025 | Publish planned and actual km for the same period as the incidents |
| **No ridership or cost data** | Impact on riders and the financial burden cannot be measured | Link incidents to ridership by line and time of day, and to cost estimates |
