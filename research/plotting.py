from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_carbon_series(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    if df.empty:
        return
    fig,ax=plt.subplots(figsize=(8,4.5))
    for aoi,group in df.groupby("aoi_id"):
        g=group.sort_values("year")
        ax.plot(g["year"],g["mean_carbon_t_ha"],marker="o",label=str(aoi))
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean carbon stock, tC/ha")
    ax.set_title("Annual CCI carbon trajectory")
    ax.legend()
    ax.grid(True,alpha=0.25)
    _save(fig,out/"carbon_trajectory.png")


def plot_uncertainty(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    required={"aoi_id","scenario","E_tco2e","L","U"}
    if df.empty or not required.issubset(df.columns):
        return
    df=df.dropna(subset=["E_tco2e","L","U"])
    if df.empty:
        return
    labels=[f"{r.aoi_id}\n{r.scenario}" for r in df.itertuples()]
    centers=df["E_tco2e"].to_numpy(float)
    lower=centers-df["L"].to_numpy(float)
    upper=df["U"].to_numpy(float)-centers
    fig,ax=plt.subplots(figsize=(max(8,len(df)*0.9),4.8))
    ax.errorbar(range(len(df)),centers,yerr=[lower,upper],fmt="o",capsize=4)
    ax.set_xticks(range(len(df)),labels,rotation=35,ha="right")
    ax.set_ylabel("E, tCO2e")
    ax.set_title("Uncertainty sensitivity across dependence scenarios")
    ax.grid(True,axis="y",alpha=0.25)
    _save(fig,out/"uncertainty_sensitivity.png")


def plot_change_methods(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    if df.empty or not {"aoi_id","method","detected_area_ha"}.issubset(df.columns):
        return
    pivot=df.pivot(index="method",columns="aoi_id",values="detected_area_ha")
    fig,ax=plt.subplots(figsize=(8,4.8))
    pivot.plot(kind="bar",ax=ax)
    ax.set_ylabel("Detected disturbance area, ha")
    ax.set_title("Change detector comparison: changed vs control")
    ax.legend(title="AOI")
    ax.grid(True,axis="y",alpha=0.25)
    _save(fig,out/"change_method_comparison.png")


def plot_thresholds(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    if df.empty or not {"z_threshold","detected_area_ha"}.issubset(df.columns):
        return
    fig,ax=plt.subplots(figsize=(7,4.5))
    ax.plot(df["z_threshold"],df["detected_area_ha"],marker="o")
    ax.set_xlabel("Robust z threshold")
    ax.set_ylabel("Detected disturbance area, ha")
    ax.set_title("Threshold sensitivity on changed AOI")
    ax.grid(True,alpha=0.25)
    _save(fig,out/"change_threshold_sensitivity.png")


def plot_baseline(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    if df.empty or not {"aoi_id","baseline_scenario","Q"}.issubset(df.columns):
        return
    df=df.dropna(subset=["Q"])
    if df.empty:
        return
    pivot=df.pivot(index="aoi_id",columns="baseline_scenario",values="Q")
    fig,ax=plt.subplots(figsize=(7,4.5))
    pivot.plot(kind="bar",ax=ax)
    ax.set_ylabel("Potential units Q")
    ax.set_title("Baseline sensitivity (official vs research-only counterfactual)")
    ax.legend(title="Scenario")
    ax.grid(True,axis="y",alpha=0.25)
    _save(fig,out/"baseline_sensitivity.png")


def plot_temporal_rho(rows: list[dict], out: Path) -> None:
    df=pd.DataFrame(rows)
    if df.empty or not {"aoi_id","median","q25","q75"}.issubset(df.columns):
        return
    df=df.dropna(subset=["median","q25","q75"])
    if df.empty:
        return
    centers=df["median"].to_numpy(float)
    lower=centers-df["q25"].to_numpy(float)
    upper=df["q75"].to_numpy(float)-centers
    fig,ax=plt.subplots(figsize=(7,4.5))
    ax.errorbar(range(len(df)),centers,yerr=[lower,upper],fmt="o",capsize=4)
    ax.axhline(0,linewidth=1)
    ax.set_xticks(range(len(df)),df["aoi_id"].astype(str),rotation=25,ha="right")
    ax.set_ylabel("Implied temporal rho")
    ax.set_title("CCI 2019→2020 temporal-dependence diagnostic (median/IQR)")
    ax.grid(True,axis="y",alpha=0.25)
    _save(fig,out/"temporal_rho_diagnostic.png")


def generate_research_figures(
    *,
    carbon_series:list[dict],
    uncertainty:list[dict],
    baseline:list[dict],
    changes:list[dict],
    thresholds:list[dict],
    temporal:list[dict],
    output_dir:Path,
) -> None:
    plot_carbon_series(carbon_series,output_dir)
    plot_uncertainty(uncertainty,output_dir)
    plot_baseline(baseline,output_dir)
    plot_change_methods(changes,output_dir)
    plot_thresholds(thresholds,output_dir)
    plot_temporal_rho(temporal,output_dir)
