# Predicting major metro service interruptions

Technical challenge leveraging STM's open data on metro incidents (January 2019 to
September 2025) and planned metro kilometres (January 2019 to September 2023).

**A note on methodology and timing**: I made heavy use of AI, mostly Claude Opus 5.5. Following my own philosophy of how one should leverage AI in general I spent 4 hours roughly divided into 30 minutes non-AI EDA  + ideation, 1h30 AI-heavy work with iteration getting to 90%, 2h cleanup, review and re-write. I chose to pursue a very broad + complete solution within the time constraint, but this choice does sacrifice depth and increases the possibility of uncaught errors. 

I use 'we' in this writeup simply because it felt less awkward than I.

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
| [`clean_data.py`](clean_data.py) | Reads the two raw files, cleans them and writes `data/incidents_clean.csv` and `data/planned_km_clean.csv`. Every cleaning decision is documented in [`DATA.md`](DATA.md) |
| [`DATA.md`](DATA.md) | Data dictionary and cleaning: for every column, what the documentation says, what the data shows and what the cleaning does |
| [`modelling.ipynb`](modelling.ipynb) | The analysis: target, features, validation, models, robustness checks and reliability per km. Saved with its outputs, so it can be read without running it |
| [`requirements.txt`](requirements.txt) | Package versions (Python 3.14) |

To run the analysis:

1. Install the packages: `python -m venv .venv`, `source .venv/bin/activate`,
   `pip install -r requirements.txt`.
2. Unpack the challenge contents into a folder named `STM challenge Data Scientist/` at the root of the repository.
3. Run `python clean_data.py` to write the cleaned files, or run
   [`modelling.ipynb`](modelling.ipynb) from top to bottom, in `jupyter lab` or an IDE: it cleans the raw files itself, through
   `clean_incidents()` and `clean_planned_km()`.


## Analytical strategy

### Target

**Train incidents only.** The documentation says station incidents do not affect metro service, so
we cannot clearly link them to major interruptions. To reduce overall complexity and provide clear messaging, we therefore choose to focus only on metro service interruptions.

**Why not predict escalation itself?** Escalation is what STM wants to improve but it is not clearly reflected in the data. The only response recorded is calling the metro emergency team, which is specialised:
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
check that a more flexible model would not do much better. Neither model is tuned; they could be given more time.

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
  Still, this means that probabilities can be used.
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
  third more service. The km unit is not documented, but the figures are very likely car-km: as
  train-km, they would mean a train about every 35 seconds in each direction. Assuming 6-car trains on
  the blue line and 9 on green and orange, the green line stays about 50% above orange per train-km,
  while the blue line is level with it (0.98 times, interval 0.88 to 1.08). The yearly trend is not
  affected (section 5.2 of the notebook).
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
  Raw counts mislead when comparing lines or years. State the km unit, because lines with shorter
  trains look worse per car-km.
- Track **interruptions of 30 minutes or more separately, with their uncertainty**: they are rare,
  so year-to-year changes are hard to tell from noise.
- Keep **station incidents separate**: they do not affect service.
- **Check whether recording changed in 2023**, before reading the 2023 rise as a drop in
  reliability.
- **Keep symptom categories stable, or document when they change.**

### How to prioritise action

**VP Operations (earlier escalation, reduced disruption).**

- Feel comfortable using **elapsed time as the main trigger (don't jump to act)**, sharpened by the symptom and the model. At minute 5, consider asking the controllers to take into account a prediction of a highest probability-delay, which already includes nearly all fire, smoke or odour incidents.
- Without a model, use two triggers: any fire, smoke or odour incident still delaying service at
  minute 5, and any delay still running at minute 15.
- **Record every escalation and its time**, so that the effect of escalating earlier can be measured,
  and better models with better tradeoffs can be built.

**CFO (prioritisation, confidence, financial burden).**

- **Prioritise lines by rate per km, not by count:** the green line comes first per car-km and per
  train-km. The blue line only stands out per car-km.
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
| **Planned km stops in September 2023**, is planned, not actually run, and has no documented unit | Incident rates per km cannot be calculated for 2024 to 2025, and line comparisons depend on the unit | Publish planned and actual km for the same period as the incidents, and state the unit |
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
  [`DATA.md`](DATA.md)).
- **The 60 incidents that start at exactly `02:00` are moved forward one day**, because their calendar
  date is the day after their service date. The `02:00` is probably a placeholder. Only 14 are train
  incidents and none reached 5 minutes, so this barely affects the models.
- **Undocumented codes are interpreted from the data**, for example `Non affecté` in `Ligne` as
  "not on a line" (see [`DATA.md`](DATA.md)).
- **The planned km file's dates are service days**, like the incidents.
- **The planned km are car-km**, with 6-car trains on the blue line and 9 on green and orange. The
  documentation gives no unit, and the train lengths come from public sources, which conflict for the
  yellow line.

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
  other or are not documented (see [`DATA.md`](DATA.md)).
- **Rates per km use planned, not actual, km**, and stop in September 2023, so 2024 and 2025 cannot
  be turned into rates.
- **No ridership or cost data**, so user impact and the financial burden cannot be measured.
