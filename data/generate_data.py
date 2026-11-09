"""
Generate a realistic, TRUST-style train movement dataset for the
Milton Keynes Central -> London Euston stopping service (West Coast Main Line).

Why simulated data?
Network Rail's real train movement feeds (TRUST / Historical Service Performance)
need a registered account. This script produces data with the same structure
(one row per train per station, planned vs actual times) so the analysis
pipeline can later be pointed at real data with minimal changes.

Behaviours deliberately built in (so the analysis has something real to find):
  * Some sections have planned run times that are too tight for peak traffic
  * Peak-hour congestion approaching London, longer dwell times at busy stations
  * Late starts on a few specific services (e.g. late-arriving inbound units)
  * Knock-on (reactionary) delay when the train in front is late
  * Occasional disruption days (e.g. signalling faults) and one-off train incidents
  * Autumn leaf-fall: slower running in October
  * Messy records: missing actual times, duplicate rows

Run:  python src/generate_data.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
START, END = "2026-07-01", "2026-10-31"
OUT = Path(__file__).resolve().parent / "train_movements.csv"

# Station calling pattern (code, name)
STATIONS = [
    ("MKC", "Milton Keynes Central"), ("LBZ", "Leighton Buzzard"), ("TRI", "Tring"),
    ("BKM", "Berkhamsted"), ("HML", "Hemel Hempstead"), ("KGL", "Kings Langley"),
    ("WFJ", "Watford Junction"), ("HRW", "Harrow & Wealdstone"), ("WMB", "Wembley Central"),
    ("EUS", "London Euston"),
]
# Planned section run times (min) and the "true" typical run time off-peak / extra in peak
PLANNED_RUN = [7, 8, 4, 4, 4, 4, 7, 4, 9]
TRUE_RUN    = [6.6, 7.5, 3.7, 3.7, 3.6, 4.1, 7.2, 3.7, 8.9]
PEAK_EXTRA  = [0.1, 0.1, 0.0, 0.1, 0.1, 0.2, 0.8, 0.1, 0.9]   # congestion near London
AUTUMN_SECT = [0.4, 0.5, 0.3, 0.2, 0.2, 0.1, 0.0, 0.0, 0.0]   # leaf-fall on rural sections
PLANNED_DWELL = 1.0                                            # minutes at each intermediate stop
DWELL_BUSY = {"WFJ": 0.6, "HRW": 0.3, "HML": 0.2}               # extra peak dwell at busy stations

# Timetable: departures from MKC (half-hourly all day, extra trains in the morning peak)
def build_timetable():
    times = list(pd.date_range("05:46", "22:16", freq="30min").time)
    times += list(pd.date_range("06:31", "08:31", freq="30min").time)  # peak extras
    times = sorted(times)
    tt = pd.DataFrame({"dep_time": times})
    tt["headcode"] = [f"2K{i:02d}" for i in range(1, len(tt) + 1)]
    tt["peak_extra"] = tt.dep_time.map(lambda t: t.minute == 31 or t.minute == 1)
    return tt

# Services with a chronic late-start problem (late inbound unit / crew changes)
PROBLEM_STARTS = {"2K08": 2.5, "2K10": 1.5, "2K12": 2.0}

def is_peak(t, weekday):
    mins = t.hour * 60 + t.minute
    return weekday < 5 and (390 <= mins <= 570 or 960 <= mins <= 1110)  # 06:30-09:30, 16:00-18:30

def main():
    rng = np.random.default_rng(SEED)
    tt = build_timetable()
    days = pd.date_range(START, END, freq="D")
    disruption_days = set(rng.choice(days, size=5, replace=False))
    rows = []
    for day in days:
        wd = day.weekday()
        autumn = day.month == 10
        disrupted = day in disruption_days
        dis_start = rng.integers(7 * 60, 17 * 60) if disrupted else None
        prev_arr_delay = np.zeros(len(STATIONS))      # train in front's lateness per station
        prev_dep_mins = None
        for _, svc in tt.iterrows():
            if wd >= 5 and svc.peak_extra:
                continue                               # no peak extras at weekends
            dep_mins = svc.dep_time.hour * 60 + svc.dep_time.minute
            peak = is_peak(svc.dep_time, wd)
            headway = dep_mins - prev_dep_mins if prev_dep_mins is not None else 60
            # start delay
            delay = max(0, rng.exponential(0.4) - 0.2)
            if svc.headcode in PROBLEM_STARTS and wd < 5:
                delay += rng.gamma(2, PROBLEM_STARTS[svc.headcode] / 2)
            # one-off incidents on individual trains (door fault, passenger assistance...)
            incident_sect = rng.integers(0, 9) if rng.random() < 0.06 else -1
            planned = day + pd.Timedelta(minutes=dep_mins)
            plan_t = planned
            delays_here = np.zeros(len(STATIONS))
            for i, (code, name) in enumerate(STATIONS):
                if i == 0:
                    p_arr, p_dep = None, plan_t
                    a_arr, a_dep = None, plan_t + pd.Timedelta(minutes=delay)
                else:
                    s = i - 1
                    run = TRUE_RUN[s] + (PEAK_EXTRA[s] if peak else 0) + (AUTUMN_SECT[s] if autumn else 0)
                    run = max(PLANNED_RUN[s] * 0.85, rng.normal(run, 0.2 + 0.05 * run))
                    # reactionary delay: close behind a late train
                    if headway <= 20 and prev_arr_delay[i] > 3:
                        run += 0.12 * (prev_arr_delay[i] - 3) * rng.random()
                    if s == incident_sect:
                        run += rng.gamma(2, 2.5)
                    # disruption window (~2.5 hours)
                    if disrupted and dis_start <= dep_mins + s * 5 <= dis_start + 150 and s >= 5:
                        run += rng.gamma(2, 6)
                    p_arr = plan_t + pd.Timedelta(minutes=PLANNED_RUN[s])
                    a_arr = a_dep + pd.Timedelta(minutes=run)
                    if code == "EUS":
                        p_dep, a_dep = None, None
                    else:
                        p_dep = p_arr + pd.Timedelta(minutes=PLANNED_DWELL)
                        dwell = rng.gamma(4, 0.18) + (DWELL_BUSY.get(code, 0) if peak else 0)
                        # a train never departs before its planned time
                        a_dep = max(a_arr + pd.Timedelta(minutes=dwell), p_dep)
                    plan_t = p_dep if p_dep is not None else p_arr
                    delays_here[i] = (a_arr - p_arr).total_seconds() / 60
                rows.append({
                    "service_date": day.date(), "headcode": svc.headcode,
                    "train_id": f"{svc.headcode}{day:%m%d}",
                    "origin_dep_time": svc.dep_time.strftime("%H:%M"),
                    "stop_seq": i + 1, "station_code": code, "station_name": name,
                    "planned_arr": p_arr, "actual_arr": a_arr,
                    "planned_dep": p_dep, "actual_dep": a_dep,
                })
            prev_arr_delay = delays_here
            prev_dep_mins = dep_mins

    df = pd.DataFrame(rows)
    for c in ["planned_arr", "actual_arr", "planned_dep", "actual_dep"]:
        df[c] = pd.to_datetime(df[c]).dt.round("s")
    # --- make it messy, like real feeds ---
    miss = rng.random(len(df)) < 0.012                 # unrecorded movements
    df.loc[miss & df.actual_arr.notna(), "actual_arr"] = pd.NaT
    df = pd.concat([df, df.sample(frac=0.005, random_state=SEED)])  # duplicate messages
    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df):,} rows -> {OUT}")

if __name__ == "__main__":
    main()
