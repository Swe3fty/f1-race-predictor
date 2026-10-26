
#======= IMPORT LIBRAIRIES =======#
from pathlib import Path
import time
import fastf1
import pandas as pd
from fastf1.ergast import Ergast
from fastf1.exceptions import ErgastInvalidRequestError, DataNotLoadedError

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"

#======= parquet type used -> keeps the data type =======#
OUT = ROOT / "data" / "races.parquet" 
SEASONS = range(2022,2027)

RESULTS_COLS = ["Abbreviation", "DriverId", "TeamName", "TeamColor", "Position", "GridPosition","Time","Status", "Points", "Laps"]

#======= CACHE =======#
CACHE.mkdir(exist_ok=True) # Doesn't touch the cache if exists
fastf1.Cache.enable_cache(CACHE)


#======= WEATHER (only what is known before the start) =======#
def weather_at_start(weather: pd.DataFrame) -> dict:
    """weather = race.weather_data (one row per minute) -> {column_name: value} for the whole race"""
    before_start = weather[weather["Time"] < pd.Timedelta(10, unit="min")] # first 10 min before the start
    rainfall = before_start["Rainfall"].any()
    temp = before_start["TrackTemp"].mean()

    return {"RainAtStart" : rainfall, "TrackTempAtStart" : temp}


#======= QUALIFYING (Jolpica/Ergast, the F1 archive is blocked since oct. 2026) =======#
ERGAST = Ergast()

def quali_gap(quali: pd.DataFrame) -> pd.Series:
    """quali = Ergast qualifying results (Q1, Q2, Q3 as Timedelta, NaT if not run) -> one gap value per driver
    Using gap instead of time because the model would just understand the type of track long short and be based on that
    
    """
    best_time_pilot_seconds = quali[["Q1","Q2","Q3"]].apply(pd.to_timedelta)
                       
    best_time_pilot_seconds = best_time_pilot_seconds.min(axis=1).dt.total_seconds()
    best_time_quali = best_time_pilot_seconds.min()
    gap_percentage = (best_time_pilot_seconds - best_time_quali) / best_time_quali * 100

    return gap_percentage


def get_quali(year: int, rnd: int) -> pd.DataFrame:
    """Jolpica sometimes answers 429 Too Many Requests -> wait and retry"""
    for attempt in range(5):
        try:
            return ERGAST.get_qualifying_results(season=year, round=rnd).content[0]
        except ErgastInvalidRequestError:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Jolpica still refuses qualifying {year} round {rnd}")


rows = []
#======= LOAD ALL YEAR SEASON ======= #
for year in SEASONS :
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    schedule = schedule[schedule["EventDate"] < pd.Timestamp.now()] # Exlcude races after our date for 2026 race

    # ======= LOAD GP & RACE ======= #
    for index, event in schedule.iterrows():
        race = fastf1.get_session(year, event["RoundNumber"], "R")
        race.load(laps=False, telemetry=False, weather=True, messages=False)

        results = race.results[RESULTS_COLS].copy()
        results["Year"] = year
        results["Round"] = event["RoundNumber"]

        try :
            weather = weather_at_start(race.weather_data)
        except DataNotLoadedError:
            weather = {"RainAtStart" : None, "TrackTempAtStart" : None}

        results = results.assign(**weather) # Transform Dict into key=value

        # Get qualifying times
        quali = get_quali(year, event["RoundNumber"])
        time.sleep(1) # Jolpica allows 4 req/s and FastF1 already sends at 4/s
        quali["QualiGap"] = quali_gap(quali)
        quali = quali[["driverId", "QualiGap"]].rename(columns={"driverId": "DriverId"})
        results = results.merge(quali, on="DriverId", how="left") # NaN if the driver set no time
        rows.append(results)

# ==  concatenate all rows== #

df = pd.concat(rows, ignore_index=True)


df = df[["Year","Round","Abbreviation", "DriverId", "TeamName", "TeamColor","GridPosition","QualiGap","Position","Time","Points","Laps","Status","RainAtStart","TrackTempAtStart"]]

# == Save to parquet file == #
df.to_parquet(OUT)

    

