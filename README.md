# Predicting major metro service interruptions

Technical challenge leveraging STM's open data on metro incidents (January 2019 to
September 2025) and planned metro kilometres (January 2019 to September 2023).

## Summary

After cleaning and exploring the dataset, we set up a prediction task for major interruptions. 
At first, we defined a basic target: predicting if an incident will last more than 10 minutes. After concluding that no alert threshold gave a satisfactory balance of precision and recall, we redefined the problem to predicting at 5 minutes elapsed if an incident would last over 30 minutes - a more actionable and consequential target. Under this definition we found that while we could build models that capture real signal, we still did not meet our success target for balanced actionable predictions. We explain why and offer suggestions for future improvements.

Along the way, we unpack several secondary findings, for example:
- simple triggers such as fire, smoke or odour, or delays lasting 15 minutes, offer clear indications that a delay will last 30 minutes about 50% of the time. 
- clear data on escalation is missing; the metro emergency team is only one example of escalation. Collecting additional data would help future analyses.
- service volumes do not explain incident trends

This README explains the repository itself, and then summarizes major data cleaning and modelling decisions and results, while leaving details to the code files themselves. We then provide takeaway summaries for each of the STM stakeholders, and offer actionable recommendations.

## Repository and how to run

| File | Contents |
|---|---|
| [`clean_data.py`](clean_data.py) | Reads the two raw files, cleans them and writes `data/incidents_clean.csv` and `data/planned_km_clean.csv`. Every cleaning decision is documented in [Data dictionary and cleaning](#data-dictionary-and-cleaning) below |
| [`modelling.ipynb`](modelling.ipynb) | The analysis: target, features, validation, models, robustness checks and reliability per km. Saved with its outputs, so it can be read without running it |
| [`requirements.txt`](requirements.txt) | Package versions (Python 3.14) |

To run the analysis:

1. Install the packages: `python -m venv .venv`, `source .venv/bin/activate`,
   `pip install -r requirements.txt`.
2. Unpack the challenge contents into a folder named `STM challenge Data Scientist/` at the root of the repository.
3. Run `python clean_data.py` to write the cleaned files, or run
   [`modelling.ipynb`](modelling.ipynb) from top to bottom, in `jupyter lab` or an IDE: it cleans the raw files itself, through
   `clean_incidents()` and `clean_planned_km()`.

**Use of AI.** The code and this README were produced in collaboration with Claude, mostly Opus 5.5. An initial EDA was conducted without the use of AI (but leveraging dataset summarization libraries). All code and text was reviewed, and the most critical text was re-written by a human (because no-one wants to read AI all day).

## Analytical strategy

### Target

**Train incidents only.** The documentation says station incidents do not affect metro service, so
we cannot clearly link them to major interruptions. To reduce overall complexity and provide clear messaging, we therefore choose to focus only on metro service interruptions.

**Why not predict escalation itself?** Escalation is what STM wants to improve, but the data barely
records it. The only response recorded is calling the metro emergency team, which is specialised:
among delays of 30 minutes or more, it was called for 84% of those with a rolling-stock symptom but
only 13% of those with fire or smoke. Predicting it would reproduce current practice, not improve on
it. So we predict what escalation is meant to prevent, a long interruption, while there is still
time to act.

The notebook tries two versions of the question, in order:

| | Part 1 | Part 2 |
|---|---|---|
| Target/Question | When a train incident is reported, will the delay reach 10 minutes? | When a train delay has lasted 5 minutes, will it reach 30 minutes? |
| Population | All train incidents | Train delays that reached 5 minutes (STM's definition of an interruption) |
| Disruption still to come when a correct alert fires | At least 10 minutes | At least 25 minutes |

**What counts as major.** The STM does not provide a definition so we decided on our own (this would be discussed with them):

- **10 minutes (Part 1):** past the 5 to 9 minutes that make up 69% of interruptions, so no longer a
  routine delay.
- **30 minutes (Part 2):** 8% of interruptions but 39% of the delay minutes, with an evacuation in
  78% of them (23% at 10 to 14 minutes).

**Duration measure.** We define duration using STM's duration category (`Incident en minutes`), not our
own calculation from the start and end times, because we read the category as the delay to train
service. There is a discrepancy between the two, which is both a warning and a future data improvement; the notebook covers the full details. 

### Features

We use only information we expect to be known when the prediction is made:

- the symptom, which the documentation says is assigned at the moment of the incident;
- the station, line and type of location;
- the hour of the service day, the weekday and the month;
- the emergency-brake and door flags;
- whether a train car or run number is recorded.

We leave out columns that look useful but may not be available in time:

- **Primary and secondary causes, and the type of rolling stock blamed:** decided after analysis,
  sometimes weeks later.
- **Calling the metro emergency team:** this is itself a response.
- **Traction power cut, evacuation and material damage:** the documentation does not say when they
  are set. Adding them roughly doubles PR-AUC, a sign that they largely describe the response to a
  long incident.

### Validation

- **Split by time:** the models are fit on 2019 to 2023 (21,057 train incidents) and tested on
  January 2024 to September 2025 (8,109). This mimics real use: trained on the past, applied to the
  future. A random split would let the model learn from incidents that happen after the ones it is
  tested on.
- **Validation year:** to compare the two models, we fit them first on 2019 to 2022 and score them on 2023.
  They are close, so both go on to the test years, with logistic regression as the main model because
  it is simpler. In a more involved analysis with more time we might use the validation set for judging tuned models.
- **Bootstrap intervals:** these show whether a difference between two methods is larger than chance.
  Both methods are scored on the same resampled test incidents.

### Metrics and reporting

Major interruptions are rare, so accuracy is not useful. We use:

- **PR-AUC**, read against the base rate, because a random ranking scores about the base rate.
  ROC-AUC is reported for reference.
- **Our self-defined success criterion:** an alert threshold that catches at least half
  of the major interruptions while at least 1 alert in 3 is right. Below that, the control room would
  either miss most major interruptions or learn to ignore the alerts. The 50% and 1-in-3 levels are
  an operational assumption that would be discussed with the STM.
- **Alert tables:** if the control room escalated the riskiest X% of incidents (riskiest meaning the
  highest predicted probability of being major), how many major ones
  would it catch? This provides clear understanding to the stakeholders.
- **Calibration:** can the model's probabilities be taken at face value?
- **Two baselines:** the base rate, and a symptom rule that gives each incident its symptom's past
  rate of major delays. This symptom rule is what a controller could do without a model.

### Models

Logistic regression is the main model because it is simple and interpretable. Gradient boosting is a
check that a more flexible model would not do much better, and it does not. Neither model is tuned.

### Alternatives considered

- **A survival model of delay duration:** this would give the risk of reaching 30 minutes at *any*
  elapsed time, not just at minute 5. Part 2 is one slice of it, so this is the natural next step.
- **Forecasting the number of incidents per line and day:** this answers a planning question, not the
  escalation question, so we did not pursue it.
- **A severity target combining duration with evacuation or several lines:** these flags cannot be
  features, but they could help define the target. We kept the simpler duration target and did not
  test this.
- **Estimating whether calling the metro emergency team shortens delays:** ruled out. There is no
  call time, and the team tends to be called for the worst incidents, so a comparison would be
  misleading.

## Findings

Test years (January 2024 to September 2025):

| | Part 1: at report, 10+ minutes | Part 2: at minute 5, 30+ minutes |
|---|---|---|
| Base rate (major incidents) | 0.077 (625 of 8,109) | 0.084 (156 of 1,857) |
| PR-AUC, symptom rule | 0.118 | 0.213 |
| PR-AUC, logistic regression | **0.262** (3.4 times the base rate) | **0.299** (3.6 times) |
| PR-AUC, gradient boosting | 0.277 | 0.264 |
| Major incidents caught with at least 1 alert in 3 right (bar: 50%) | 14% (244 alerts, about 12 a month) | 34% (154 alerts, about 7 a month) |

- **Part 1 finds real signal but cannot be easily acted on.** Logistic regression clearly beats the
  symptom rule (bootstrap interval for the PR-AUC difference: 0.12 to 0.17), but it is far from
  the bar. And its alerts fire when the delay has just started: in the training years, 46% of
  10-minute delays were over before 15 minutes, often too soon for a response to make a difference.
- **Elapsed time is an important variable.** In the training years, 1.7% of train incidents reach
  30 minutes; among delays that have lasted 5 minutes, 8.1%; 10 minutes, 26%; 15 minutes, 48%.
- **Part 2's improvement has two sources** (section 3.6 of the notebook). With the same 30-minute target at
  minute 0, the model catches 23% of major incidents (PR-AUC 0.181), against 34% (0.299) at minute 5.
  So of the rise from 14% in Part 1 to 34%, about 9 points come from the target and 11 from waiting
  until minute 5.
- **The model adds to the symptoms in Part 2** (PR-AUC difference 0.05 to 0.13). Fire, smoke or
  odour still delaying service at minute 5 is the clearest single signal: 51% of these incidents
  reached 30 minutes in the test years (40 of 79), a quarter of all 30-minute interruptions. The
  model already puts 78 of these 79 incidents in its riskiest 10% (about 9 alerts a month).
- **The probabilities are reasonably calibrated:** 9.0% predicted on average against 8.4%
  observed. The highest-risk group is overestimated (about 27% predicted against 20% observed).
- **Reliability per km** (January to September of each year, so that years compare fairly):

  | | 2019 | 2020 | 2021 | 2022 | 2023 |
  |---|---|---|---|---|---|
  | Interruptions of 5+ minutes per million planned km | 9.72 | 9.53 | 9.56 | 10.31 | 12.98 |
  | Interruptions of 30+ minutes per million planned km | 0.60 | 0.74 | 0.76 | 0.90 | 0.75 |

  In 2023, planned km was 8% below 2019, but interruptions were 23% above. So service volume does not
  explain the rise: it reflects either a real drop in reliability or a change in how incidents are
  recorded, and this data cannot say which. Interruptions of
  30 minutes or more are too few (40 to 57 a year) to separate a trend from year-to-year
  variation. By line (2019 to September 2023), per million km: green 12.8, blue 12.1, yellow 9.1,
  orange 8.2, with the same pattern at 30 minutes or more. The green and orange lines have similar raw counts, but the orange line runs about a
  third more service.
- **How symptoms are recorded has changed over time** (train incidents, section 5.4 of the notebook):

  | Share of train incidents | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 (Jan to Sep) |
  |---|---|---|---|---|---|---|---|
  | `Exploitation stations` | 0.8% | 1.0% | 2.2% | 3.1% | 3.4% | 4.7% | 8.8% |
  | `Exploitation trains` | 12.3% | 9.3% | 7.3% | 6.1% | 4.9% | 4.0% | 5.4% |
  | Symptom missing (`#N/A`) | 2 | 2 | 7 | 17 | 21 | 22 | 12 |

  The last row is a count of incidents. `Exploitation stations` (operations in stations) is not in
  the documentation's list of symptoms, yet it is used for a growing share of *train* incidents,
  while `Exploitation trains` shrinks. The change is gradual, which
  points to a change in how incidents are classified rather than in what happens. Station incidents
  show the same rise in missing symptoms, from 9 a year to about 80.

  **This does not explain the 2023 rise**, which is spread across the main symptoms, but a trend in
  one symptom may reflect classification, not reliability.
- **One cause surges inside the test years** (section 5.5 of the notebook). `Service de la voie` is
  41% of train incidents in August and September 2024, and its share with a rolling-stock symptom
  rose from 4% in 2019 to 72% in 2024. Neither the 2023 rise nor the test results depend on it.

  ### Overall summary:

Neither model meets our self-imposed success criterion, however part 2 is clearly an improvement. Pending discussion with stakeholders to better understand missing variables, it would likely be reasonable for a controller to take the model's predictions into account when making an escalation decision in the control room.

## Recommendations

### How STM should measure reliability

- Count **interruptions of 5 minutes or more per million km actually run**, by line and month.
  Raw counts mislead when comparing lines or years.
- Track **interruptions of 30 minutes or more separately, with their uncertainty**: they are rare,
  so year-to-year changes are hard to tell from noise.
- Keep **station incidents separate**: they do not affect service.
- **Check whether recording changed in 2023**, before reading the 2023 rise as a drop in
  reliability.
- **Keep symptom categories stable, or document when they change.**

### How to prioritise action

**VP Operations (earlier escalation, reduced disruption).**

- Use **elapsed time as the main trigger**, sharpened by the symptom and the model. At minute 5,
  escalate the model's riskiest 10% of delays, which already includes nearly all fire, smoke or odour
  incidents.
- Without a model, use two triggers: any fire, smoke or odour incident still delaying service at
  minute 5, and any delay still running at minute 15.
- **Record every escalation and its time**, so that the effect of escalating earlier can be measured,
  and better models with better tradeoffs can be built.

**CFO (prioritisation, confidence, financial burden).**

- **Prioritise lines by rate per km, not by count:** on that measure, the green and blue lines come
  first.
- **Confidence:** treat the model as support for the control room, not a decision-maker. It is better
  than a simple rule but misses the success bar, so it would likely not be trusted on its own. Use it
  to rank incidents, and read its top scores as "high", not as exact probabilities. More complete and
  reliable data would enable a higher-confidence model.
- **Financial burden:** this data cannot measure it. Link incidents to cost and ridership data; until
  then, delay minutes could stand in for impact, with stated assumptions.

**Public Affairs and Safety (user impact, communication risk, rare severe events).**

- **Use fire, smoke or odour as the trigger for early public communication:** it is the clearest early
  warning of a long interruption, and a safety issue in itself.
- **Communicate rare severe events with their uncertainty:** interruptions of 30 minutes or more are
  rare, so every estimate about them is uncertain. Collecting and publishing detailed data about how
  they unfold could lead to a better predictive model.
- **Link incidents to ridership by line and time of day**, so that user impact can be measured.

### How to improve data collection

What STM could change in how the data is recorded and published, most important first:

| Issue | Effect on this analysis | Recommendation |
|---|---|---|
| **Escalation is not recorded**, apart from calling the metro emergency team, with no time | It is impossible to measure whether escalating earlier reduces disruption, or to evaluate any escalation model | Record **every** escalation: which team or action (emergency team, other teams, replacement buses, public communication) and when |
| **`Incident en minutes` is not documented**, and disagrees with the start and end times | Two competing sources of truth for the target: the times give 27% more interruptions of 30 minutes or more | Document what it measures and how it relates to the start and end times, and resolve the inconsistency between the two in the data. Record the delay to service and the length of the incident as separate fields |
| **Train times cover the delay to customers**, not the incident | No way to measure how long detection or escalation takes; the prediction time in the model is approximate | Also record when the incident started, was detected, was escalated, and when service resumed |
| **When the response flags are set is not recorded** (`CAT`, `Évacuation`, `Dommage matériel`) | They had to be left out of the models: it is unknown whether they are known early or are consequences of a long incident | Record the time each flag is set |
| **Planned km stops in September 2023**, and is planned, not actually run | Incident rates per km cannot be calculated for 2024 to 2025 | Publish planned and actual km for the same period as the incidents |
| **No ridership or cost data** | Impact on riders and the financial burden cannot be measured | Link incidents to ridership by line and time of day, and to cost estimates |
| **Symptom recording changes over time** (see Findings) | A change in classification can look like a change in reliability, and the symptom, a key feature of the models, means slightly different things in different years | Make the symptom mandatory, document every category, and record when the categories or their rules change |
| **Some fields contradict each other or differ from their documentation**, such as `Porte` and `Porte de voiture`, and `Type de matériel` | Features that look usable are unreliable or leak the outcome | Document what each field means, and check consistency when incidents are entered |
| **The service-day convention is not documented**, and the `02:00` incidents break it | Timestamps had to be rebuilt and checked by hand | Document it, or publish full date-times |
| **Missing values are coded several ways** (`#N/A`, `#`, `Non affecté`, `Autres`) | Easy to misread: `Autres` looks like 40% of all causes | Use empty values, and document any code that is kept |
| **`Ligne` and `Code de lieu` are free text**, with inconsistent formats | Values had to be merged by hand | Store the lines as a structured list of line numbers |

## Assumptions

- **Prediction time:** "at report time" means the recorded start of the delay to customers, and Part 2
  predicts 5 minutes after it.
- **Features known in time:** the location, line, flags and whether a car or run number is recorded
  are assumed to be known by the prediction time. Part 2 does not depend on this (section 4.2 of the
  notebook).
- **The success bar** (50% caught, 1 alert in 3 right) is our operational choice.
- **"Major" is our definition** (10 minutes in Part 1, 30 in Part 2), for STM to confirm.
- **STM's duration category is the truth** for the target, not the start and end times: the most
  consequential choice (section 4.3 of the notebook).
- **The service day runs from 2 a.m. to 2 a.m.**, inferred from the data, not documented (see
  [Data dictionary and cleaning](#data-dictionary-and-cleaning)).
- **The 60 incidents that start at exactly `02:00` are moved forward one day**, because their calendar
  date is the day after their service date. The `02:00` is probably a placeholder. Only 14 are train
  incidents and none reached 5 minutes, so this barely affects the models.
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
- **Change over time:** the training years include the COVID period (2020 to 2021), and 2025 is
  partial. The latest months show no sign of being incomplete (section 1.2 of the notebook). The 2023 rise in interruptions per km
  is unexplained. Symptom categories also shift over the years, so the symptom does not mean exactly
  the same thing in the training and test years.
- **Data quality:** the start and end times give 18% to 27% more major incidents than the duration
  category, and these disagreements are rising (section 4.3 of the notebook). The documentation
  defines the times, not the category, as the delay to customers. Several fields contradict each
  other or are not documented (see the data dictionary).
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

**The `02:00` incidents.** 60 incidents start at exactly `02:00` but have a calendar date one day after
their service date. They break the convention: their times are written `02:00` instead of `26:00`, and
the `02:00` is probably a placeholder. Their start and end are moved forward one day to match their
calendar date (duration unchanged), their `start_service_hour` is 26, and they are flagged in
`suspect_start_time`.

### Metro incidents

| Raw column → clean column | Definition (documentation) | Missing-value code (documentation) | Missing-value code in the data (rows) | Other findings in the data | Cleaning |
|---|---|---|---|---|---|
| `Numero d'incident` → `incident_id` | Unique number identifying each incident (numeric) | — | None | All unique. Not numeric: T or S, then the service day as DDMMYY, then a sequence number (e.g. `T01082509` = train, 01-08-25, incident 09). The date matches the service date for every incident | Kept as text |
| `Type d'incident` → `incident_type` | T = train, S = station | — | None | 29,167 train, 16,394 station | None |
| `Cause primaire` → `primary_cause` | Primary cause, decided after analysis of the incident | Left empty for station incidents (no code given). Train analysis can take more than 30 days | `Autres`: all 16,394 station incidents. `#N/A`: 482 train incidents, spread over all years | `Autres` is also a real category for train incidents (1,688) | Station `Autres` → missing. `#N/A` → missing. Only known after analysis: not used to predict |
| `Cause secondaire` → `secondary_cause` | Secondary cause, decided after analysis | Same as primary cause | `Autres`: all 16,394 station incidents (never used for trains). `#N/A`: the same 482 train incidents as primary cause | `Véhicules de travaux` (20) is spelled differently from the dictionary. `Matériel roulant` (5) is not in the dictionary | Station `Autres` → missing. `#N/A` → missing. Spelling changed to `Véhicule de travaux`. Not used to predict |
| `Symptome` → `symptom` | Initial cause, assigned at the moment of the incident. For stations, the symptom is also the cause | — | `#N/A`: 377 (294 station, 83 train), rising from about 10 a year (2019) to about 100 a year (2023 on) | 2 values not in the dictionary: `Exploitation stations` (5,176) and `Divers` (136). `Exploitation stations` and `Exploitation trains` shift over time (see Findings) | `#N/A` → missing |
| `Ligne` → `line`, `lines_involved`, `number_of_lines` | Line of the incident: 1 green, 2 orange, 4 yellow, 5 blue | — | `Non affecté`: 103, all at workshops or the control centre, so it means "not on a line", not "unknown". `02-avr`: 1, a value Excel turned into a date | 378 incidents on several lines, with the same lines in different orders (`Ligne 1, 2` and `Ligne 2, 1`) | Single lines keep their colour name (matches the planned km file). Several lines → `Plusieurs lignes`, with sorted numbers in `lines_involved`. `Non affecté` kept as a category (`number_of_lines` = 0). `02-avr` → missing |
| `Numéro de tournée` → `run_number` | Run number of the train involved | `#` = no run associated | `#`: 21,846 (all station incidents and 5,452 train incidents) | — | `#` → missing (means "no run"). Converted to a number |
| `Date du jour (Alpha)` | Calendar day of the incident | — | — | **Not in the file** | — |
| `Heure de l'incident` → `start_datetime` | Trains: start of the delay to customers, *not* the start of the incident. Stations: start of the incident | — | None, apart from the `02:00` incidents (see Service day) | Two formats (`HH:MM` and `HH:MM:SS`). 2,316 times are past 24:00 (service day). | Converted to a date-time: service date + time (see Service day for the `02:00` incidents). The original time text (e.g. `25:10:00`) is not kept: the service date stays in `service_date` and the service-day hour in `start_service_hour` |
| `Heure de reprise` → `end_datetime` | Trains: end of the delay to customers, *not* the end of the incident. Stations: end of the incident | — | None | Two formats. 3,268 times are past 24:00 (up to 29:xx). | Converted to a date-time: service date + time (see Service day for the `02:00` incidents). The original time text is not kept: the service date stays in `service_date` |
| `Incident en minutes` → `duration_bucket` | **Not in the documentation** | — | None | 8 buckets, from `02 min et moins` (2 min or less) to `30 min et plus` (30 min or more). We read it as the delay to train service, because every station incident is in the lowest bucket, whatever its real duration; this is an inference (see Assumptions). For trains, disagrees with the start and end times in 646 incidents, almost always because the times are longer: 141 incidents last 30 minutes or more by the times but not by the category (8 in 2019, 37 in 2024) | Kept. Added `bucket_min_minutes` and `bucket_matches_times` (see below) |
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
| `Jour calendaire` → *(not kept; = date part of `start_datetime`)* | Calendar day of the incident | — | None | The real date: one day after the service date for incidents after midnight (2,376) | Used to find the `02:00` incidents. Not kept as a separate column because it equals the date part of `start_datetime` for every incident (`start_datetime.dt.date`) |

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
| `service_date`, `start_datetime`, `end_datetime`, `start_service_hour` | See Service day above |
| `duration_minutes` | Calculated duration: `end_datetime` − `start_datetime`, in minutes. For trains: the delay to customers. For stations: how long the incident lasted. Unlike `duration_bucket`, it is meaningful for station incidents too |
| `suspect_start_time` | True for the `02:00` incidents (see Service day above) |
| `bucket_min_minutes` | Lower limit of `duration_bucket`, in minutes (e.g. `10 à 14 min` → 10) |
| `bucket_matches_times` | Train incidents only: does `duration_minutes` fall inside `duration_bucket`? Empty for station incidents |
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
