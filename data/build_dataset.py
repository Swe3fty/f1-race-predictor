
#======= IMPORT LIBRAIRIES =======#
from pathlib import Path
import fastf1
import pandas as pd

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"

#======= parquet type used -> keeps the data type =======#
OUT = ROOT / "data" / "races.parquet" 
SEASONS = range(2022,2027)

RESULTS_COLS = ["Abbreviation", "DriverId", "TeamName", "TeamColor", "Position", "GridPosition","Time","Status", "Points", "Laps"]

#======= CACHE =======#
CACHE.mkdir(exist_ok=True) # Doesn't touch the cache if exists
fastf1.Cache.enable_cache(CACHE)


rows = []
#======= LOAD ALL YEAR SEASON ======= #
for year in SEASONS :
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    schedule = schedule[schedule["EventDate"] < pd.Timestamp.now()] # Exlcude races after our date for 2026 race

    # ======= LOAD GP & RACE ======= #
    for index, event in schedule.iterrows():
        race = fastf1.get_session(year, event["RoundNumber"], "R")
        race.load(laps=False, telemetry=False, weather=False, messages=False)
        print(year, event["RoundNumber"], event["EventName"], len(race.results))

        results = race.results[RESULTS_COLS].copy()
        results["Year"] = year
        results["Round"] = event["RoundNumber"]
        rows.append(results)

# ==  concatenate all rows== #

df = pd.concat(rows, ignore_index=True)

# == Save to parquet file == #
df.to_parquet(OUT)

    

