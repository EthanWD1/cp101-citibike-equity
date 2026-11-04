"""Readable midterm figures; display geometry never changes the analytical tracts."""
import json
import os
from pathlib import Path
import textwrap

os.environ.setdefault("MPLCONFIGDIR", str(Path(".cache/matplotlib")))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import difference, union_all

from .config import RAW, PROCESSED, FIGURES, CRS, WATER_SOURCES, SCOPES, GROUPS

BOROUGH_COLORS = dict(zip(SCOPES, ["#252525", "#0072B2", "#D69000", "#008B69", "#B85F95", "#777777"]))
DENSITY_COLORS = ["#c7e9d9", "#78c3af", "#288b9b", "#204e76"]
INK = "#21343e"
SOURCE = "Citi Bike: September 2025 · ACS: 2020–2024 · TIGER/Line: 2024 · Group PAIR"


def heading(fig, title, subtitle, size=17):
    fig.text(.045, .968, title, ha="left", va="top", fontsize=size, fontweight="bold", color=INK)
    fig.text(.045, .927, subtitle, ha="left", va="top", fontsize=11, color="#52636c")


def save(fig, name, caption, note="", population=""):
    """Reserve space for captions rather than squeezing them against an axis label."""
    width = int(fig.get_figwidth() * 13)
    fig.text(.045, .052, textwrap.fill(caption, width), fontsize=10, va="bottom", color=INK)
    source = SOURCE + (" · " + note if note else "")
    fig.text(.045, .012, textwrap.fill(source, int(width * 1.2)), fontsize=8.5, va="bottom", color="#5b6870")
    fig.savefig(FIGURES / name, dpi=190, facecolor="white")
    plt.close(fig)
    return {"file": name, "caption": caption, "population": population, "note": note}


def display_land(tracts, water):
    """Return a geometry-only rendering change while retaining every row and attribute."""
    if tracts.crs != water.crs:
        water = water.to_crs(tracts.crs)
    result = tracts.copy()
    water_union = union_all(water.geometry.to_numpy())
    result["geometry"] = difference(tracts.geometry.to_numpy(), water_union)
    if not result.geometry.is_valid.all():
        raise ValueError("Water subtraction produced invalid display geometry")
    if (result.eligible & result.geometry.is_empty).any():
        raise ValueError("Water subtraction hid an eligible residential tract")
    return result


def load_display_geography(tracts):
    water = gpd.GeoDataFrame(pd.concat([gpd.read_file(RAW / name).to_crs(CRS)
                                       for name in WATER_SOURCES], ignore_index=True), crs=CRS)
    return display_land(tracts, water), water


def quartile_labels(variable, thresholds, multiline=False):
    """Labels are rounded for display; the saved quartile assignments remain authoritative."""
    a, b, c = thresholds[variable]
    if variable == "income":
        ranges = [f"≤${a/1000:.1f}k", f"${a/1000:.1f}–{b/1000:.1f}k",
                  f"${b/1000:.1f}–{c/1000:.1f}k", f">${c/1000:.1f}k"]
    else:
        ranges = [f"≤{a*100:.1f}%", f"{a*100:.1f}–{b*100:.1f}%",
                  f"{b*100:.1f}–{c*100:.1f}%", f">{c*100:.1f}%"]
    sep = "\n" if multiline else "  "
    return [q + sep + value for q, value in zip(GROUPS, ranges)]


def map_coverage(tracts, land, water):
    fig = plt.figure(figsize=(9, 7.6))
    ax = fig.add_axes([.025, .145, .655, .735])
    eligible = tracts.eligible
    zero_count = int((eligible & tracts.observed_stations.eq(0)).sum())
    zero_pct = 100 * zero_count / int(eligible.sum())
    heading(fig, f"{zero_pct:.1f}% of residential tracts had no observed station",
            "Observed Citi Bike stations per km² of land · September 2025", size=16)
    water.plot(ax=ax, color="#e8f2f7", edgecolor="none", zorder=0)
    valid = land.eligible & land.stations_per_km2.notna()
    zero = valid & land.observed_stations.eq(0)
    positive = valid & land.observed_stations.gt(0)
    land.loc[~valid & ~land.geometry.is_empty].plot(ax=ax, color="#d9d9d9", edgecolor="#b7b7b7", linewidth=.15, hatch="///")
    land.loc[zero].plot(ax=ax, color="#fbf4df", edgecolor="#d4d0c5", linewidth=.20)
    values = tracts.loc[positive, "stations_per_km2"]
    cuts = values.quantile([.25, .50, .75]).to_numpy()
    classes = np.searchsorted(cuts, values, side="left")
    bounds = [0, *cuts.tolist(), float(values.max())]
    for i, color in enumerate(DENSITY_COLORS):
        subset = land.loc[values.index[classes == i]]
        if len(subset):
            subset.plot(ax=ax, color=color, edgecolor="#ffffff", linewidth=.20)
    boroughs = land.loc[~land.geometry.is_empty, ["borough", "geometry"]].dissolve(by="borough")
    boroughs.boundary.plot(ax=ax, color="#59666d", linewidth=.65)
    for name, row in boroughs.iterrows():
        point = row.geometry.representative_point()
        if name == "Manhattan":
            ax.annotate(name, (point.x, point.y), xytext=(-52, 26), textcoords="offset points",
                        ha="right", fontsize=11, fontweight="bold", color=INK,
                        arrowprops=dict(arrowstyle="-", color=INK, lw=.8),
                        bbox=dict(facecolor="white", edgecolor="none", alpha=.9, pad=2))
        else:
            ax.annotate(name, (point.x, point.y), ha="center", fontsize=11, fontweight="bold", color=INK,
                        bbox=dict(facecolor="white", edgecolor="none", alpha=.85, pad=2))
    xmin, ymin, xmax, ymax = land.total_bounds
    ax.set_xlim(xmin - 1500, xmax + 1500)
    ax.set_ylim(ymin - 1500, ymax + 1500)
    ax.set_aspect("equal")
    ax.set_axis_off()
    # EPSG:32618 coordinates are meters; the scale is independent of physical image size.
    x0, y0 = xmin + 2000, ymin + 1500
    ax.plot([x0, x0+5000], [y0, y0], color=INK, lw=2.5)
    for x in [x0, x0+5000]:
        ax.plot([x, x], [y0-250, y0+250], color=INK, lw=1)
    ax.text(x0+2500, y0+650, "5 km", ha="center", fontsize=10, color=INK)
    ax.annotate("N", xy=(.08, .93), xytext=(.08, .85), xycoords="axes fraction", ha="center",
                fontsize=11, fontweight="bold", arrowprops=dict(arrowstyle="-|>", color=INK))
    legend_ax = fig.add_axes([.71, .15, .28, .70])
    legend_ax.axis("off")
    handles = [Patch(facecolor="#fbf4df", edgecolor="#b7ad95", label="0 observed stations")]
    handles += [Patch(facecolor=color, label=f">{bounds[i]:.1f}–{bounds[i+1]:.1f}") for i,color in enumerate(DENSITY_COLORS)]
    handles += [Patch(facecolor="#d9d9d9", hatch="///", edgecolor="#b7b7b7", label="Not eligible"),
                Patch(facecolor="#e8f2f7", label="Water")]
    legend_ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=11,
                     title="Observed stations\nper km² of land", title_fontsize=12,
                     labelspacing=.85, handlelength=1.7, borderaxespad=0)
    legend_ax.text(0, .39, f"{zero_count:,} of {int(eligible.sum()):,}\neligible tracts had\nno observed station.",
                   fontsize=12, fontweight="bold", color=INK, linespacing=1.5, va="top")
    legend_ax.text(0, .20, "Eligible: positive households,\npopulation, and land area.\n\nZero means none observed\nin the month's trip records.",
                   fontsize=10, color="#52636c", linespacing=1.4, va="top")
    caption = "Observed coverage varies across the five boroughs; no observed station within a tract does not establish a lack of nearby access."
    result = save(fig, "01_station_density_map.png", caption,
                  "Positive classes: citywide quartiles · Water removed for display only · EPSG:32618",
                  "All NYC tracts shown; density comparisons use eligible residential tracts")
    return result, cuts.tolist(), {
        "eligible_tracts": int(eligible.sum()), "zero_station_tracts": zero_count, "zero_station_pct": zero_pct,
        "valid_display_geometries": bool(land.geometry.is_valid.all()),
        "eligible_display_geometries_lost": int((eligible & land.geometry.is_empty).sum()),
        "tract_ids_preserved": land.GEOID.tolist() == tracts.GEOID.tolist(),
        "analytical_attributes_preserved": land.drop(columns="geometry").equals(tracts.drop(columns="geometry")),
        "water_archives": list(WATER_SOURCES),
    }


def comparison_block(comparisons, scope, variable):
    return comparisons.loc[comparisons.scope.eq(scope) & comparisons.variable.eq(variable)].set_index("quartile").reindex(GROUPS)


def density_chart(comparisons, variable, thresholds):
    fig = plt.figure(figsize=(13, 10.8))
    income = variable == "income"
    title = ("Income–coverage patterns differ across boroughs" if income else
             "Higher no-vehicle shares coincide with greater observed coverage")
    city = comparison_block(comparisons, "NYC", variable)
    subtitle = ("Median and middle 50% · Eligible tracts with income estimates, including those with zero stations" if income else
                f"NYC: {city.loc['Q1','zero_station_pct']:.1f}% with no station in the lowest group vs. "
                f"{city.loc['Q4','zero_station_pct']:.1f}% in the highest · All eligible tracts")
    heading(fig, title, subtitle, size=16)
    grid = fig.add_gridspec(3, 2, left=.045, right=.98, top=.865, bottom=.16, wspace=.16, hspace=.47)
    labels = quartile_labels(variable, thresholds)
    records = []
    for pos, scope in enumerate(SCOPES):
        sub = grid[pos//2, pos%2].subgridspec(1, 3, width_ratios=[1.35, 2.25, 1.1], wspace=.06)
        label_ax, ax, number_ax = [fig.add_subplot(sub[0, j]) for j in range(3)]
        for item in [label_ax, ax, number_ax]:
            item.set_ylim(3.6, -.7)
        label_ax.axis("off")
        number_ax.axis("off")
        label_ax.set_title(scope, color=BOROUGH_COLORS[scope], fontsize=13, fontweight="bold", pad=13)
        number_ax.text(0, -.85, "No station | n", fontsize=9, color="#52636c")
        block = comparison_block(comparisons, scope, variable)
        for i, (quartile, row) in enumerate(block.iterrows()):
            count = int(row.tracts)
            label_ax.text(0, i, labels[i], va="center", fontsize=10)
            if count:
                lo, med, hi = [float(row[f"stations_per_km2_{stat}"]) for stat in ["p25", "median", "p75"]]
                ax.hlines(i, lo, hi, color=BOROUGH_COLORS[scope], lw=5, alpha=.45)
                ax.plot(med, i, "o", color=BOROUGH_COLORS[scope], ms=7, clip_on=False, zorder=5)
                number_ax.text(0, i, f"{row.zero_station_pct:.1f}% | {count:,}", va="center", fontsize=10)
            else:
                lo = med = hi = None
                ax.text(2, i, "No eligible tracts", va="center", fontsize=9, color="#777777")
                number_ax.text(0, i, "— | 0", va="center", fontsize=10)
            records.append({"scope":scope,"variable":variable,"quartile":quartile,"tracts":count,
                            "zero_station_pct":float(row.zero_station_pct) if count else None,
                            "p25":lo,"median":med,"p75":hi})
        ax.set_xlim(0, 60)
        ax.set_xticks([0, 20, 40, 60])
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.grid(axis="x", color="#dddddd", lw=.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("Stations / km² of land", fontsize=9)
    fig.legend(handles=[Line2D([0],[0],marker="o",lw=0,color=INK,label="Median tract density"),
                        Line2D([0],[0],lw=5,alpha=.45,color=INK,label="Middle 50% of tracts (25th–75th percentiles)")],
               loc="lower center", bbox_to_anchor=(.5,.095), ncol=2, frameon=False, fontsize=10)
    caption = ("Income groups show different coverage patterns across boroughs; a zero median means at least half of that group's tracts have no observed station."
               if income else "Tracts with more households without a vehicle generally show greater station coverage citywide, while borough comparisons reveal substantial differences.")
    name = "02_density_by_income.png" if income else "03_density_by_vehicle_access.png"
    return save(fig, name, caption,
                ("Income: 2024 dollars" if income else "Groups: % of households without a vehicle") +
                " · Fixed citywide groups; labels rounded · Intervals describe tracts, not uncertainty · n = eligible tracts",
                "Eligible residential tracts with the relevant demographic estimate; zero-station tracts included"), records


def usage_cells(comparisons, variable):
    records = []
    for scope in SCOPES:
        for quartile, row in comparison_block(comparisons, scope, variable).iterrows():
            n = int(row.served_tracts)
            records.append({"scope":scope,"variable":variable,"quartile":quartile,"served_tracts":n,
                            "median":float(row.departures_per_station_median) if n else None,
                            "small_group":0 < n < 5})
    return records


def usage_chart(comparisons, thresholds):
    fig = plt.figure(figsize=(13, 8))
    heading(fig, "Compare usage only where stations were observed",
            "Median September departures per observed station · n = eligible tracts with stations and a demographic estimate", size=17)
    records = usage_cells(comparisons, "income") + usage_cells(comparisons, "no_vehicle_share")
    vmax = np.ceil(max(r["median"] for r in records if r["median"] is not None)/1000)*1000
    norm = Normalize(0, vmax)
    cmap = plt.get_cmap("Blues").copy()
    cmap.set_bad("#ededed")
    for i, variable in enumerate(["income", "no_vehicle_share"]):
        ax = fig.add_axes([.14 + i*.43, .23, .355, .54])
        subset = records[i*24:(i+1)*24]
        values = np.array([r["median"] if r["median"] is not None else np.nan for r in subset]).reshape(6,4)
        im = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(4), quartile_labels(variable, thresholds, multiline=True), fontsize=10)
        ax.xaxis.tick_top()
        ax.tick_params(length=0, pad=8)
        ax.set_yticks(range(6), SCOPES if i == 0 else [""]*6, fontsize=11)
        ax.set_title("Household income (2024 dollars)" if i == 0 else "Households without a vehicle", fontsize=13, pad=47)
        ax.set_xticks(np.arange(-.5,4,1),minor=True)
        ax.set_yticks(np.arange(-.5,6,1),minor=True)
        ax.grid(which="minor",color="white",linewidth=2)
        ax.tick_params(which="minor",bottom=False,left=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for j, record in enumerate(subset):
            row, col = divmod(j, 4)
            n, median = record["served_tracts"], record["median"]
            label = "Not defined\nn = 0" if not n else f"{median:,.0f}\nn = {n:,}" + (" †" if record["small_group"] else "")
            color = "white" if median is not None and norm(median) > .7 else "#10222b"
            ax.text(col,row,label,ha="center",va="center",fontsize=11.5,color=color)
            if record["small_group"]:
                ax.add_patch(Rectangle((col-.48,row-.48),.96,.96,fill=False,edgecolor="#d17a00",lw=2))
    fig.text(.14,.188,"† Fewer than 5 contributing tracts: interpret these medians cautiously. Gray cells have no defined usage.",fontsize=10,color=INK)
    cax = fig.add_axes([.28,.137,.51,.018])
    cb = fig.colorbar(im,cax=cax,orientation="horizontal")
    cb.ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_: f"{x:,.0f}"))
    cb.ax.tick_params(labelsize=9)
    cb.set_label("Monthly departures per observed station (median across tracts)",fontsize=10)
    caption = "Usage differs among tracts with observed stations; empty groups, including every Staten Island group, have undefined usage rather than zero usage."
    return save(fig,"04_usage_by_demographics.png",caption,
                "Fixed citywide groups; labels rounded · A tract's usage = departures ÷ observed stations",
                "Eligible residential tracts with a demographic estimate and at least one observed station"), records


def scatter_chart(tracts, correlations):
    fig, axes = plt.subplots(2,2,figsize=(13,10))
    fig.subplots_adjust(left=.095,right=.97,bottom=.20,top=.85,wspace=.25,hspace=.48)
    heading(fig,"Citywide income is more closely associated with usage than coverage",
            "Each point is one eligible tract · Density includes zero-station tracts; usage requires at least one station",size=16)
    records = []
    for col, variable in enumerate(["income","no_vehicle_share"]):
        for row, metric in enumerate(["stations_per_km2","departures_per_station"]):
            ax = axes[row,col]
            data = tracts.loc[tracts.eligible & tracts[variable].notna() & tracts[metric].notna()]
            factor = .001 if variable == "income" else 100
            for borough in SCOPES[1:]:
                part = data.loc[data.borough.eq(borough)]
                censored = part.income_censored.astype(bool) if variable == "income" else pd.Series(False,index=part.index)
                ax.scatter(part.loc[~censored,variable]*factor,part.loc[~censored,metric],s=14,
                           alpha=.50,color=BOROUGH_COLORS[borough],edgecolors="none",zorder=3)
                if censored.any():
                    ax.scatter(part.loc[censored,variable]*factor,part.loc[censored,metric],s=38,marker=">",
                               alpha=.9,color=BOROUGH_COLORS[borough],edgecolors=INK,linewidths=.4,zorder=4)
            corr = correlations.loc[correlations.scope.eq("NYC") & correlations.variable.eq(variable) & correlations.metric.eq(metric)].iloc[0]
            ax.set_title(f"Spearman ρ = {corr.spearman_rho:.2f}  ·  n = {len(data):,} tracts",fontsize=11,pad=9)
            if variable == "income":
                ax.set_xlim(-5,260)
                ax.set_xticks([0,50,100,150,200,250],["$0","$50k","$100k","$150k","$200k","$250k+"])
                ax.set_xlabel("Median household income (2024 dollars)",fontsize=10)
            else:
                ax.set_xlim(-2,102)
                ax.set_xticks([0,20,40,60,80,100],["0%","20%","40%","60%","80%","100%"])
                ax.set_xlabel("Households without a vehicle (%)",fontsize=10)
            if row == 0:
                ax.set_ylim(-2,60)
                ax.set_yticks([0,15,30,45,60])
                ax.set_ylabel("Observed stations / km² of land",fontsize=10)
                zero = int(data.observed_stations.eq(0).sum())
                ax.axhline(0,color="#7a858b",lw=.7,zorder=1)
                ax.text(.025,.965,f"At zero: {zero:,} tracts ({100*zero/len(data):.1f}%)",transform=ax.transAxes,
                        va="top",fontsize=10,color=INK,bbox=dict(facecolor="white",alpha=.88,edgecolor="none",pad=2))
            else:
                zero = 0
                ax.set_ylim(0,15000)
                ax.set_yticks([0,5000,10000,15000])
                ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f"{x:,.0f}"))
                ax.set_ylabel("September departures / station",fontsize=10)
            ax.tick_params(labelsize=9)
            ax.grid(color="#e5e5e5",lw=.5)
            ax.set_axisbelow(True)
            records.append({"variable":variable,"metric":metric,"plotted_tracts":len(data),
                            "correlation_tracts":int(corr.tracts),"zero_station_tracts":zero,
                            "censored_income_tracts":int(data.income_censored.sum()) if variable=="income" else 0,
                            "all_values_in_range":bool(data[metric].between(0,60 if row==0 else 15000).all())})
    handles = [Line2D([0],[0],marker="o",lw=0,color=BOROUGH_COLORS[b],label=b) for b in SCOPES[1:]]
    handles += [Line2D([0],[0],marker=">",lw=0,color=INK,label="Income reported as $250,000+ (censored)")]
    fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.5,.102),ncol=3,frameon=False,fontsize=10)
    caption = "Citywide associations can obscure borough differences, and overlapping zero-density points represent many tracts without an observed station."
    return save(fig,"05_demographic_scatterplots.png",caption,
                "Spearman ρ: rank association, −1 decreasing / 0 no monotonic pattern / +1 increasing; not causation",
                "Eligible residential tracts with complete values for each panel; every observation retained"), records


def daily_summary(daily):
    data = daily.loc[daily.GEOID.notna()].copy()
    data["date"] = pd.to_datetime(data.date)
    pivot = data.groupby(["date","member_casual"]).departures.sum().unstack(fill_value=0)
    pivot = pivot.reindex(pd.date_range("2025-09-01","2025-09-30"),fill_value=0)
    weekend = pivot.index.day_of_week >= 5
    return pivot, {"weekend_days":int(weekend.sum()),"weekday_days":int((~weekend).sum()),
                   "categories":{category:{"departures":int(pivot[category].sum()),
                                            "weekend_daily_mean":float(pivot.loc[weekend,category].mean()),
                                            "weekday_daily_mean":float(pivot.loc[~weekend,category].mean())}
                                 for category in pivot.columns}}


def daily_chart(daily):
    pivot, summary = daily_summary(daily)
    fig, ax = plt.subplots(figsize=(10.5,5))
    fig.subplots_adjust(left=.095,right=.97,bottom=.285,top=.78)
    heading(fig,"Members make most trips; casual daily averages are higher on weekends",
            "NYC station departures, September 2025 · Shaded bands mark Saturdays and Sundays",size=13.5)
    for day in pivot.index[pivot.index.day_of_week >= 5].day:
        ax.axvspan(day-.5,day+.5,color="#eceeef",zorder=0)
    colors = {"member":"#0072B2","casual":"#B47700"}
    for category in pivot:
        ax.plot(pivot.index.day,pivot[category],color=colors.get(category,"#777777"),lw=2)
        ax.text(30.5,pivot[category].iloc[-1],category.title(),va="center",fontsize=11,
                fontweight="bold",color=colors.get(category,"#777777"))
    ax.set_xlim(.5,34)
    ax.set_ylim(0,180000)
    ax.set_yticks([0,40000,80000,120000,160000])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_:"0" if x==0 else f"{x/1000:.0f}k"))
    ax.set_xticks([1,8,15,22,29],["Mon 1","Mon 8","Mon 15","Mon 22","Mon 29"])
    ax.set_ylabel("Departures per day",fontsize=10)
    ax.set_xlabel("September 2025",fontsize=10)
    ax.grid(axis="y",color="#dddddd",lw=.6)
    ax.set_axisbelow(True)
    casual = summary["categories"]["casual"]
    fig.text(.095,.153,f"Casual daily average: {casual['weekend_daily_mean']/1000:.1f}k on weekends (8 days) vs. "
             f"{casual['weekday_daily_mean']/1000:.1f}k on weekdays (22 days)",fontsize=10.5,color=INK)
    caption = "Casual departures averaged more on weekends than weekdays during this month; the chart does not establish why."
    return save(fig,"06_daily_departures.png",caption,
                "All matched NYC station departures, including nonresidential tracts; k = 1,000",
                "All retained departures assigned to NYC stations, including nonresidential tracts"), summary


def create_figures(tracts, stations, daily, comparisons, correlations):
    """Shared by the raw-input pipeline and the processed-table preview command."""
    FIGURES.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":11,"axes.spines.top":False,
                         "axes.spines.right":False,"axes.titlelocation":"left","text.parse_math":False})
    thresholds = {variable:tracts.loc[tracts.eligible,variable].dropna().quantile([.25,.5,.75]).tolist()
                  for variable in ["income","no_vehicle_share"]}
    land, water = load_display_geography(tracts)
    map_meta, cuts, map_checks = map_coverage(tracts,land,water)
    income_meta, income_records = density_chart(comparisons,"income",thresholds)
    vehicle_meta, vehicle_records = density_chart(comparisons,"no_vehicle_share",thresholds)
    usage_meta, usage_records = usage_chart(comparisons,thresholds)
    scatter_meta, scatter_records = scatter_chart(tracts,correlations)
    daily_meta, daily_records = daily_chart(daily)
    figures = [map_meta,income_meta,vehicle_meta,usage_meta,scatter_meta,daily_meta]
    (FIGURES / "captions.json").write_text(json.dumps({"figures":figures,"positive_density_breaks":cuts,
                                                     "revision":"2026-11-03"},indent=2)+"\n")
    (FIGURES / "figure_data.json").write_text(json.dumps({"map":map_checks,"exact_group_thresholds":thresholds,
        "density_groups":income_records+vehicle_records,"usage_groups":usage_records,
        "scatter_panels":scatter_records,"daily":daily_records},indent=2,allow_nan=False)+"\n")
    return figures


def regenerate_from_processed():
    tracts = gpd.read_file(PROCESSED / "tract_metrics.gpkg")
    stations = pd.read_csv(PROCESSED / "observed_stations.csv",dtype={"station_id":str,"GEOID":str})
    daily = pd.read_csv(PROCESSED / "station_daily_departures.csv",dtype={"station_id":str,"GEOID":str})
    comparisons = pd.read_csv(PROCESSED / "quartile_comparisons.csv")
    correlations = pd.read_csv(PROCESSED / "spearman_correlations.csv")
    create_figures(tracts,stations,daily,comparisons,correlations)
    print("Regenerated six figures from processed tables.")


if __name__ == "__main__":
    regenerate_from_processed()
