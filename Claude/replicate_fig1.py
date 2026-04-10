"""
replicate_fig1.py
=================
Replication code for Figure 1 (five-panel combined figure) and the
in-text statistics cited in the Venezuela deportation note.

Figures produced
----------------
  fig_combined.pdf / .png  — the five-panel stacked figure

Text statistics computed
------------------------
  (a) Total interior Venezuelan removals, Jan. 16 – Mar. 10, 2026
  (b) Daily rate Jan. 16 – Mar. 10 vs. daily rate Jul. 1 – Dec. 9, 2025
      → cited as "38% more per day than in the latter half of 2025"
      (Dec. 10–31 excluded: flights were paused; see footnote 2)
      Alt-calc: if Dec. 10–31 included → ~47% increase (footnote 2)
  (c) Daily rate in the first three weeks after Jan. 16 (Jan. 16 – Feb. 5)
      → cited as "an average of 120 per day"
  (d) Peak three-week (21-day) rolling window in calendar year 2025
      → cited as "58% higher than the peak three-week period in all of 2025"

Key definitions
---------------
  Interior removal : the removed individual's Anonymized Identifier appears
                     in the ERO arrests files (FY23–FY26).  This indicates
                     the person was arrested in the interior of the US by
                     ICE Enforcement and Removal Operations (ERO), not
                     encountered at the border.
  Latter half 2025 : Jul. 1 – Dec. 9, 2025.  Dec. 10–31 is excluded
                     because deportation flights to Venezuela were paused
                     during that period (footnote 2 in the note).  Including
                     Dec. 10–31 would lower the baseline rate and raise the
                     apparent increase to ~47% (the alt-calc in footnote 2).

Data sources (FOIA release, UC Berkeley Deportation Data Project)
-----------------------------------------------------------------
  Arrests  : 2026-ICLI-00005_Arrests_{FY}_20260311_Redacted.xlsx  (FY23–FY26)
  Removals : 2026-ICLI-00005_Removals_{FY}_20260311_Redacted.csv  (FY23–FY26)
  Detention: data/inputs/detention-stays-latest.xlsx

TPS eligibility classification (panel 5, replicating DK_TPS.do)
----------------------------------------------------------------
  TPS 2021  : entry_date ≤ Mar. 9, 2021   AND no prior deportation
  TPS 2023  : Mar. 9, 2021 < entry_date ≤ Jul. 31, 2023  AND no prior deportation
  Ineligible: entry_date > Jul. 31, 2023  OR prior deportation
  Unknown   : entry_date missing

  Prior deportation proxy: person appears more than once in Venezuelan
  interior removals (matching Stata do-file; the "Prior Deport Yes No"
  column is NOT used because the Stata code does not use it).

  Denominator for panel 5 percentage: all interior Venezuelan removals
  including those with missing entry dates (Unknown).
"""

import warnings; warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.transforms import blended_transform_factory
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
INDIR  = ROOT / "data" / "inputs"
ARRDIR = INDIR / "2026-ICLI-00005_Arrests_Redacted"
REMDIR = INDIR / "2026-ICLI-00005_Removals_Redacted"
FIGDIR = Path("/Users/dorothykronick/ddp/figures")

# ── date constants ─────────────────────────────────────────────────────────────
START = pd.Timestamp("2024-08-01")   # figure x-axis start
END   = pd.Timestamp("2026-03-10")   # last day in the data

JAN20 = pd.Timestamp("2025-01-20")   # Trump inauguration
OCT3  = pd.Timestamp("2025-10-03")   # Supreme Court TPS ruling (Noem v. Bhattarai)
JAN3  = pd.Timestamp("2026-01-03")   # Operation Absolute Resolve announced
JAN16 = pd.Timestamp("2026-01-16")   # First deportation flight to VZ after Jan. 3
FEB5  = pd.Timestamp("2026-02-05")   # End of first 3 weeks after Jan. 16 (21 days)

JUL1  = pd.Timestamp("2025-07-01")   # Start of "latter half of 2025" comparison period
DEC9  = pd.Timestamp("2025-12-09")   # End of "latter half of 2025" comparison period
# Dec 10–31 is EXCLUDED because deportation flights to Venezuela were paused
# during that period (see footnote 2 in the note).  If Dec 10–31 were included,
# the baseline rate would be lower and the post-Jan.-16 increase would appear
# larger (~47% instead of ~38%).
DEC31 = pd.Timestamp("2025-12-31")   # Alt-calc end (footnote 2 counterfactual)

TPS2021_CUT = pd.Timestamp("2021-03-09")   # TPS 2021 entry cutoff
TPS2023_CUT = pd.Timestamp("2023-07-31")   # TPS 2023 entry cutoff

# Panel 5 settings
PCT_MIN_DENOM = 50    # mask weeks with < 50 total interior VZ removals (too noisy)

# ── event-line specs ───────────────────────────────────────────────────────────
# Each tuple: (date, display label, linestyle, color)
# Panels 1–4: inauguration + Operation Absolute Resolve only
VLINES_MAIN = [
    (JAN20, "Jan.\u00a020,\u00a02025", ":",  "#888888"),
    (JAN3,  "Jan.\u00a03,\u00a02026",  "-.", "#CC3333"),
]
# Panel 5 (TPS %): all three events; TPS ruling in red, Jan. 3 very faint
VLINES_TPS = [
    (JAN20, "Jan.\u00a020,\u00a02025", ":",  "#888888"),
    (OCT3,  "Oct.\u00a03,\u00a02025",  "--", "#CC3333"),
    (JAN3,  "Jan.\u00a03,\u00a02026",  "-.", "#CCCCCC"),
]

VEN      = "#4C9BE8"   # blue  — Venezuela
MEX      = "#4CAF82"   # green — all other nationalities
DARK_BLUE = "#1A5296"  # dark blue — period-average reference lines

# ── figure geometry ────────────────────────────────────────────────────────────
FW  = 3.3   # figure width (inches)
PH  = 2.2   # per-panel height (inches)
GAP = 0.04  # fractional gap between panels
FS  = 7.5   # base font size (points)

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════

# ── ERO arrest IDs (interior filter) ──────────────────────────────────────────
# Anyone whose Anonymized Identifier appears here was arrested by ERO in the
# interior of the US; this is used to distinguish interior from border removals.
print("Loading arrests …")
arr_dfs = []
for fy in ["FY23", "FY24", "FY25", "FY26"]:
    df = pd.read_excel(
        ARRDIR / f"2026-ICLI-00005_Arrests_{fy}_20260311_Redacted.xlsx",
        skiprows=6, engine="openpyxl",
        usecols=["Anonymized Identifier", "Apprehension Date", "Citizenship Country"]
    )
    arr_dfs.append(df)
arrests_all = pd.concat(arr_dfs, ignore_index=True)
arrests_all["Apprehension Date"] = (
    pd.to_datetime(arrests_all["Apprehension Date"]).dt.normalize()
)
ero_ids = set(arrests_all["Anonymized Identifier"])
print(f"  {len(ero_ids):,} unique ERO IDs (interior filter)")

# ── Removals ──────────────────────────────────────────────────────────────────
print("Loading removals …")
rem_dfs = []
for fy in ["FY23", "FY24", "FY25", "FY26"]:
    df = pd.read_csv(
        REMDIR / f"2026-ICLI-00005_Removals_{fy}_20260311_Redacted.csv",
        skiprows=6, low_memory=False
    )
    rem_dfs.append(df)
rem = pd.concat(rem_dfs, ignore_index=True)
# Drop exact duplicate rows (can occur at fiscal-year file boundaries)
rem = rem.drop_duplicates()

# Interior removals: keep only rows whose Anonymized Identifier appears
# in the ERO arrests file — this is the interior filter, excluding border
# encounters.  All text statistics below use this interior subset.
interior = rem[rem["Anonymized Identifier"].isin(ero_ids)].copy()
interior["date"] = pd.to_datetime(interior["Departed Date"])
interior["week"] = (interior["date"]
                    - pd.to_timedelta(interior["date"].dt.dayofweek, unit="d"))

# Separate Venezuelan and non-Venezuelan interior removals
ven_rem   = interior[interior["Citizenship Country"] == "VENEZUELA"]
other_rem = interior[interior["Citizenship Country"] != "VENEZUELA"]

# ══════════════════════════════════════════════════════════════════════════════
# 2. TEXT CALCULATIONS
#    These back up statistics cited in the note's text.
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Text statistics ──────────────────────────────────────────────────")

# (a) Total interior Venezuelan removals, Jan. 16 – Mar. 10, 2026
#     "Between January 16 … and March 10 … ICE deported 2,956 Venezuelans
#      from the interior of the United States"
jan16_mar10 = ven_rem[
    (ven_rem["date"] >= JAN16) & (ven_rem["date"] <= END)
]
n_jan16_mar10 = len(jan16_mar10)
days_jan16_mar10 = (END - JAN16).days + 1     # inclusive day count
rate_jan16_mar10 = n_jan16_mar10 / days_jan16_mar10
print(f"\n(a) Interior VZ removals Jan. 16 – Mar. 10:")
print(f"    N = {n_jan16_mar10:,}  over {days_jan16_mar10} days  ({rate_jan16_mar10:.1f}/day)")

# (b) Latter-half-of-2025 baseline: Jul. 1 – Dec. 9, 2025
#     "38% more per day than in the latter half of 2025"
#     Dec. 10–31 is excluded because deportation flights to Venezuela were
#     paused during that period (see footnote 2 in the note).
latter_half = ven_rem[
    (ven_rem["date"] >= JUL1) & (ven_rem["date"] <= DEC9)
]
days_latter = (DEC9 - JUL1).days + 1
rate_latter = len(latter_half) / days_latter
pct_increase_ab = (rate_jan16_mar10 / rate_latter - 1) * 100
print(f"\n(b) Interior VZ removals Jul. 1 – Dec. 9, 2025 (latter half baseline):")
print(f"    N = {len(latter_half):,}  over {days_latter} days  ({rate_latter:.1f}/day)")
print(f"    Jan.16–Mar.10 rate is {pct_increase_ab:.0f}% higher than latter-half-2025 rate")

# Footnote 2 alternative calculation: if Dec. 10–31 were included in the baseline
# (flights paused → fewer removals → lower baseline rate → larger apparent increase)
latter_half_alt = ven_rem[
    (ven_rem["date"] >= JUL1) & (ven_rem["date"] <= DEC31)
]
days_latter_alt = (DEC31 - JUL1).days + 1
rate_latter_alt = len(latter_half_alt) / days_latter_alt
pct_increase_alt = (rate_jan16_mar10 / rate_latter_alt - 1) * 100
print(f"    [Footnote 2 alt-calc — Jul. 1–Dec. 31 baseline: {rate_latter_alt:.1f}/day → "
      f"{pct_increase_alt:.0f}% increase (cited in note as ~47%)]")

# (c) First three weeks after Jan. 16 (Jan. 16 – Feb. 5, 21 days)
#     "an average of 120 per day"
first3wks = ven_rem[
    (ven_rem["date"] >= JAN16) & (ven_rem["date"] <= FEB5)
]
n_first3wks   = len(first3wks)
rate_first3wks = n_first3wks / 21
print(f"\n(c) Interior VZ removals Jan. 16 – Feb. 5 (first 3 weeks, 21 days):")
print(f"    N = {n_first3wks:,}  ({rate_first3wks:.1f}/day)")

# (d) Peak 21-day rolling window in calendar-year 2025 (before Jan. 16)
#     "58% higher than the peak three-week period in all of 2025"
#
#     Method: build a daily time series of interior VZ removals for all of
#     2025 (Jan. 1 – Jan. 15, 2026), then use a 21-day rolling sum to find
#     the window with the highest total.
cal2025_range = pd.date_range("2025-01-01", JAN16 - pd.Timedelta(days=1), freq="D")
daily_2025 = (
    ven_rem[ven_rem["date"].isin(cal2025_range)]
    .groupby("date").size()
    .reindex(cal2025_range, fill_value=0)
)
rolling_21 = daily_2025.rolling(21).sum()
peak_end   = rolling_21.idxmax()
peak_start = peak_end - pd.Timedelta(days=20)
peak_total = int(rolling_21.max())
rate_peak  = peak_total / 21
pct_increase_cd = (rate_first3wks / rate_peak - 1) * 100
print(f"\n(d) Peak 21-day window in 2025:")
print(f"    {peak_start.date()} – {peak_end.date()}: N = {peak_total}  ({rate_peak:.1f}/day)")
print(f"    First-3-weeks rate is {pct_increase_cd:.0f}% higher than this peak")
print("─────────────────────────────────────────────────────────────────────\n")

# ══════════════════════════════════════════════════════════════════════════════
# 3. WEEKLY TIME GRID (panels 1–4)
#    Complete Monday–Sunday weeks only; partial final week dropped.
# ══════════════════════════════════════════════════════════════════════════════
WKS = pd.date_range(START, END, freq="W-MON")
WKS = WKS[WKS + pd.Timedelta(days=6) <= END]

def weekly(df, col="week"):
    """Weekly counts reindexed to the full WKS grid; missing weeks = 0."""
    return (df.groupby(col).size().rename("n")
              .reindex(WKS, fill_value=0).reset_index()
              .rename(columns={"index": col, col: "week"}))

ven_wk   = weekly(ven_rem)
other_wk = weekly(other_rem)

# Panel 3: Venezuelan ICE arrests by week
ven_arr = arrests_all[
    (arrests_all["Citizenship Country"] == "VENEZUELA") &
    (arrests_all["Apprehension Date"] >= START) &
    (arrests_all["Apprehension Date"] <= END)
].copy()
ven_arr["week"] = (ven_arr["Apprehension Date"]
                   - pd.to_timedelta(ven_arr["Apprehension Date"].dt.dayofweek, unit="d"))
arr_wk = weekly(ven_arr, "week")

# ══════════════════════════════════════════════════════════════════════════════
# 4. TPS ELIGIBILITY CLASSIFICATION (panel 5)
#
#    Replicates DK_TPS.do.  Key choices:
#      - Prior deportation proxy: a person who appears more than once in the
#        Venezuelan interior removals dataset is treated as having a prior
#        deportation and is therefore TPS-ineligible.  (Nine people appear
#        more than 3 times; they are dropped.)
#      - Denominator: all interior Venezuelan removals, including those with
#        a missing entry date (Unknown).
#      - Week grid: anchored to Oct. 3, 2025 (the TPS ruling date), so that
#        Oct. 3 is always the first day of its week.  This prevents the ruling
#        date from being split across two weeks.
# ══════════════════════════════════════════════════════════════════════════════
ven_int = interior[interior["Citizenship Country"] == "VENEZUELA"].copy()
ven_int["entry_date"] = pd.to_datetime(ven_int["Entry Date"], errors="coerce")

# Count appearances per person; use as prior-deportation proxy
obs_counts = ven_int["Anonymized Identifier"].value_counts()
ven_int["obs_perperson"] = ven_int["Anonymized Identifier"].map(obs_counts)
ven_int = ven_int[ven_int["obs_perperson"] <= 3].copy()   # drop 9 high-frequency persons

def tps_cat(row):
    ed  = row["entry_date"]
    obs = row["obs_perperson"]
    if pd.isna(ed):       return "Unknown"      # missing entry date
    if obs > 1:           return "Ineligible"   # prior deportation proxy
    if ed <= TPS2021_CUT: return "TPS 2021"
    if ed <= TPS2023_CUT: return "TPS 2023"
    return "Ineligible"

ven_int["tps"] = ven_int.apply(tps_cat, axis=1)

# Custom week grid anchored to Oct. 3, 2025
def custom_week_start(date_series):
    """Floor each date to the nearest OCT3 + k*7 boundary."""
    delta = (date_series - OCT3).dt.days
    return OCT3 + pd.to_timedelta((delta // 7) * 7, unit="D")

k_min = int((JAN20 - OCT3).days // 7) - 1
k_max = int((END   - OCT3).days // 7) + 1
all_custom_wks = pd.DatetimeIndex(
    [OCT3 + pd.Timedelta(days=7 * k) for k in range(k_min, k_max + 1)]
)
PCT_WKS = all_custom_wks[
    (all_custom_wks >= JAN20) &
    (all_custom_wks + pd.Timedelta(days=6) <= pd.Timestamp("2026-03-09"))
]

ven_int["week_c"] = custom_week_start(ven_int["date"])

# Weekly totals (all VZ, including Unknown — used as denominator and for masking)
wk_total_c = ven_int.groupby("week_c").size().reindex(PCT_WKS, fill_value=0)
# Weekly numerator: TPS 2023-eligible only
wk_tps23_c = (ven_int[ven_int["tps"] == "TPS 2023"]
              .groupby("week_c").size().reindex(PCT_WKS, fill_value=0))
# Also computed for CSV output (denominator excluding Unknown)
ven_known  = ven_int[ven_int["tps"] != "Unknown"]
wk_denom_c = ven_known.groupby("week_c").size().reindex(PCT_WKS, fill_value=0)

pct_2023_c = wk_tps23_c / wk_total_c.replace(0, np.nan) * 100

pct_plot_c = pct_2023_c.copy()
pct_plot_c[wk_total_c < PCT_MIN_DENOM] = np.nan   # suppress low-denominator weeks

# Weighted period averages (sum of numerators / sum of denominators)
pre_mask_pct  = PCT_WKS < OCT3
post_mask_pct = PCT_WKS >= OCT3
pre_avg  = wk_tps23_c[pre_mask_pct].sum()  / wk_total_c[pre_mask_pct].sum()  * 100
post_avg = wk_tps23_c[post_mask_pct].sum() / wk_total_c[post_mask_pct].sum() * 100
print(f"TPS 2023%: pre-Oct. 3 mean = {pre_avg:.1f}%,  post-Oct. 3 mean = {post_avg:.1f}%")

# Save weekly TPS % table for independent verification
tps_check = pd.DataFrame({
    "week_start":        PCT_WKS,
    "numerator_tps2023": wk_tps23_c.values,
    "denominator_all":   wk_total_c.values,
    "denominator_known": wk_denom_c.values,
    "pct_tps2023":       pct_2023_c.values,
    "masked":            pct_plot_c.isna().values,
})
tps_check.to_csv(FIGDIR / "tps_pct_by_week.csv", index=False)
print("Saved tps_pct_by_week.csv")

# ══════════════════════════════════════════════════════════════════════════════
# 5. DETENTION STOCK (panel 4)
#    Count of ERO-interior Venezuelans in ICE detention on each calendar day.
#    A person is "in detention" on day d if book_in ≤ d and (book_out > d or
#    book_out is missing, meaning they are still detained).
# ══════════════════════════════════════════════════════════════════════════════
print("Loading detention stays …")
stays = pd.read_excel(
    str(INDIR / "detention-stays-latest.xlsx"),
    usecols=["citizenship_country", "stay_book_in_date_time",
             "stay_book_out_date_time", "unique_identifier"]
)
stays["country"]  = stays["citizenship_country"].str.upper()
stays["book_in"]  = pd.to_datetime(stays["stay_book_in_date_time"],  errors="coerce")
stays["book_out"] = pd.to_datetime(stays["stay_book_out_date_time"], errors="coerce")

ven_stays = stays[
    (stays["country"] == "VENEZUELA") &
    stays["book_in"].notna() &
    stays["unique_identifier"].isin(ero_ids)   # ERO-interior only
].copy()
bin_d  = ven_stays["book_in"].dt.normalize()
bout_d = ven_stays["book_out"].dt.normalize()

days       = pd.date_range(START, END, freq="D")
stock_vals = [((bin_d <= d) & (bout_d.isna() | (bout_d > d))).sum() for d in days]
stock      = pd.DataFrame({"date": days, "n": stock_vals})

peak_date = stock.loc[stock["n"].idxmax(), "date"]
peak_val  = stock["n"].max()
print(f"  Detention stock peak: {peak_val:,} on {peak_date.date()}")

# ══════════════════════════════════════════════════════════════════════════════
# 6. FIGURE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def k_formatter(x, pos):
    return f"{x/1000:.0f}K" if abs(x) >= 1000 else f"{int(x)}"

def style_ax(ax, is_bottom=False):
    """Apply sparkline-style axis formatting."""
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#AAAAAA")
    ax.spines["right"].set_color("#AAAAAA")
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax.tick_params(axis="y", labelsize=FS - 1.5, length=2, pad=2)
    ax.tick_params(axis="x", labelsize=FS - 1.0, length=2)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.4, color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n'%y"))
    ax.set_xlim(START - pd.Timedelta(days=3), END + pd.Timedelta(days=7))
    if is_bottom:
        ax.tick_params(axis="x", labelbottom=True, labelsize=FS - 1.0)
    else:
        ax.tick_params(axis="x", labelbottom=False, length=0)

def add_title(ax, title, above=False):
    """Add bold narrative panel title (above axes or superimposed)."""
    if above:
        ax.text(0.01, 1.02, title, transform=ax.transAxes,
                fontsize=FS - 0.5, va="bottom", fontweight="bold",
                color="#222222", linespacing=1.0, clip_on=False)
    else:
        ax.text(0.01, 0.97, title, transform=ax.transAxes,
                fontsize=FS - 0.5, va="top", fontweight="bold",
                color="#222222", linespacing=1.0,
                bbox=dict(facecolor="white", alpha=0.5, edgecolor="none", pad=1.5))

def yticks_compact(ax, n=4):
    ax.yaxis.set_major_locator(
        mticker.MaxNLocator(nbins=n, integer=True, prune="lower"))

def expand_for_title(ax, factor=1.35):
    ylo, yhi = ax.get_ylim()
    ax.set_ylim(ylo, yhi * factor)

def add_event_lines(ax, lines, add_labels=False):
    """Draw event vertical lines; optionally add rotated date labels."""
    for date, label, ls, color in lines:
        ax.axvline(date, color=color, linewidth=0.7, linestyle=ls, zorder=5)
        if add_labels:
            trans = blended_transform_factory(ax.transData, ax.transAxes)
            ax.text(date + pd.Timedelta(days=3), 0.97, label,
                    transform=trans, rotation=90, va="top", ha="left",
                    fontsize=FS - 2.5, color=color, zorder=6, clip_on=True)

# ══════════════════════════════════════════════════════════════════════════════
# 7. BUILD FIGURE
# ══════════════════════════════════════════════════════════════════════════════
TITLES = [
    "(1) Interior deportations of all other\nnationalities plateaued in 2026",
    "(2) But interior deportations\nof Venezuelans spiked",
    "(3) Even as ICE arrests of\nVenezuelans declined",
    "(4) Because the number of\nVenezuelans in ICE detention declined.",
    "(5) TPS 2023-eligible as a % of\nVenezuelan interior removals\nrises after October 3, 2025",
]

N          = len(TITLES)
fig_height = N * PH + (N - 1) * GAP * PH
fig, axes  = plt.subplots(N, 1, figsize=(FW, fig_height),
                          sharex=True, gridspec_kw={"hspace": GAP})

# Panel 1: non-Venezuelan interior removals
ax = axes[0]
ax.bar(other_wk["week"], other_wk["n"], width=5, color=MEX, zorder=2)
style_ax(ax)
yticks_compact(ax)
add_event_lines(ax, VLINES_MAIN, add_labels=True)   # labels on top panel only
add_title(ax, TITLES[0], above=True)                # above to avoid label overlap
expand_for_title(ax)

# Panel 2: Venezuelan interior removals
ax = axes[1]
ax.bar(ven_wk["week"], ven_wk["n"], width=5, color=VEN, zorder=2)
style_ax(ax)
yticks_compact(ax)
add_event_lines(ax, VLINES_MAIN)
add_title(ax, TITLES[1])
expand_for_title(ax)

# Panel 3: Venezuelan ERO arrests
ax = axes[2]
ax.bar(arr_wk["week"], arr_wk["n"], width=5, color=VEN, zorder=2)
style_ax(ax)
yticks_compact(ax)
add_event_lines(ax, VLINES_MAIN)
add_title(ax, TITLES[2])
expand_for_title(ax)

# Panel 4: ERO-interior Venezuelan detention stock (daily)
ax = axes[3]
ax.fill_between(stock["date"], stock["n"], color=VEN, alpha=0.25, zorder=1)
ax.plot(stock["date"], stock["n"], color=VEN, linewidth=0.8, zorder=2)
style_ax(ax)
yticks_compact(ax)
add_event_lines(ax, VLINES_MAIN)
add_title(ax, TITLES[3])
expand_for_title(ax)

# Panel 5: TPS 2023-eligible % (custom week grid, Oct. 3 anchor)
ax = axes[4]
ax.plot(PCT_WKS, pct_plot_c.values,
        color="#7BBCF0", linewidth=0.9,
        marker="o", markersize=2.0, markeredgewidth=0, zorder=3)

# Weighted period-average reference lines with centered labels
pre_end  = PCT_WKS[pre_mask_pct][-1]  + pd.Timedelta(days=6)
post_end = PCT_WKS[post_mask_pct][-1] + pd.Timedelta(days=6)
ax.hlines(pre_avg,  PCT_WKS[pre_mask_pct][0],  pre_end,
          colors=DARK_BLUE, linewidth=1.0, zorder=4)
ax.hlines(post_avg, PCT_WKS[post_mask_pct][0], post_end,
          colors=DARK_BLUE, linewidth=1.0, zorder=4)
pre_mid  = PCT_WKS[pre_mask_pct][0]  + (pre_end  - PCT_WKS[pre_mask_pct][0])  / 2
post_mid = PCT_WKS[post_mask_pct][0] + (post_end - PCT_WKS[post_mask_pct][0]) / 2
for mid, avg in [(pre_mid, pre_avg), (post_mid, post_avg)]:
    ax.text(mid, avg, f"Mean = {avg:.1f}%",
            ha="center", va="bottom", fontsize=FS - 2.5, color=DARK_BLUE, zorder=7,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none",
                      boxstyle="square,pad=0"))

style_ax(ax, is_bottom=True)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.yaxis.set_major_locator(mticker.FixedLocator([25, 35, 45]))
add_event_lines(ax, VLINES_TPS, add_labels=False)
# Oct. 3 rotated label on this panel only
trans = blended_transform_factory(ax.transData, ax.transAxes)
ax.text(OCT3 + pd.Timedelta(days=3), 0.97, "Oct.\u00a03,\u00a02025",
        transform=trans, rotation=90, va="top", ha="left",
        fontsize=FS - 2.5, color="#CC3333", zorder=6, clip_on=True)
add_title(ax, TITLES[4])
ylo, _ = ax.get_ylim()
ax.set_ylim(max(ylo, 0), 47)

# ── save ───────────────────────────────────────────────────────────────────────
fig.savefig(FIGDIR / "fig_combined.pdf", bbox_inches="tight")
fig.savefig(FIGDIR / "fig_combined.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("Saved fig_combined")
