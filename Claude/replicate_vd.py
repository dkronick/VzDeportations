"""
replicate_vd.py
===============
Replication code for the voluntary-departures (VD) robustness check.

This script supports the claim in the note that voluntary departures from
immigration court did NOT account for the differential increase in Venezuelan
removals after January 3, 2026.

The argument uses a difference-in-differences (DiD) design:
  - Mexicans serve as a comparison group.  Both Venezuelans and Mexicans
    have large numbers of pending immigration-court cases; if voluntary
    departures surged for Venezuelans but not Mexicans after Jan. 3, that
    is evidence of a real increase in VDs rather than a mechanical artifact
    of broader court trends.

Figures produced
----------------
  fig_vd_venezuela.pdf/.png    — weekly Venezuelan VDs (linear scale)
  fig_vd_mexico.pdf/.png       — weekly Mexican VDs (linear scale)
  fig_vd_event_study.pdf/.png  — event study: log(VZ VDs) − log(MX VDs),
                                  centered at pre-Jan. 3 mean
  fig_vd_event_study_levels.pdf/.png — event study in levels (counts):
                                  (VZ_t − VZ_pre) − (MX_t − MX_pre)

Event-study design
------------------
  Treatment date : Jan. 3, 2026 (Operation Absolute Resolve announced).
  Pre-period     : all complete weeks before the week containing Jan. 3.
  Post-period    : the week of Jan. 3 onward.
  Comparison     : week of Dec. 29, 2025 is the first post-period week
                   (Jan. 3 is a Saturday; the Monday-anchored week
                   containing it starts Dec. 29, 2025).

  Log-ratio version (fig_vd_event_study):
    Y = log(VZ_t + 0.5) − log(MX_t + 0.5), centered at pre-period mean.
    The +0.5 (Jeffreys prior) prevents log(0) in zero-count weeks.
    SE via delta method: sqrt(1/VZ_s + 1/MX_s).
    Interpretation: a value of δ means VZ VDs grew exp(δ) times more
    than MX VDs, relative to their respective pre-period levels.

  Levels version (fig_vd_event_study_levels):
    Y = (VZ_t − VZ_pre_mean) − (MX_t − MX_pre_mean).
    SE via Poisson approximation: sqrt(VZ_t + MX_t).
    Interpretation: excess weekly VZ VDs relative to Mexico's deviation
    from its own pre-period baseline.  Zero = no differential change.

Data source
-----------
  EOIR immigration court records:
    data/inputs/courts/cases.dta
  Columns used: nationality_code, case_outcome, final_completion_date
  Nationality codes: VE = Venezuela, MX = Mexico
  Case outcome: "Voluntary Departure"
"""

import warnings; warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
from matplotlib.transforms import blended_transform_factory
from pathlib import Path

# ── paths & constants ──────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
INDIR  = ROOT / "data" / "inputs"
FIGDIR = Path("/Users/dorothykronick/ddp/figures")

START = pd.Timestamp("2024-08-01")
END   = pd.Timestamp("2026-03-10")

JAN20 = pd.Timestamp("2025-01-20")   # Trump inauguration
OCT3  = pd.Timestamp("2025-10-03")   # Supreme Court TPS ruling
JAN3  = pd.Timestamp("2026-01-03")   # Operation Absolute Resolve (treatment date)

# Week of Jan. 3: Jan. 3, 2026 is a Saturday; Monday-anchored week = Dec. 29, 2025
JAN3_WEEK = JAN3 - pd.Timedelta(days=JAN3.dayofweek)

VEN = "#4C9BE8"   # blue  — Venezuela
MEX = "#4CAF82"   # green — Mexico

FW = 3.3   # figure width (inches)
PH = 2.4   # figure height (inches)
FS = 7.5   # base font size (points)

VLINES = [
    (JAN20, "Jan.\u00a020,\u00a02025", ":",  "#888888"),
    (OCT3,  "Oct.\u00a03,\u00a02025",  "--", "#888888"),
    (JAN3,  "Jan.\u00a03,\u00a02026",  "-",  "#CC3333"),
]

# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD IMMIGRATION COURT DATA
# ══════════════════════════════════════════════════════════════════════════════
print("Loading courts data …")
courts = pd.read_stata(
    str(INDIR / "courts" / "cases.dta"),
    columns=["nationality_code", "case_outcome", "final_completion_date"]
)

courts["date"] = pd.to_datetime(courts["final_completion_date"], errors="coerce")

# Keep only voluntary departures within the analysis window
courts = courts[
    courts["date"].notna() &
    (courts["date"] >= START) &
    (courts["date"] <= END) &
    (courts["case_outcome"].astype(str) == "Voluntary Departure")
].copy()

# Assign each case to its Monday-anchored week
courts["week"] = courts["date"] - pd.to_timedelta(courts["date"].dt.dayofweek, unit="d")

# Complete weeks only (a week is complete if its last day ≤ END)
WKS = pd.date_range(START, END, freq="W-MON")
WKS = WKS[WKS + pd.Timedelta(days=6) <= END]

def weekly_vd(nat_code):
    """Return array of weekly VD counts for nationality code nat_code."""
    sub = courts[courts["nationality_code"].astype(str) == nat_code]
    return (sub.groupby("week").size()
               .reindex(WKS, fill_value=0)
               .values.astype(float))

vz_n = weekly_vd("VE")
mx_n = weekly_vd("MX")

print(f"  Venezuelan VDs in window: {int(vz_n.sum()):,}")
print(f"  Mexican VDs in window:    {int(mx_n.sum()):,}")

# ══════════════════════════════════════════════════════════════════════════════
# 2. RAW WEEKLY VD FIGURES (separate for Venezuela and Mexico)
#
#    These show the absolute level of voluntary departures for each country.
#    Mexico has far more VDs than Venezuela (different scales); plotting
#    separately avoids a misleading comparison of levels.
# ══════════════════════════════════════════════════════════════════════════════

def k_formatter(x, pos):
    return f"{x/1000:.0f}K" if abs(x) >= 1000 else f"{int(x)}"

def style_ax_vd(ax):
    """Standard sparkline style for VD figures."""
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#AAAAAA")
    ax.spines["right"].set_color("#AAAAAA")
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4, integer=True, prune="lower"))
    ax.tick_params(axis="y", labelsize=FS - 1.5, length=2, pad=2)
    ax.tick_params(axis="x", labelsize=FS - 1.0, length=2, labelbottom=True)
    ax.yaxis.grid(True, linestyle=":", linewidth=0.4, color="#DDDDDD", zorder=0)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n'%y"))
    ax.set_xlim(START - pd.Timedelta(days=3), END + pd.Timedelta(days=7))

def add_event_lines(ax, add_labels=False):
    for date, label, ls, color in VLINES:
        lw = 1.0 if date == JAN3 else 0.7
        ax.axvline(date, color=color, linewidth=lw, linestyle=ls, zorder=5)
        if add_labels:
            trans = blended_transform_factory(ax.transData, ax.transAxes)
            ax.text(date + pd.Timedelta(days=3), 0.97, label,
                    transform=trans, rotation=90, va="top", ha="left",
                    fontsize=FS - 2.5, color=color, zorder=6, clip_on=True)

wks_arr = WKS.to_numpy()

def draw_raw_vd(counts, color, title, fname):
    fig, ax = plt.subplots(figsize=(FW, PH))
    ax.plot(wks_arr, counts, color=color, linewidth=1.0, zorder=2)
    style_ax_vd(ax)
    add_event_lines(ax, add_labels=True)
    ax.text(0.01, 0.97, title, transform=ax.transAxes,
            fontsize=FS - 0.5, va="top", fontweight="bold",
            color="#222222", linespacing=1.0)
    ylo, yhi = ax.get_ylim()
    ax.set_ylim(max(ylo, 0), yhi * 1.35)
    fig.savefig(FIGDIR / f"{fname}.pdf", bbox_inches="tight")
    fig.savefig(FIGDIR / f"{fname}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {fname}")

draw_raw_vd(vz_n, VEN,
            title="Voluntary departures\nof Venezuelans (weekly)",
            fname="fig_vd_venezuela")

draw_raw_vd(mx_n, MEX,
            title="Voluntary departures\nof Mexicans (weekly)",
            fname="fig_vd_mexico")

# ══════════════════════════════════════════════════════════════════════════════
# 3. EVENT STUDY — LOG-RATIO VERSION
#
#    Y = log(VZ_t + 0.5) − log(MX_t + 0.5), centered at pre-period mean.
#
#    Why log ratio?  VZ and MX VDs are on very different scales (VZ ≪ MX),
#    so a raw DiD in counts would be dominated by Mexico.  The log ratio
#    puts both countries on a comparable relative scale: it measures how
#    much each series deviated from its own baseline.
#
#    95% CI: pointwise, via Poisson delta method.
#      Var[log n] ≈ 1/n  →  Var[log VZ − log MX] ≈ 1/VZ_s + 1/MX_s
#    where VZ_s = VZ_n + 0.5 to avoid division by zero.
#
#    Interpretation: a post-period value of δ means Venezuelan VDs grew
#    exp(δ) times more than Mexican VDs, relative to their respective
#    pre-period averages.  Zero = no differential change.
# ══════════════════════════════════════════════════════════════════════════════

# Smoothed counts (Jeffreys prior prevents log(0))
vz_s = vz_n + 0.5
mx_s = mx_n + 0.5

log_ratio = np.log(vz_s) - np.log(mx_s)

pre_mask = WKS < JAN3_WEEK
pre_mean = log_ratio[pre_mask].mean()
centered = log_ratio - pre_mean    # zero line = pre-period average

se    = np.sqrt(1.0 / vz_s + 1.0 / mx_s)
ci_lo = centered - 1.96 * se
ci_hi = centered + 1.96 * se

fig, ax = plt.subplots(figsize=(FW, PH))

ax.axvspan(START, JAN3_WEEK, color="#F5F5F5", zorder=0)   # shade pre-period

# CI ribbon: gray in pre-period, blue in post-period
ax.fill_between(wks_arr[pre_mask],  ci_lo[pre_mask],  ci_hi[pre_mask],
                color="#BBBBBB", alpha=0.35, zorder=1, linewidth=0)
ax.fill_between(wks_arr[~pre_mask], ci_lo[~pre_mask], ci_hi[~pre_mask],
                color=VEN,      alpha=0.20, zorder=1, linewidth=0)

# Point estimates: gray pre-period, blue post-period
ax.plot(wks_arr[pre_mask],  centered[pre_mask],  color="#999999", linewidth=0.9, zorder=3)
ax.plot(wks_arr[~pre_mask], centered[~pre_mask], color=VEN,       linewidth=1.1, zorder=3)

ax.axhline(0, color="#AAAAAA", linewidth=0.6, zorder=2)

add_event_lines(ax, add_labels=True)

ax.spines["top"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#AAAAAA")
ax.spines["right"].set_color("#AAAAAA")
ax.yaxis.set_label_position("right")
ax.yaxis.tick_right()
ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5, prune="both"))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))
ax.tick_params(axis="y", labelsize=FS - 1.5, length=2, pad=2)
ax.tick_params(axis="x", labelsize=FS - 1.0, length=2, labelbottom=True)
ax.yaxis.grid(True, linestyle=":", linewidth=0.4, color="#DDDDDD", zorder=0)
ax.set_axisbelow(True)
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n'%y"))
ax.set_xlim(START - pd.Timedelta(days=3), END + pd.Timedelta(days=7))
ax.set_ylabel("log(VZ VDs) \u2212 log(MX VDs),\ncentered at pre-period mean",
              fontsize=FS - 2.0, labelpad=4)
ax.text(0.01, 0.97,
        "Event study: Venezuelan vs. Mexican\nvoluntary departures (log ratio, weekly)",
        transform=ax.transAxes, fontsize=FS - 0.5, va="top", fontweight="bold",
        color="#222222", linespacing=1.0)
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi * 1.45)

fig.savefig(FIGDIR / "fig_vd_event_study.pdf", bbox_inches="tight")
fig.savefig(FIGDIR / "fig_vd_event_study.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("Saved fig_vd_event_study")

# ══════════════════════════════════════════════════════════════════════════════
# 4. EVENT STUDY — LEVELS VERSION
#
#    Y = (VZ_t − VZ_pre_mean) − (MX_t − MX_pre_mean)
#
#    This is the standard DiD estimator in count units.  Each series is
#    centered by subtracting its own pre-period mean; the difference shows
#    how much more (or less) Venezuelan VDs deviated from their baseline
#    compared with Mexican VDs.
#
#    95% CI: Poisson approximation.
#      Var[n_VZ − n_MX] ≈ n_VZ + n_MX  (counts from independent Poissons)
#    Weeks with very few VZ VDs will have wide CIs; that is informative.
# ══════════════════════════════════════════════════════════════════════════════

pre_mean_vz = vz_n[pre_mask].mean()
pre_mean_mx = mx_n[pre_mask].mean()

dev_vz = vz_n - pre_mean_vz   # VZ deviation from its pre-period mean
dev_mx = mx_n - pre_mean_mx   # MX deviation from its pre-period mean
diff   = dev_vz - dev_mx      # DiD: excess VZ deviation relative to MX

se_lev = np.sqrt(np.maximum(vz_n, 0.5) + np.maximum(mx_n, 0.5))
ci_lo_l = diff - 1.96 * se_lev
ci_hi_l = diff + 1.96 * se_lev

fig, ax = plt.subplots(figsize=(FW, PH))

ax.axvspan(START, JAN3_WEEK, color="#F5F5F5", zorder=0)

ax.fill_between(wks_arr[pre_mask],  ci_lo_l[pre_mask],  ci_hi_l[pre_mask],
                color="#BBBBBB", alpha=0.35, zorder=1, linewidth=0)
ax.fill_between(wks_arr[~pre_mask], ci_lo_l[~pre_mask], ci_hi_l[~pre_mask],
                color=VEN,      alpha=0.20, zorder=1, linewidth=0)

ax.plot(wks_arr[pre_mask],  diff[pre_mask],  color="#999999", linewidth=0.9, zorder=3)
ax.plot(wks_arr[~pre_mask], diff[~pre_mask], color=VEN,       linewidth=1.1, zorder=3)

ax.axhline(0, color="#AAAAAA", linewidth=0.6, zorder=2)

add_event_lines(ax, add_labels=True)

ax.spines["top"].set_visible(False)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color("#AAAAAA")
ax.spines["right"].set_color("#AAAAAA")
ax.yaxis.set_label_position("right")
ax.yaxis.tick_right()
ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5, prune="both"))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(
    lambda x, _: f"{int(x):+d}" if x != 0 else "0"))
ax.tick_params(axis="y", labelsize=FS - 1.5, length=2, pad=2)
ax.tick_params(axis="x", labelsize=FS - 1.0, length=2, labelbottom=True)
ax.yaxis.grid(True, linestyle=":", linewidth=0.4, color="#DDDDDD", zorder=0)
ax.set_axisbelow(True)
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n'%y"))
ax.set_xlim(START - pd.Timedelta(days=3), END + pd.Timedelta(days=7))
ax.set_ylabel("(VZ\u2212VZ\u0305\u209A\u1D63\u2091) \u2212 (MX\u2212MX\u0305\u209A\u1D63\u2091)\nweekly VD counts",
              fontsize=FS - 2.0, labelpad=4)
ax.text(0.01, 0.97,
        "Event study: Venezuelan vs. Mexican\nvoluntary departures (levels, weekly)",
        transform=ax.transAxes, fontsize=FS - 0.5, va="top", fontweight="bold",
        color="#222222", linespacing=1.0)
ylo, yhi = ax.get_ylim()
ax.set_ylim(ylo, yhi * 1.45)

fig.savefig(FIGDIR / "fig_vd_event_study_levels.pdf", bbox_inches="tight")
fig.savefig(FIGDIR / "fig_vd_event_study_levels.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("Saved fig_vd_event_study_levels")
