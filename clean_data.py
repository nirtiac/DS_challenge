"""
Clean the two STM open datasets.

    1. Metro incidents         -> data/incidents_clean.csv
    2. Planned metro kilometres -> data/planned_km_clean.csv

Run from the project folder:

    python clean_data.py

The functions can also be imported, e.g. in a notebook:

    from clean_data import clean_incidents, clean_planned_km

Column names are translated to English. Category values (causes, symptoms,
line names...) are kept in French so they match the official documentation.

Missing values in the cleaned data:
    - text columns: NaN (np.nan)
    - whole-number and true/false columns: <NA> (pd.NA), because these
      column types cannot hold NaN
Both are empty cells in the CSV. Test for them with pd.isna(), never with
"== None" or "is None".
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_FOLDER = Path(__file__).parent
RAW_FOLDER = PROJECT_FOLDER / "STM challenge Data Scientist"
OUTPUT_FOLDER = PROJECT_FOLDER / "data"

INCIDENTS_FILE = RAW_FOLDER / "Incidents métro_20260707.xls"
PLANNED_KM_FILE = RAW_FOLDER / "Kilométrage métro planifé_20260707.xls"

# Note: both files end in .xls but are really text (CSV) files.


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

INCIDENT_COLUMN_NAMES = {
    "Numero d'incident": "incident_id",
    "Type d'incident": "incident_type",  # T = train, S = station
    "Cause primaire": "primary_cause",
    "Cause secondaire": "secondary_cause",
    "Symptome": "symptom",
    "Ligne": "line",
    "Numéro de tournée": "run_number",
    "Heure de l'incident": "start_time",
    "Heure de reprise": "end_time",
    "Incident en minutes": "duration_bucket",
    "Véhicule": "vehicle",
    "Porte de voiture": "car_doors",
    "Type de matériel": "rolling_stock_at_fault",  # see replace_placeholders()
    "Code de lieu": "location",
    "Dommage matériel": "material_damage",
    "KFS": "emergency_brake",
    "Porte": "door_involved",
    "Urgence métro": "metro_emergency",
    "CAT": "traction_power_cut",
    "Évacuation": "evacuation",
    "Année civile": "year",
    "Année civile/mois": "year_month",
    "Mois calendrier": "month",
    "Jour du mois": "day",
    "Jour de la semaine": "weekday",  # 1 = Monday ... 7 = Sunday
    "Jour calendaire": "calendar_date",
}

FLAG_COLUMNS = [
    "material_damage",
    "emergency_brake",
    "door_involved",
    "metro_emergency",
    "traction_power_cut",
]

# Each duration bucket and the (min, max) number of minutes it covers.
# None means "no upper limit".
DURATION_BUCKETS = {
    "02 min et moins": (0, 2),
    "03 à 04 min": (3, 4),
    "05 à 09 min": (5, 9),
    "10 à 14 min": (10, 14),
    "15 à 19 min": (15, 19),
    "20 à 24 min": (20, 24),
    "25 à 29 min": (25, 29),
    "30 min et plus": (30, None),
}

# The incidents file uses colour names for single lines and numbers for
# incidents on several lines ("Ligne 2, 1"). We convert everything to numbers.
LINE_NAME_TO_NUMBER = {
    "Ligne verte": "1",
    "Ligne orange": "2",
    "Ligne jaune": "4",
    "Ligne bleue": "5",
}
LINE_NUMBER_TO_NAME = {
    "1": "Ligne verte",
    "2": "Ligne orange",
    "4": "Ligne jaune",
    "5": "Ligne bleue",
}
MULTIPLE_LINES = "Plusieurs lignes"

# Words that identify a location which is not a station or a track section
# (garages, workshops, power stations, control centres...).
OTHER_SITE_WORDS = [
    "ARRIERE",
    "ARRIÈRE",
    "ATELIER",
    "GARAGE",
    "POSTE",
    "CENTRE DE CONTRÔLE",
    "CFSPI",
    "BR42",
    "G. H-BOUR",
    "DUVERNAY",  # not a metro station (see also "Duvernay PR")
]


# ---------------------------------------------------------------------------
# Small helper functions (one value in, one value out)
# ---------------------------------------------------------------------------

def time_to_minutes(time_text):
    """Convert a time such as "05:30" or "25:13:00" to minutes after midnight.

    STM uses a "service day": an incident belongs to the day it started in.
    Start times run from 02:00 to 25:59 (2 a.m. the next morning). End times
    keep counting on the same clock, so they go up to 29:xx (5 a.m.).

    Note: this is custom to this specific dataset and is not written to be robust.
    """
    parts = time_text.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    return hours * 60 + minutes


def sort_line_numbers(numbers_text):
    """Sort a list of line numbers written as text: "2, 1" -> "1, 2"."""
    numbers = numbers_text.split(", ")
    numbers.sort()
    return ", ".join(numbers)


def get_line_numbers(line_value):
    """Return the line numbers of an incident, sorted, e.g. "1, 2".

    "Ligne verte" -> "1"
    "Ligne 2, 1"  -> "1, 2"
    Returns a missing value (NaN) when the line is unknown.
    """
    if pd.isna(line_value):
        return np.nan

    if line_value in LINE_NAME_TO_NUMBER:
        return LINE_NAME_TO_NUMBER[line_value]

    if line_value.startswith("Ligne "):
        return sort_line_numbers(line_value.replace("Ligne ", ""))

    # Anything else has no line numbers:
    # - "Non affecté" (not on a line), which add_line_columns() keeps as a category;
    # - "02-avr", a value that Excel turned into a date (2 April): an error.
    return np.nan


def get_line_name(line_numbers):
    """Return the line name ("Ligne verte"...) or "Plusieurs lignes"."""
    if pd.isna(line_numbers):
        return np.nan
    if "," in line_numbers:
        return MULTIPLE_LINES
    return LINE_NUMBER_TO_NAME[line_numbers]


def clean_location(location):
    """Write the lines in a location in one consistent way.

    Stations shared by several lines keep their line suffix, with the
    line numbers sorted:
        "Berri-UQAM - Ligne 2, 1" -> "Berri-UQAM - Ligne 1, 2"
        "Ligne 2, 1"              -> "Ligne 1, 2"
    "Berri L-2" is Berri-UQAM's orange-line platform (all its incidents are
    on line 2), written in a different format:
        "Berri L-2"               -> "Berri-UQAM - Ligne 2"
    """
    location = location.strip()

    if location == "Berri L-2":
        return "Berri-UQAM - Ligne 2"

    if " - Ligne " in location:
        parts = location.split(" - Ligne ")
        station = parts[0]
        lines = parts[1]
        return station + " - Ligne " + sort_line_numbers(lines)

    if location.startswith("Ligne "):
        return "Ligne " + sort_line_numbers(location.replace("Ligne ", ""))

    return location


def remove_line_suffix(location):
    """Remove the line suffix from a station location.

    "Lionel-Groulx - Ligne 1, 2" -> "Lionel-Groulx"
    "Atwater"                    -> "Atwater"
    """
    if " - Ligne " in location:
        return location.split(" - Ligne ")[0]
    return location


def get_location_type(location):
    """Sort a location into one of four types."""
    if location == "Réseau" or location.startswith("Ligne"):
        return "line or network"

    # A station with a line suffix: "Berri-UQAM - Ligne 1, 2".
    # (Checked before the next rule, which also looks for " - ".)
    if " - Ligne " in location:
        return "station"

    # "Atwater/Guy-Concordia" and "Cartier - Henri-Bourassa" are track
    # sections between two stations.
    if "/" in location or " - " in location:
        return "between stations"

    # "Faillon PR", "GARAGE MONTMORENCY", "POSTE DE REDR.JARRY"...
    if location.endswith(" PR"):
        return "other site"
    for word in OTHER_SITE_WORDS:
        if word in location.upper():
            return "other site"

    return "station"


def count_doors(car_doors_value):
    """Count the doors involved, e.g. "1;3;" -> 2. Not recorded -> missing."""
    if pd.isna(car_doors_value):
        return np.nan
    doors = []
    for door in car_doors_value.split(";"):
        if door != "":
            doors.append(door)
    return len(doors)


def duration_matches_bucket(duration, bucket):
    """True if the duration (in minutes) falls inside the duration bucket."""
    low, high = DURATION_BUCKETS[bucket]
    if high is None:
        return duration >= low
    return low <= duration <= high


# ---------------------------------------------------------------------------
# Incident cleaning steps (one DataFrame in, one DataFrame out)
# ---------------------------------------------------------------------------

def load_incidents(path):
    # Read every column as text so pandas does not guess types:
    # it would otherwise mis-read times like "25:10:00" and the "#" values.
    # keep_default_na=False stops pandas from silently turning values such
    # as "#N/A" into missing values: we handle every code ourselves below.
    return pd.read_csv(
        path, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False
    )


def rename_columns(df):
    return df.rename(columns=INCIDENT_COLUMN_NAMES)


def replace_placeholders(df):
    """Replace the placeholder codes with a missing value or a real category.

    According to the data dictionary, "#" means "none": no run, no vehicle,
    no door, no evacuation.
    """
    # "#N/A" is an Excel error ("value not available"), not described in the
    # documentation. It appears in 482 train incidents (both causes) and
    # 377 incidents (symptom). These are real missing values.
    df["primary_cause"] = df["primary_cause"].replace("#N/A", np.nan)
    df["secondary_cause"] = df["secondary_cause"].replace("#N/A", np.nan)
    df["symptom"] = df["symptom"].replace("#N/A", np.nan)

    df["run_number"] = df["run_number"].replace("#", np.nan)
    df["vehicle"] = df["vehicle"].replace("#", np.nan)

    # For car doors, the data contradicts the dictionary: 1,335 incidents
    # flagged as door incidents (door_involved = 1) have "#". So here "#"
    # means "door number not recorded", not "no door".
    df["car_doors"] = df["car_doors"].replace("#", np.nan)

    # For evacuation, "none" is a meaningful answer, so we keep it as a category.
    df["evacuation"] = df["evacuation"].replace("#", "Aucune")

    # "Non affecté" (not assigned) is NOT replaced, because it is not a
    # missing value in either column where it appears:
    #
    # - line: all 103 incidents are at workshops or the control centre,
    #   so it means "not on a line".
    #
    # - rolling_stock_at_fault: the column is filled only when the secondary
    #   cause is "MR-73" or "MPM-10" (plus 4 incidents marked "10" whose
    #   cause is "#N/A"), so it is the type of train *blamed after
    #   analysis*, not the type of train involved. "Non affecté" means
    #   the cause was not the train itself. Like the causes, this column is
    #   only known after the incident and cannot be used to predict it.
    return df


def clear_station_causes(df):
    """Station incidents have no cause.

    The documentation says the cause fields are left empty for station
    incidents, but the file fills them with "Autres" (other). Left as is,
    this makes "Autres" look like the most common cause overall.
    """
    is_station = df["incident_type"] == "S"
    df.loc[is_station, "primary_cause"] = np.nan
    df.loc[is_station, "secondary_cause"] = np.nan

    # Note: 482 train incidents also have no cause ("#N/A" in the file, see
    # replace_placeholders). The documentation says cause analysis can take
    # more than 30 days, but these are spread over all years, so the delay
    # does not explain them.
    return df


def fix_labels(df):
    # Use the spelling from the data dictionary.
    df["secondary_cause"] = df["secondary_cause"].replace(
        "Véhicules de travaux", "Véhicule de travaux"
    )
    return df


def convert_types(df):
    for column in FLAG_COLUMNS:
        df[column] = df[column].astype(int)

    # "Int64" (capital I) is a whole-number type that allows missing values.
    df["run_number"] = pd.to_numeric(df["run_number"]).astype("Int64")
    df["vehicle"] = pd.to_numeric(df["vehicle"]).astype("Int64")

    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df["day"] = df["day"].astype(int)
    df["weekday"] = df["weekday"].astype(int)
    df["calendar_date"] = pd.to_datetime(df["calendar_date"])
    return df


def add_timestamps(df):
    """Build real start and end date-times.

    The year, month, day and weekday columns describe the *service day*.
    "calendar_date" is the real date, which is one day later for incidents
    after midnight. We build the timestamps from the service day plus the
    time, which handles times past 24:00 correctly.

    For train incidents, these times are the start and end of the delay to
    customers, not the start and end of the incident itself.
    """
    df["service_date"] = pd.to_datetime(
        {"year": df["year"], "month": df["month"], "day": df["day"]}
    )

    start_minutes = df["start_time"].apply(time_to_minutes)
    end_minutes = df["end_time"].apply(time_to_minutes)

    df["start_datetime"] = df["service_date"] + pd.to_timedelta(start_minutes, unit="min")
    df["end_datetime"] = df["service_date"] + pd.to_timedelta(end_minutes, unit="min")

    # 60 incidents break the convention: their calendar date is the day after
    # the service date, but their times are written as normal clock times
    # ("02:00" instead of "26:00"). We move their start and end forward one
    # day, so they fall on their calendar date. The duration does not change.
    # Their start time is always exactly "02:00", which is probably a
    # placeholder, so we also flag them.
    starts_before_midnight = start_minutes < 24 * 60
    dates_differ = df["calendar_date"] != df["service_date"]
    df["suspect_start_time"] = starts_before_midnight & dates_differ

    one_day = pd.to_timedelta(1, unit="D")
    suspect = df["suspect_start_time"]
    df.loc[suspect, "start_datetime"] = df.loc[suspect, "start_datetime"] + one_day
    df.loc[suspect, "end_datetime"] = df.loc[suspect, "end_datetime"] + one_day

    # Hour of the service day at the start of the incident, counted from
    # midnight at the start of the service day: 2 to 25 (26 for the 60
    # incidents moved forward above). Unlike the clock hour, this keeps late-night
    # service together: 23:50 -> 23, and 00:10 the next morning -> 24.
    time_into_service_day = df["start_datetime"] - df["service_date"]
    seconds_into_service_day = time_into_service_day.dt.total_seconds()
    df["start_service_hour"] = (seconds_into_service_day // 3600).astype(int)
    return df


def add_duration_columns(df):
    """Add the calculated duration, and compare it with the duration bucket.

    duration_minutes is end time minus start time:
    - for train incidents, it is the delay to customers (per the documentation);
    - for station incidents, it is how long the incident lasted.

    The bucket is not documented. We read it as the delay to train service,
    because station incidents are all in the lowest bucket, whatever their
    real duration. So it is only meaningful for train incidents.
    """
    duration = df["end_datetime"] - df["start_datetime"]
    df["duration_minutes"] = (duration.dt.total_seconds() / 60).astype(int)

    bucket_minimums = {}
    for bucket, (low, high) in DURATION_BUCKETS.items():
        bucket_minimums[bucket] = low
    df["bucket_min_minutes"] = df["duration_bucket"].map(bucket_minimums)

    # For train incidents: does the bucket agree with the start and end times?
    # (It does for about 98% of them; when it does not, the times are almost
    # always longer than the bucket.) Left empty for station incidents.
    matches = []
    for incident_type, minutes, bucket in zip(
        df["incident_type"], df["duration_minutes"], df["duration_bucket"]
    ):
        if incident_type == "T":
            matches.append(duration_matches_bucket(minutes, bucket))
        else:
            matches.append(pd.NA)
    df["bucket_matches_times"] = pd.Series(matches, index=df.index, dtype="boolean")
    return df


def add_line_columns(df):
    """Standardise the line.

    line            -> "Ligne verte", "Ligne orange", ... or "Plusieurs lignes"
                       (same names as the planned km file, for joining),
                       or "Non affecté" for incidents not on a line
    lines_involved  -> all line numbers, sorted, e.g. "1, 2"
    number_of_lines -> how many lines were affected
    """
    # Incidents at workshops and the control centre are not on any line.
    not_on_a_line = df["line"] == "Non affecté"

    df["lines_involved"] = df["line"].apply(get_line_numbers)
    df["line"] = df["lines_involved"].apply(get_line_name)
    df["number_of_lines"] = (df["lines_involved"].str.count(",") + 1).astype("Int64")

    df.loc[not_on_a_line, "line"] = "Non affecté"
    df.loc[not_on_a_line, "number_of_lines"] = 0
    return df


def add_location_columns(df):
    """Standardise the location, and add its type and the station affected.

    affected_station is the station name without the line suffix, so all
    incidents at one station can be grouped together. It is only filled
    when the location is a station; otherwise it is missing.
    """
    df["location"] = df["location"].apply(clean_location)
    df["location_type"] = df["location"].apply(get_location_type)

    stations = []
    for location, location_type in zip(df["location"], df["location_type"]):
        if location_type == "station":
            stations.append(remove_line_suffix(location))
        else:
            stations.append(np.nan)
    df["affected_station"] = stations
    return df


def add_door_count(df):
    door_counts = df["car_doors"].apply(count_doors)
    df["number_of_doors"] = door_counts.astype("Int64")
    return df


def remove_duplicates(df):
    """Remove rows that are identical except for their incident number.

    There are 5 such pairs, with consecutive or nearly consecutive incident
    numbers (e.g. T28102213 and T28102214). They look like the same incident
    entered twice. We keep the first one.
    """
    all_columns_except_id = []
    for column in df.columns:
        if column != "incident_id":
            all_columns_except_id.append(column)

    rows_before = len(df)
    df = df.drop_duplicates(subset=all_columns_except_id, keep="first")
    print(f"  Removed {rows_before - len(df)} duplicate rows")
    return df


def drop_unneeded_columns(df):
    # Nothing is lost by dropping these columns:
    # - year_month ("janv-19") repeats year and month
    # - day is part of service_date
    # - start_time / end_time (the raw text, e.g. "25:10:00") are now
    #   start_datetime / end_datetime, plus start_service_hour
    # - calendar_date is the date part of start_datetime
    return df.drop(columns=["year_month", "day", "start_time", "end_time", "calendar_date"])


def clean_incidents(path=INCIDENTS_FILE):
    """Run every cleaning step on the incidents file, in order."""
    df = load_incidents(path)
    df = rename_columns(df)
    df = replace_placeholders(df)
    df = clear_station_causes(df)
    df = fix_labels(df)
    df = convert_types(df)
    df = add_timestamps(df)
    df = add_duration_columns(df)
    df = add_line_columns(df)
    df = add_location_columns(df)
    df = add_door_count(df)
    df = remove_duplicates(df)
    df = drop_unneeded_columns(df)
    return df


# ---------------------------------------------------------------------------
# Planned kilometres
# ---------------------------------------------------------------------------

def clean_planned_km(path=PLANNED_KM_FILE):
    """Return the planned kilometres per line per day.

    Notes on the raw file:
    - It is comma-separated (the incidents file uses semicolons).
    - Numbers use a French decimal comma: "16315,92".
    - On 384 days between Jan 2019 and Jun 2020, each line has two rows:
      a normal row and a row with period "#" and day type "Non affecté".
      Exactly one of the two has kilometres (the other has 0), and it is
      not always the normal row, so we add the two rows together.
    - It only covers 2019-01-01 to 2023-09-30, while incidents go to 2025.
    """
    # Same reading options as the incidents file: everything as text, and no
    # automatic conversion of codes to missing values.
    df = pd.read_csv(path, sep=",", encoding="utf-8-sig", dtype=str, keep_default_na=False)

    df["planned_km"] = df["KM planifié"].str.replace(",", ".").astype(float)
    df["date"] = pd.to_datetime(df["Jour calendaire"])
    df["line"] = df["Ligne"]

    daily = df.groupby(["line", "date"], as_index=False)["planned_km"].sum()
    daily["year"] = daily["date"].dt.year
    daily["month"] = daily["date"].dt.month
    return daily


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------

def main():
    OUTPUT_FOLDER.mkdir(exist_ok=True)

    print("Cleaning incidents...")
    incidents = clean_incidents()
    incidents.to_csv(OUTPUT_FOLDER / "incidents_clean.csv", index=False)
    print(f"  Saved {len(incidents)} incidents")

    print("Cleaning planned kilometres...")
    planned_km = clean_planned_km()
    planned_km.to_csv(OUTPUT_FOLDER / "planned_km_clean.csv", index=False)
    print(f"  Saved {len(planned_km)} line-days")
    print(f"  Covers {planned_km['date'].min().date()} to {planned_km['date'].max().date()}")


if __name__ == "__main__":
    main()
