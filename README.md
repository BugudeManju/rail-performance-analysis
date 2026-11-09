# Train Punctuality & Run-Time Analysis: Milton Keynes → London Euston

Analysis of train performance on the Milton Keynes Central to London Euston stopping service, using Python (Pandas, NumPy, Matplotlib).

I travel on this route, so I wanted to understand why peak trains into London are often late, and whether the timetable itself is part of the problem.

## What the notebook does
1. **Cleans** the train movement data: removes duplicates, converts times, calculates lateness at each station
2. **Measures punctuality** at Euston: On Time (< 1 min), Time to 3 and PPM (< 5 min), for peak vs off-peak and by month
3. **Finds where delay builds up** along the route
4. **Compares planned vs actual run times** to find unachievable sections (median, 90th percentile, % achieved)
5. **Ranks services** by total delay minutes
6. **Monte-Carlo simulation** (10,000 runs): checked against the real data first, then used to test adding time to the timetable

## Key findings
| | Off-peak | Peak |
|---|---|---|
| On Time (< 1 min) | 84.5% | **13.5%** |
| PPM (< 5 min) | 97.7% | 90.8% |

- **3 peak run times are unachievable.** Watford → Harrow is planned at 7 minutes but usually takes 8, and only 5% of peak trains achieve it.
- **5 of 39 services cause about 28% of weekday delay minutes.** The 07:46 starts late from Milton Keynes, so it has a different cause.
- **Simulation:** adding 2 minutes to two sections raises peak On Time from about **13% to 62%**. The trade-off is a longer advertised journey.

## Data
The data is **simulated**. It's in the same format as Network Rail's train movement records: planned and actual arrival and departure times at each station, July–October 2026, about 4,600 journeys. Real feeds need a registered account. `data/generate_data.py` creates the dataset, including peak congestion, autumn leaf-fall, disruption days and missing or duplicate records.

## How to run
```
pip install -r requirements.txt
jupyter notebook analysis.ipynb
```

## Limitations and next steps
- The data is simulated; the next step is to run the same analysis on real Network Rail data.
- On Time is measured at the destination only.
- The simulation doesn't include knock-on delay between trains.

*I used AI tools (Claude) to help with parts of the code; the analysis and conclusions were reviewed and run by me.*
