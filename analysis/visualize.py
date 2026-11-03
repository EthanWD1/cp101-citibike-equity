"""Six explanatory figures, all regenerated from the tract and daily tables."""
import json
import os
from pathlib import Path
import textwrap

os.environ.setdefault("MPLCONFIGDIR", str(Path(".cache/matplotlib")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from .config import FIGURES, SCOPES, GROUPS

PALETTE = ["#222222", "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#7A7A7A"]
SOURCE = "Sources: Citi Bike, September 2025; ACS 2020–2024; TIGER/Line 2024. Group PAIR."


def save(fig, name, caption, extra=""):
    width = int(fig.get_figwidth() * 17)
    fig.text(.035, .043, textwrap.fill(caption, width), fontsize=9, va="bottom")
    fig.text(.035, .010, textwrap.fill(SOURCE + (" " + extra if extra else ""), int(width * 1.2)), fontsize=7.5, color="#555555", va="bottom")
    fig.savefig(FIGURES / name, dpi=170, facecolor="white")
    plt.close(fig)
    return {"file": name, "caption": caption}


def map_coverage(tracts, stations):
    fig, ax = plt.subplots(figsize=(8, 7.2))
    fig.subplots_adjust(left=.09, right=.96, bottom=.12, top=.91)
    valid = tracts.eligible & tracts.stations_per_km2.notna()
    zero = valid & tracts.observed_stations.eq(0)
    positive = valid & tracts.observed_stations.gt(0)
    tracts.loc[~valid].plot(ax=ax, color="#dddddd", edgecolor="#b0b0b0", linewidth=.15, hatch="///")
    tracts.loc[zero].plot(ax=ax, color="#faf8ec", edgecolor="#c8c8c8", linewidth=.15)
    cuts = tracts.loc[positive, "stations_per_km2"].quantile([.25, .5, .75]).to_numpy()
    handles = [Patch(facecolor="#faf8ec", edgecolor="#888888", label="0 observed stations"),
               Patch(facecolor="#dddddd", hatch="///", label="Not eligible / missing denominator")]
    colors = ["#d9f0d3", "#78c3a5", "#2a8f98", "#254b75"]
    if len(cuts) and positive.any():
        values = tracts.loc[positive, "stations_per_km2"]
        classes = np.searchsorted(cuts, values, side="left")
        bounds = [0, *cuts.tolist(), float(values.max())]
        for i, color in enumerate(colors):
            subset = tracts.loc[values.index[classes == i]]
            if len(subset):
                subset.plot(ax=ax, color=color, edgecolor="white", linewidth=.1)
            handles.append(Patch(facecolor=color, label=f">{bounds[i]:.1f}–{bounds[i+1]:.1f} stations/km²"))
    borough = tracts[["borough", "geometry"]].dissolve(by="borough")
    borough.boundary.plot(ax=ax, color="#4b4b4b", linewidth=.65)
    stations.loc[stations.GEOID.notna()].plot(ax=ax, markersize=1.7, color="#18212a", alpha=.65)
    handles.append(Line2D([], [], marker=".", linestyle="", color="#18212a", label="Observed station"))
    for name, row in borough.iterrows():
        point = row.geometry.representative_point()
        ax.annotate(name, (point.x, point.y), fontsize=9, fontweight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=.75, pad=1.5))
    ax.legend(handles=handles, loc="lower right", fontsize=8, framealpha=.95, title="Eligible residential tracts")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v/1000:.0f}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v/1000:.0f}"))
    ax.set(xlabel="UTM zone 18N easting (km)", ylabel="UTM zone 18N northing (km)")
    ax.set_title("Observed Citi Bike station density across NYC tracts", fontsize=16, loc="left", pad=20)
    fig.text(.09, .925, "September 2025 · land-area denominator · EPSG:32618", fontsize=10, color="#555555")
    return save(fig, "01_station_density_map.png",
                "Station coverage is shown for all five boroughs; zero means no station was observed in this month's trip records.",
                "Positive-density classes: citywide quartiles."), cuts.tolist()


def boxplot_density(tracts, group, name, title, x_label):
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), sharey=True)
    fig.subplots_adjust(left=.075, right=.98, bottom=.16, top=.88, wspace=.16, hspace=.42)
    eligible = tracts.loc[tracts.eligible]
    for ax, scope, color in zip(axes.flat, SCOPES, PALETTE):
        area = eligible if scope == "NYC" else eligible.loc[eligible.borough.eq(scope)]
        values = [area.loc[area[group].eq(q), "stations_per_km2"].dropna().to_numpy() for q in GROUPS]
        for i, val in enumerate(values, 1):
            if len(val):
                ax.boxplot([val], positions=[i], widths=.55, patch_artist=True,
                           boxprops=dict(facecolor=color, alpha=.65), medianprops=dict(color="#111111", linewidth=1.6),
                           flierprops=dict(marker=".", markersize=2.5, alpha=.35, markeredgecolor=color))
            else:
                ax.text(i, .08, "empty", ha="center", rotation=90, fontsize=8, transform=ax.get_xaxis_transform())
        ax.set_xticks([1, 2, 3, 4], [f"{q}\nn={len(v)}" for q, v in zip(GROUPS, values)])
        ax.set_title(scope, fontweight="bold", fontsize=11)
        ax.set_xlim(.4, 4.6)
        ax.set_yscale("symlog", linthresh=1)
        ax.set_ylim(bottom=-.05)
        ax.grid(axis="y", alpha=.15)
        ax.set_xlabel(x_label, fontsize=9)
    for ax in axes[:, 0]:
        ax.set_ylabel("Observed stations / land km²\n(symlog; linear from 0 to 1)")
    fig.suptitle(title, x=.075, ha="left", fontsize=16)
    return save(fig, name,
                "Boxes show tract density distributions, including zeros; citywide quartile thresholds are held fixed in every borough.",
                "Box: 25th–75th percentiles; line: median; whiskers: 1.5×IQR; dots: outliers.")


def usage_chart(comparisons):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharey=True)
    fig.subplots_adjust(left=.08, right=.98, bottom=.26, top=.83, wspace=.15)
    for ax, variable, label in zip(axes, ["income", "no_vehicle_share"], ["Tract income quartile", "No-vehicle household share quartile"]):
        for scope, color in zip(SCOPES, PALETTE):
            subset = comparisons.loc[comparisons.scope.eq(scope) & comparisons.variable.eq(variable)].set_index("quartile").reindex(GROUPS)
            values = subset.departures_per_station_median.to_numpy(dtype=float)
            ax.plot(range(1, 5), values, marker="o", label=scope + (" (no observations)" if np.isnan(values).all() else ""),
                    color=color, linewidth=2 if scope == "NYC" else 1.3, linestyle="-" if scope == "NYC" else "--")
        ax.set_xticks(range(1, 5), GROUPS)
        ax.set_xlabel(label)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=.15)
    axes[0].set_ylabel("Median September departures / observed station")
    fig.suptitle("Usage in tracts with observed stations", fontsize=16, x=.08, ha="left")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.51, .095), ncol=3, fontsize=9, frameon=False)
    return save(fig, "04_usage_by_demographics.png",
                "Median usage is compared only among tracts with observed stations; gaps denote empty groups, not zero usage.")


def scatter_chart(tracts, correlations):
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.subplots_adjust(left=.09, right=.98, bottom=.15, top=.9, wspace=.22, hspace=.35)
    eligible = tracts.loc[tracts.eligible]
    for row, (metric, ylabel) in enumerate([("stations_per_km2", "Observed stations / land km²"),
                                          ("departures_per_station", "September departures / observed station")]):
        for col, (variable, factor, xlabel) in enumerate([("income", .001, "Median household income (2024 dollars, thousands)"),
                                                       ("no_vehicle_share", 100, "Households with no vehicle (%)")]):
            ax = axes[row, col]
            for scope, color in zip(SCOPES[1:], PALETTE[1:]):
                data = eligible.loc[eligible.borough.eq(scope)].dropna(subset=[variable, metric])
                ax.scatter(data[variable] * factor, data[metric], s=8, color=color, alpha=.5, label=scope, edgecolors="none")
            rho = correlations.loc[correlations.scope.eq("NYC") & correlations.variable.eq(variable) & correlations.metric.eq(metric)].iloc[0]
            ax.set_title(f"NYC Spearman ρ = {rho.spearman_rho:.2f} · n = {rho.tracts:,}", fontsize=11)
            ax.set(xlabel=xlabel, ylabel=ylabel)
            ax.set_yscale("symlog", linthresh=1 if row == 0 else 100)
            ax.set_ylim(bottom=0)
            ax.grid(alpha=.12)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .066), ncol=5, fontsize=9, frameon=False)
    fig.suptitle("Tract demographics, coverage, and usage", fontsize=16, x=.09, ha="left")
    return save(fig, "05_demographic_scatterplots.png",
                "Each point is a tract; citywide associations can differ from within-borough patterns and do not identify individual riders.",
                "Y: symlog, linear below 1 station/km² or 100 departures/station.")


def daily_chart(daily):
    fig, ax = plt.subplots(figsize=(11, 5))
    fig.subplots_adjust(left=.10, right=.98, bottom=.21, top=.84)
    dates = pd.date_range("2025-09-01", "2025-09-30")
    pivot = daily.loc[daily.GEOID.notna()].groupby(["date", "member_casual"]).departures.sum().unstack(fill_value=0)
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.reindex(dates, fill_value=0)
    for category, color in [("member", "#0072B2"), ("casual", "#E69F00"), ("unknown", "#777777")]:
        if category in pivot:
            ax.plot(pivot.index.day, pivot[category], label=category.title(), color=color, marker="o", markersize=3)
    ax.set(xlabel="Day of September 2025", ylabel="Departures from assigned NYC stations (trips/day)", xlim=(1,30), ylim=(0,None))
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p: f"{v:,.0f}"))
    ax.grid(axis="y", alpha=.2)
    ax.legend(frameon=False)
    fig.suptitle("Daily Citi Bike departures by rider category", x=.1, ha="left", fontsize=16)
    return save(fig, "06_daily_departures.png",
                "Daily departures show the full month's observed activity by rider category, including stations in nonresidential NYC tracts.")


def create_figures(tracts, stations, daily, comparisons, correlations):
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titlelocation": "left"})
    coverage, cuts = map_coverage(tracts, stations)
    figures = [coverage,
               boxplot_density(tracts, "income_quartile", "02_density_by_income.png", "Observed station density by tract income", "Citywide income quartile"),
               boxplot_density(tracts, "no_vehicle_quartile", "03_density_by_vehicle_access.png", "Observed station density by vehicle availability", "Citywide no-vehicle share quartile"),
               usage_chart(comparisons), scatter_chart(tracts, correlations), daily_chart(daily)]
    (FIGURES / "captions.json").write_text(json.dumps({"figures": figures, "positive_density_breaks_stations_per_km2": cuts}, indent=2) + "\n")
    return figures
