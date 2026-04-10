"""
replicate_flights.py
====================
Replication code for the flights figure and associated text paragraph.

Text supported
--------------
  The note discusses the breakdown of interior Venezuelan removals by mode:
  charter flights to Venezuela, commercial flights to Venezuela, and removals
  to third countries.  This script computes daily averages pre- and post-
  Jan. 16, 2026 for each mode to document which channels drove the surge.

Printed statistics (for text)
------------------------------
  Daily average interior VZ removals by mode, pre (Jul 1–Dec 10, 2025)
  vs. post (Jan 16–Mar 10, 2026): charter, commercial, other.

Figure produced
---------------
  fig_flights_by_mode.pdf/.png — weekly interior Venezuelan removals
                                  broken down by mode:
      (1) Charter flights to Venezuela   [dark navy]
      (2) Commercial flights to Venezuela [blue]
      (3) To other (third) countries      [green]

Classification methodology (replicating DKreplicateClaude.do lines 287–293)
----------------------------------------------------------------------------
  Charter vs. commercial distinction:
    - The Human Rights First (HRF) ICE Flight Monitor reports the number of
      ICE charter flights to Venezuela by month.  We use those counts as N_t
      (the number of charter flights in month t).
    - Within each month, port-days (port × date combinations) are ranked
      descending by the total number of Venezuelans removed to Venezuela on
      that day (using all removals, not just interior, for the ranking).
    - The top N_t port-days in each month are classified as charter flights.
    - Remaining to-Venezuela port-days are classified as commercial flights.

  Why use total (not interior) removals for charter ranking?
    The Stata code uses total removals to Venezuela — interior + border — when
    ranking port-days.  This matches the HRF flight-count data, which covers
    all removal flights regardless of whether passengers were interior or
    border cases.  Only the plotted series (the bars) use interior removals.

  To other countries:
    Interior Venezuelan removals where Departure Country ≠ VENEZUELA.

Data sources
------------
  Removals : 2026-ICLI-00005_Removals_{FY}_20260311_Redacted.csv  (FY23–FY26)
  Arrests  : 2026-ICLI-00005_Arrests_{FY}_20260311_Redacted.xlsx  (FY23–FY26)
             (used only to identify interior removals)
  HRF flight monitor: data/inputs/iceflightmonitor.csv
             columns: month (e.g. "January 2025"), flight count, passengers
"""

import warnings; warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from pathlib import Path

# ── paths & constants ──────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
INDIR  = ROOT / "data" / "inputs"
ARRDIR = INDIR / "2026-ICLI-00005_Arrests_Redacted"
REMDIR = INDIR / "2026-ICLI-00005_Removals_Redacted"
FIGDIR = Path("/Users/dorothykronick/ddp/figures")

# Analysis window: two years ending at the last day of available data
END   = pd.Timestamp("2026-03-10")
START = END - pd.DateOffset(years=2)   # 2024-03-10

JAN3  = pd.Timestamp("2026-01-03")   # Operation Absolute Resolve

C_CHARTER    = "#1B4F8A"   # dark navy  — charter flights to Venezuela
C_COMMERCIAL = "#4C9BE8"   # blue       — commercial flights to Venezuela
C_OTHER      = "#4CAF82"   # green      — to other (third) countries

FW = 3.3
PH = 2.2
FS = 7.5

# ══════════════════════════════════════════════════════════════════════════════
# 1. BUILD ERO-INTERIOR ID SET
#    A removal is "interior" if the person's Anonymized Identifier appears
#    in the ERO arrests files.
# ══════════════════════════════════════════════════════════════════════════════
print("Loading arrests (interior filter) …")
arr_dfs = []
for fy in ["FY23", "FY24", "FY25", "FY26"]:
    df = pd.read_excel(
        ARRDIR / f"2026-ICLI-00005_Arrests_{fy}_20260311_Redacted.xlsx",
        skiprows=6, engine="openpyxl",
        usecols=["Anonymized Identifier"]
    )
    arr_dfs.append(df)
ero_ids = set(pd.concat(arr_dfs, ignore_index=True)["Anonymized Identifier"])
print(f"  {len(ero_ids):,} ERO IDs")

# ══════════════════════════════════════════════════════════════════════════════
# 2. LOAD ALL VENEZUELAN REMOVALS
#    We need both interior and border removals at this stage because the
#    charter-flight classification is based on *total* removals to Venezuela
#    (matching the HRF flight-count data).
# ══════════════════════════════════════════════════════════════════════════════
print("Loading removals …")
rem_dfs = []
for fy in ["FY23", "FY24", "FY25", "FY26"]:
    df = pd.read_csv(
        REMDIR / f"2026-ICLI-00005_Removals_{fy}_20260311_Redacted.csv",
        skiprows=6, low_memory=False,
        usecols=["Anonymized Identifier", "Citizenship Country",
                 "Departed Date", "Port of Departure", "Departure Country"]
    )
    rem_dfs.append(df)
rem = pd.concat(rem_dfs, ignore_index=True)

ven = rem[rem["Citizenship Country"] == "VENEZUELA"].copy()
ven["date"]     = pd.to_datetime(ven["Departed Date"], errors="coerce").dt.normalize()
ven["interior"] = ven["Anonymized Identifier"].isin(ero_ids).astype(int)
ven["to_vz"]    = (ven["Departure Country"] == "VENEZUELA")
ven = ven[ven["date"].notna() & ven["Port of Departure"].notna()]
ven["month"] = ven["date"].dt.to_period("M")

# ══════════════════════════════════════════════════════════════════════════════
# 3. PORT-DAY AGGREGATION
#    For the charter classification, we need the total removals to Venezuela
#    (all + border) on each port-day.  For the plotted series, we use interior
#    removals only.
# ══════════════════════════════════════════════════════════════════════════════

# Total (all) removals to VZ by port-day — used for charter ranking
total_vz = (ven[ven["to_vz"]]
            .groupby(["month", "Port of Departure", "date"])
            .size().reset_index(name="total_vz"))

# Interior removals to VZ by port-day — plotted
interior_vz = (ven[ven["to_vz"] & (ven["interior"] == 1)]
               .groupby(["Port of Departure", "date"])
               .size().reset_index(name="interior_vz"))

# Interior removals to other countries (by departure date only)
interior_other = (ven[~ven["to_vz"] & (ven["interior"] == 1)]
                  .groupby("date")
                  .size().reset_index(name="interior_other"))

# ══════════════════════════════════════════════════════════════════════════════
# 4. CHARTER CLASSIFICATION
#    Load HRF monthly flight counts; within each month, classify the top N
#    port-days (by total_vz) as charter, the rest as commercial.
# ══════════════════════════════════════════════════════════════════════════════
hrf = pd.read_csv(INDIR / "iceflightmonitor.csv", header=None,
                  names=["month_str", "flightcount", "passengers"])
hrf["month"] = pd.to_datetime(hrf["month_str"], format="%B %Y").dt.to_period("M")
hrf = hrf[["month", "flightcount"]].set_index("month")

# Attach the monthly flight count to each port-day
total_vz["flightcount"] = total_vz["month"].map(hrf["flightcount"])

# Rank port-days within each month, descending by total removals to VZ
total_vz = total_vz.sort_values(["month", "total_vz"], ascending=[True, False])
total_vz["rank"] = total_vz.groupby("month").cumcount() + 1

# Top-N port-days = charter; remaining = commercial
# Months with no HRF count get NaN (charter status unknown)
total_vz["charter"] = np.where(
    total_vz["flightcount"].isna(), np.nan,
    (total_vz["rank"] <= total_vz["flightcount"]).astype(float)
)

# ══════════════════════════════════════════════════════════════════════════════
# 5. MERGE CHARTER FLAG ONTO INTERIOR VZ SERIES
# ══════════════════════════════════════════════════════════════════════════════
port_day = total_vz[["Port of Departure", "date", "charter"]].merge(
    interior_vz, on=["Port of Departure", "date"], how="left"
)
port_day["interior_vz"] = port_day["interior_vz"].fillna(0)

# ══════════════════════════════════════════════════════════════════════════════
# 6. WEEKLY AGGREGATION
#    Monday-anchored weeks; no complete-week filter applied here because the
#    figure uses a longer window (2 years) and the stacked-bar style is less
#    sensitive to partial weeks than a line chart.
# ══════════════════════════════════════════════════════════════════════════════
WKS = pd.date_range(START, END, freq="W-MON")

def to_weekly(df, date_col, val_col, mask=None):
    sub = df if mask is None else df[mask]
    sub = sub.copy()
    d   = pd.to_datetime(sub[date_col])
    sub["week"] = d - pd.to_timedelta(d.dt.dayofweek, unit="d")
    return sub.groupby("week")[val_col].sum().reindex(WKS, fill_value=0)

charter_wk    = to_weekly(port_day, "date", "interior_vz", port_day["charter"] == 1)
commercial_wk = to_weekly(port_day, "date", "interior_vz", port_day["charter"] == 0)
other_wk      = to_weekly(interior_other, "date", "interior_other")

print("\nWeekly interior removals — last 10 weeks:")
check = pd.DataFrame({"charter": charter_wk, "commercial": commercial_wk,
                       "other": other_wk})
check["total"] = check.sum(axis=1)
print(check.tail(10).to_string())

# ── Pre/post daily averages by mode ──────────────────────────────────────────
# Pre-period  : Jul. 1 – Dec. 10, 2025 (latter half of 2025; flights paused after Dec. 10)
# Post-period : Jan. 16 – Mar. 10, 2026 (first deportation flight onward)
PRE_START  = pd.Timestamp("2025-07-01")
PRE_END    = pd.Timestamp("2025-12-10")
POST_START = pd.Timestamp("2026-01-16")
POST_END   = pd.Timestamp("2026-03-10")

pre_days  = pd.date_range(PRE_START, PRE_END)
post_days = pd.date_range(POST_START, POST_END)

# Daily interior removals by mode (reindex to full calendar to count zero-days)
charter_daily    = port_day.loc[port_day["charter"] == 1].groupby("date")["interior_vz"].sum()
commercial_daily = port_day.loc[port_day["charter"] == 0].groupby("date")["interior_vz"].sum()
other_daily      = interior_other.set_index("date")["interior_other"]

print("\n── Daily average interior VZ removals by mode (pre vs. post) ────────")
print(f"{'Mode':25s}  {'Pre (Jul1–Dec10)':>17s}  {'Post (Jan16–Mar10)':>18s}  {'Change':>8s}")
for label, series in [("Charter to VZ",    charter_daily),
                       ("Commercial to VZ", commercial_daily),
                       ("To other countries", other_daily)]:
    pre_avg  = series.reindex(pre_days,  fill_value=0).mean()
    post_avg = series.reindex(post_days, fill_value=0).mean()
    pct = (post_avg / pre_avg - 1) * 100 if pre_avg > 0 else float("inf")
    print(f"  {label:23s}  {pre_avg:17.1f}  {post_avg:18.1f}  {pct:+7.0f}%")
print("─────────────────────────────────────────────────────────────────────\n")

# ══════════════════════════════════════════════════════════════════════════════
# 7. FIGURE
#    Overlaid bars (each series drawn from zero, not stacked).  This matches
#    the Stata twoway bar style: the largest series (charter) is drawn first
#    (background) and the smallest (commercial) on top, so all three are
#    visible without requiring a true stacked chart.
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(FW, PH))

ax.bar(WKS, charter_wk.values,    width=5, color=C_CHARTER,    alpha=0.85,
       zorder=2, label="Charter to Venezuela")
ax.bar(WKS, other_wk.values,      width=5, color=C_OTHER,      alpha=0.85,
       zorder=3, label="To other countries")
ax.bar(WKS, commercial_wk.values, width=5, color=C_COMMERCIAL, alpha=0.85,
       zorder=4, label="Commercial to Venezuela")

ax.spines["top"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#AAAAAA")
ax.spines["right"].set_color("#AAAAAA")
ax.yaxis.set_label_position("right")
ax.yaxis.tick_right()
ax.yaxis.set_major_formatter(mticker.FuncFormatter(
    lambda x, _: f"{x/1000:.0f}K" if x >= 1000 else f"{int(x)}"))
ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, integer=True, prune="lower"))
ax.tick_params(axis="y", labelsize=FS - 1.5, length=2, pad=2)
ax.tick_params(axis="x", labelsize=FS - 1.0, length=2, labelbottom=True)
ax.yaxis.grid(True, linestyle=":", linewidth=0.4, color="#DDDDDD", zorder=0)
ax.set_axisbelow(True)
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[4, 7, 10, 1]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n'%y"))
ax.set_xlim(START - pd.Timedelta(days=7), END + pd.Timedelta(days=7))

ax.axvline(JAN3, color="#CC3333", linewidth=0.8, linestyle="--", zorder=5)

ax.text(0.01, 0.97,
        "Venezuelan interior removals\nby mode",
        transform=ax.transAxes,
        fontsize=FS - 0.5, va="top", fontweight="bold",
        color="#222222", linespacing=1.0)

ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi * 1.35)

ax.legend(fontsize=FS - 2.5, frameon=False,
          loc="upper left", bbox_to_anchor=(0.01, 0.78),
          handlelength=1.2, handletextpad=0.4, labelspacing=0.3,
          borderaxespad=0)

fig.savefig(FIGDIR / "fig_flights_by_mode.pdf", bbox_inches="tight")
fig.savefig(FIGDIR / "fig_flights_by_mode.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("\nSaved fig_flights_by_mode")
