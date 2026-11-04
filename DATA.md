# Data dictionary and cleaning

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

## Metro incidents

| Raw column → clean column | Definition (documentation) | Missing-value code (documentation) | Missing-value code in the data (rows) | Other findings in the data | Cleaning |
|---|---|---|---|---|---|
| `Numero d'incident` → `incident_id` | Unique number identifying each incident (numeric) | — | None | All unique. Not numeric: T or S, then the service day as DDMMYY, then a sequence number (e.g. `T01082509` = train, 01-08-25, incident 09). The date matches the service date for every incident | Kept as text |
| `Type d'incident` → `incident_type` | T = train, S = station | — | None | 29,167 train, 16,394 station | None |
| `Cause primaire` → `primary_cause` | Primary cause, decided after analysis of the incident | Left empty for station incidents (no code given). Train analysis can take more than 30 days | `Autres`: all 16,394 station incidents. `#N/A`: 482 train incidents, spread over all years | `Autres` is also a real category for train incidents (1,688) | Station `Autres` → missing. `#N/A` → missing. Only known after analysis: not used to predict |
| `Cause secondaire` → `secondary_cause` | Secondary cause, decided after analysis | Same as primary cause | `Autres`: all 16,394 station incidents (never used for trains). `#N/A`: the same 482 train incidents as primary cause | `Véhicules de travaux` (20) is spelled differently from the dictionary. `Matériel roulant` (5) is not in the dictionary | Station `Autres` → missing. `#N/A` → missing. Spelling changed to `Véhicule de travaux`. Not used to predict |
| `Symptome` → `symptom` | Initial cause, assigned at the moment of the incident. For stations, the symptom is also the cause | — | `#N/A`: 377 (294 station, 83 train), rising from about 10 a year (2019) to about 100 a year (2023 on) | 2 values not in the dictionary: `Exploitation stations` (5,176) and `Divers` (136). `Exploitation stations` and `Exploitation trains` shift over time (see Findings in the [README](README.md#findings)) | `#N/A` → missing |
| `Ligne` → `line`, `lines_involved`, `number_of_lines` | Line of the incident: 1 green, 2 orange, 4 yellow, 5 blue | — | `Non affecté`: 103, all at workshops or the control centre, so it means "not on a line", not "unknown". `02-avr`: 1, a value Excel turned into a date | 378 incidents on several lines, with the same lines in different orders (`Ligne 1, 2` and `Ligne 2, 1`) | Single lines keep their colour name (matches the planned km file). Several lines → `Plusieurs lignes`, with sorted numbers in `lines_involved`. `Non affecté` kept as a category (`number_of_lines` = 0). `02-avr` → missing |
| `Numéro de tournée` → `run_number` | Run number of the train involved | `#` = no run associated | `#`: 21,846 (all station incidents and 5,452 train incidents) | — | `#` → missing (means "no run"). Converted to a number |
| `Date du jour (Alpha)` | Calendar day of the incident | — | — | **Not in the file** | — |
| `Heure de l'incident` → `start_datetime` | Trains: start of the delay to customers, *not* the start of the incident. Stations: start of the incident | — | None, apart from the `02:00` incidents (see Service day) | Two formats (`HH:MM` and `HH:MM:SS`). 2,316 times are past 24:00 (service day). | Converted to a date-time: service date + time (see Service day for the `02:00` incidents). The original time text (e.g. `25:10:00`) is not kept: the service date stays in `service_date` and the service-day hour in `start_service_hour` |
| `Heure de reprise` → `end_datetime` | Trains: end of the delay to customers, *not* the end of the incident. Stations: end of the incident | — | None | Two formats. 3,268 times are past 24:00 (up to 29:xx). | Converted to a date-time: service date + time (see Service day for the `02:00` incidents). The original time text is not kept: the service date stays in `service_date` |
| `Incident en minutes` → `duration_bucket` | **Not in the documentation** | — | None | 8 buckets, from `02 min et moins` (2 min or less) to `30 min et plus` (30 min or more). We read it as the delay to train service, because every station incident is in the lowest bucket, whatever its real duration; this is an inference (see Assumptions in the [README](README.md#assumptions)). For trains, disagrees with the start and end times in 646 incidents, almost always because the times are longer: 141 incidents last 30 minutes or more by the times but not by the category (8 in 2019, 37 in 2024) | Kept. Added `bucket_min_minutes` and `bucket_matches_times` (see below) |
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

## Values merged during cleaning

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

## Columns added during cleaning

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

## Rows removed

| What | Rows | Why |
|---|---|---|
| Duplicates | 5 | Identical in every column except the incident number, which is consecutive or nearly so (e.g. `T28102213` and `T28102214`; `S01042203` and `S01042205`). Probably the same incident entered twice. The first of each pair is kept |

The cleaned file has 45,556 incidents.

## Planned metro kilometres

| Raw column → clean column | Definition (documentation) | Missing-value code (documentation) | Missing-value code in the data (rows) | Other findings in the data | Cleaning |
|---|---|---|---|---|---|
| `Ligne` → `line` | Name of the line | — | None | 4 lines, same colour names as the incidents file | Kept (used to join the two files) |
| `Jour calendaire` → `date` | Calendar day | — | None | Runs from 2019-01-01 to **2023-09-30 only**; incidents run to 2025-09-30 | Converted to a date |
| `KM planifié` → `planned_km` | Planned km after the year's budget adjustments | — | `0`: 1,536, the empty half of each pair of placeholder rows (see next row) | Written with a French decimal comma (`16315,92`). Planned, not actually run. Unit not documented; very likely car-km (see Findings in the [README](README.md#findings)) | Converted to a number. Summed per line and day |
| `Période Exploitation`, `Type de Jour` | Service period and day type | — | `#` (`Période Exploitation`) and `Non affecté` (`Type de Jour`): 1,536 rows. On 384 days between 2019-01-01 and 2020-06-14, each line has a second row with these codes | Exactly one row in each pair has kilometres, and it is not always the normal row (868 times it is the `#` row), so the `#` rows cannot simply be dropped | The two rows are added together, then these columns are dropped |
| `Tournée` | Run number: 001, 050, 060, 066 or 999 | — | None | Always `001` | Dropped |
| `Année civile`, `Année civile/mois`, `Année civile/semaine`, `Jour de la semaine`, `Mois calendrier` | Date parts | — | None | Repeat `Jour calendaire` | Dropped; `year` and `month` rebuilt from `date` |

The cleaned file has one row per line per day (6,936 rows). It is used in section 5 of
[`modelling.ipynb`](modelling.ipynb) to calculate interruptions per million planned km, by year
and by line. Only incidents on a single line, up to September 2023, can be matched to it.
