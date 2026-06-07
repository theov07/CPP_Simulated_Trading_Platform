from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
RESULTS_DIR = PROJECT_ROOT / "results"
BUILD_DIR = PROJECT_ROOT / "build"
BINARY_NAME = "trading_sim.exe" if os.name == "nt" else "trading_sim"
BINARY_PATH = BUILD_DIR / BINARY_NAME

STRATEGIES = {
    "momentum": "Short/long moving-average momentum",
    "mean_reversion": "Rolling z-score mean reversion",
    "bollinger": "Bollinger Bands mean reversion",
    "ma_cross": "Longer moving-average crossover",
}

DATASET_DESCRIPTIONS = {
    "test_events.csv": "Main benchmark order-flow scenario",
    "trend_events.csv": "Small upward-trend scenario",
    "mean_reversion_events.csv": "Small oscillating mean-reversion scenario",
}

NAVY = "#07111f"
NAVY_2 = "#0d1b2d"
PANEL = "#101f33"
BORDER = "#20324d"
TEXT = "#e8edf5"
MUTED = "#94a3b8"
BLUE = "#4f8cff"
BLUE_SOFT = "#7aa2f7"
RED = "#cf4d5c"
RED_SOFT = "#e06c75"
GREEN = "#55c28b"
AMBER = "#d6a84f"
GRID = "rgba(148, 163, 184, 0.18)"


st.set_page_config(
    page_title="C++ Trading Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_theme() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --navy: {NAVY};
            --navy-2: {NAVY_2};
            --panel: {PANEL};
            --border: {BORDER};
            --text: {TEXT};
            --muted: {MUTED};
            --blue: {BLUE};
            --red: {RED};
        }}

        * {{
            letter-spacing: 0 !important;
        }}

        .stApp {{
            background:
                radial-gradient(circle at 15% 0%, rgba(79, 140, 255, 0.12), transparent 26rem),
                linear-gradient(180deg, #07111f 0%, #0a1424 42%, #07111f 100%);
            color: var(--text);
        }}

        [data-testid="stSidebar"] {{
            background: #060d18;
            border-right: 1px solid var(--border);
        }}

        [data-testid="stSidebar"] * {{
            color: var(--text);
        }}

        h1, h2, h3 {{
            color: var(--text);
            font-weight: 650;
        }}

        p, li, label, span {{
            color: var(--text);
        }}

        .block-container {{
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1440px;
        }}

        .hero {{
            border: 1px solid var(--border);
            background: linear-gradient(135deg, rgba(16, 31, 51, 0.94), rgba(8, 18, 32, 0.96));
            border-radius: 8px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
        }}

        .hero h1 {{
            margin: 0;
            font-size: 2rem;
            line-height: 1.2;
        }}

        .hero p {{
            margin: 0.45rem 0 0 0;
            color: var(--muted);
            font-size: 0.98rem;
        }}

        .status-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.9rem;
        }}

        .status-pill {{
            border: 1px solid var(--border);
            background: rgba(13, 27, 45, 0.82);
            border-radius: 999px;
            padding: 0.35rem 0.7rem;
            color: var(--muted);
            font-size: 0.85rem;
        }}

        .status-pill strong {{
            color: var(--text);
            font-weight: 600;
        }}

        .metric-panel {{
            border: 1px solid var(--border);
            background: rgba(16, 31, 51, 0.78);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            min-height: 6.1rem;
        }}

        .metric-label {{
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }}

        .metric-value {{
            color: var(--text);
            font-size: 1.45rem;
            font-weight: 650;
            line-height: 1.15;
        }}

        .metric-caption {{
            color: var(--muted);
            font-size: 0.78rem;
            margin-top: 0.45rem;
        }}

        .section-card {{
            border: 1px solid var(--border);
            background: rgba(16, 31, 51, 0.72);
            border-radius: 8px;
            padding: 1rem;
        }}

        div[data-testid="stMetric"] {{
            border: 1px solid var(--border);
            background: rgba(16, 31, 51, 0.72);
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
        }}

        div[data-testid="stMetricLabel"] {{
            color: var(--muted);
        }}

        div[data-testid="stMetricValue"] {{
            color: var(--text);
        }}

        .stButton > button {{
            border: 1px solid var(--border);
            background: linear-gradient(180deg, #162844 0%, #0f1e33 100%);
            color: var(--text);
            border-radius: 6px;
            height: 2.65rem;
            font-weight: 600;
        }}

        .stButton > button:hover {{
            border-color: var(--red);
            color: #ffffff;
        }}

        .stDownloadButton > button {{
            border-radius: 6px;
            border: 1px solid var(--border);
            background: #0f1e33;
            color: var(--text);
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}

        hr {{
            border-color: var(--border);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, value: str) -> str:
    return f'<span class="status-pill">{label}: <strong>{value}</strong></span>'


def hero(dataset: str, strategy: str) -> None:
    binary_status = "ready" if BINARY_PATH.exists() else "missing"
    output_status = "ready" if (OUTPUT_DIR / "risk_report.csv").exists() else "empty"
    st.markdown(
        f"""
        <div class="hero">
            <h1>C++17 Simulated Trading Platform</h1>
            <p>Streamlit dashboard for running the C++ trading engine and reviewing market data, trades, portfolio P&L, and risk metrics.</p>
            <div class="status-row">
                {status_pill("Market scenario", dataset)}
                {status_pill("Strategy", strategy)}
                {status_pill("C++ binary", binary_status)}
                {status_pill("Output", output_status)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_command(command: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = "\n".join(part for part in [exc.stdout or "", exc.stderr or ""] if part)
        return 124, f"Command timed out after {timeout}s.\n{output}".strip()

    output = "\n".join(
        part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
    )
    return completed.returncode, output


def configure_and_build() -> tuple[bool, str]:
    configure_code, configure_log = run_command(["cmake", "-S", ".", "-B", "build"], timeout=120)
    if configure_code != 0:
        return False, configure_log

    build_code, build_log = run_command(["cmake", "--build", "build"], timeout=180)
    combined_log = "\n\n".join(part for part in [configure_log, build_log] if part)
    return build_code == 0, combined_log


def run_simulation(dataset_path: Path, strategy: str, build_first: bool) -> tuple[bool, str]:
    logs: list[str] = []

    if build_first or not BINARY_PATH.exists():
        ok, build_log = configure_and_build()
        logs.append(build_log)
        if not ok:
            return False, "\n\n".join(logs)

    relative_dataset = dataset_path.relative_to(PROJECT_ROOT)
    code, run_log = run_command([str(BINARY_PATH), str(relative_dataset), strategy], timeout=120)
    logs.append(run_log)
    return code == 0, "\n\n".join(logs)


def available_datasets() -> list[Path]:
    return sorted(DATA_DIR.glob("*.csv"))


@st.cache_data(show_spinner=False)
def read_csv_cached(path: str, modified_at: float) -> pd.DataFrame:
    _ = modified_at
    return pd.read_csv(path)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_csv_cached(str(path), path.stat().st_mtime)


def read_outputs() -> dict[str, pd.DataFrame]:
    return {
        "market": read_csv(OUTPUT_DIR / "market_data.csv"),
        "trades": read_csv(OUTPUT_DIR / "trades.csv"),
        "equity": read_csv(OUTPUT_DIR / "equity_curve.csv"),
        "risk": read_csv(OUTPUT_DIR / "risk_report.csv"),
        "comparison": read_csv(RESULTS_DIR / "strategy_comparison.csv"),
    }


def risk_dict(risk: pd.DataFrame) -> dict[str, str]:
    if risk.empty or not {"metric", "value"}.issubset(risk.columns):
        return {}
    return dict(zip(risk["metric"].astype(str), risk["value"].astype(str)))


def as_float(value: str | float | int | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_money(value: float) -> str:
    return f"{value:,.2f}"


def format_ratio(value: float) -> str:
    return f"{value:.4f}"


def format_int(value: float) -> str:
    return f"{int(round(value)):,}"


def add_time_column(df: pd.DataFrame) -> pd.DataFrame:
    plotted = df.copy()
    if "timestamp" in plotted.columns:
        plotted["datetime"] = pd.to_datetime(plotted["timestamp"], unit="s")
    return plotted


def plot_layout(
    fig: go.Figure,
    height: int = 420,
    *,
    time_axis: bool = False,
    y_tickformat: str | None = None,
) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(7,17,31,0.45)",
        font={"color": TEXT, "family": "Inter, sans-serif"},
        margin={"l": 38, "r": 24, "t": 52, "b": 38},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        hovermode="x unified" if time_axis else "closest",
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    if time_axis:
        fig.update_xaxes(tickformat="%Y-%m-%d %H:%M:%S", tickangle=-25)
    if y_tickformat:
        fig.update_yaxes(tickformat=y_tickformat)
    return fig


def add_empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="section-card">
            <h3>{title}</h3>
            <p style="color:{MUTED}; margin-bottom:0;">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, caption: str = "", accent: str | None = None) -> None:
    accent_css = f"border-top: 2px solid {accent};" if accent else ""
    st.markdown(
        f"""
        <div class="metric-panel" style="{accent_css}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_kpis(risk: dict[str, str]) -> None:
    total_pnl = as_float(risk.get("total_pnl"))
    realized_pnl = as_float(risk.get("realized_pnl"))
    final_position = as_float(risk.get("final_position"))
    trades = as_float(risk.get("number_of_trades"))
    sharpe = as_float(risk.get("sharpe_ratio_annualized"))
    drawdown = as_float(risk.get("max_drawdown"))
    risk_rejects = as_float(risk.get("risk_rejects"))
    liquidity_rejects = as_float(risk.get("liquidity_rejects"))

    pnl_color = GREEN if total_pnl >= 0 else RED

    cols = st.columns(4)
    with cols[0]:
        metric_card("Total P&L", format_money(total_pnl), f"Realized: {format_money(realized_pnl)}", pnl_color)
    with cols[1]:
        metric_card("Final Position", format_int(final_position), "Absolute limit: 10", BLUE)
    with cols[2]:
        metric_card("Trades", format_int(trades), f"Risk rejects: {format_int(risk_rejects)}", BLUE_SOFT)
    with cols[3]:
        metric_card("Sharpe", format_ratio(sharpe), f"Max drawdown: {drawdown * 100:.6f}%", RED_SOFT)

    cols = st.columns(4)
    with cols[0]:
        metric_card("Final Mark", format_money(as_float(risk.get("final_mark_price"))), "Last valuation price")
    with cols[1]:
        metric_card("Cash", format_money(as_float(risk.get("cash"))), "Portfolio cash")
    with cols[2]:
        metric_card("Win Rate", f"{as_float(risk.get('win_rate')) * 100:.2f}%", "Executed strategy trades")
    with cols[3]:
        metric_card("Liquidity Rejects", format_int(liquidity_rejects), "All-or-nothing rejects")


def plot_equity_and_pnl(equity: pd.DataFrame) -> go.Figure:
    plotted = add_time_column(equity)
    initial_equity = plotted["equity"].iloc[0] if not plotted.empty else 0.0
    plotted["equity_change"] = plotted["equity"] - initial_equity

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=("Equity Change", "Total P&L"),
    )
    fig.add_trace(
        go.Scatter(
            x=plotted["datetime"],
            y=plotted["equity_change"],
            mode="lines",
            line={"color": BLUE, "width": 2.4, "shape": "hv"},
            customdata=plotted["equity"],
            hovertemplate="Date=%{x}<br>Equity change=%{y:,.2f}<br>Equity=%{customdata:,.2f}<extra></extra>",
            name="Equity change",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plotted["datetime"],
            y=plotted["pnl"],
            mode="lines",
            line={"color": RED_SOFT, "width": 2.0, "shape": "hv"},
            name="P&L",
            hovertemplate="Date=%{x}<br>P&L=%{y:,.2f}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        title="Equity Change And P&L",
    )
    fig.update_yaxes(title_text="Value", tickformat=",.2f", row=1, col=1)
    fig.update_yaxes(title_text="Value", tickformat=",.2f", row=2, col=1)
    return plot_layout(fig, height=500, time_axis=True, y_tickformat=",.2f")


def plot_position(equity: pd.DataFrame) -> go.Figure:
    plotted = add_time_column(equity)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=plotted["datetime"],
            y=plotted["position"],
            mode="lines",
            fill="tozeroy",
            line={"color": BLUE_SOFT, "width": 2.2, "shape": "hv"},
            fillcolor="rgba(79, 140, 255, 0.20)",
            hovertemplate="Date=%{x}<br>Position=%{y}<extra></extra>",
            name="Position",
        )
    )
    fig.update_layout(title="Position Over Time", yaxis_title="Position")
    return plot_layout(fig, height=330, time_axis=True, y_tickformat="d")


def plot_market_and_trades(market: pd.DataFrame, trades: pd.DataFrame) -> go.Figure:
    plotted = add_time_column(market)
    plotted_trades = add_time_column(trades) if not trades.empty else trades
    price_cols = ["best_bid", "best_ask", "last_price"]
    for column in price_cols:
        if column in plotted:
            plotted.loc[plotted[column] <= 0, column] = pd.NA

    fig = go.Figure()
    traces = [
        ("best_bid", "Best Bid", BLUE),
        ("best_ask", "Best Ask", RED_SOFT),
        ("last_price", "Last Price", TEXT),
    ]
    for column, name, color in traces:
        if column in plotted:
            fig.add_trace(
                go.Scatter(
                    x=plotted["datetime"],
                    y=plotted[column],
                    mode="lines",
                    line={"color": color, "width": 1.9, "shape": "hv"},
                    hovertemplate="Date=%{x}<br>Price=%{y:,.2f}<extra>" + name + "</extra>",
                    name=name,
                )
            )

    if not plotted_trades.empty:
        trade_colors = plotted_trades["aggressor_side"].map({"BID": BLUE, "ASK": RED}).fillna(AMBER)
        fig.add_trace(
            go.Scatter(
                x=plotted_trades["datetime"],
                y=plotted_trades["price"],
                mode="markers",
                marker={
                    "size": (plotted_trades["quantity"].clip(lower=1) * 3 + 7).clip(8, 18),
                    "color": trade_colors,
                    "line": {"color": "#ffffff", "width": 0.7},
                    "opacity": 0.9,
                },
                text=[
                    f"{side} | qty {qty} | {strategy}"
                    for side, qty, strategy in zip(
                        plotted_trades["aggressor_side"],
                        plotted_trades["quantity"],
                        plotted_trades["strategy_name"],
                    )
                ],
                hovertemplate="Date=%{x}<br>Price=%{y:,.2f}<br>%{text}<extra>Trade</extra>",
                name="Trades",
            )
        )

    fig.update_layout(title="Market Data And Strategy Trades", yaxis_title="Price")
    return plot_layout(fig, height=520, time_axis=True, y_tickformat=",.2f")


def plot_trade_distribution(trades: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not trades.empty:
        sides = trades.groupby("aggressor_side", as_index=False).agg(
            trades=("trade_id", "count"),
            quantity=("quantity", "sum"),
        )
        colors = [BLUE if side == "BID" else RED for side in sides["aggressor_side"]]
        fig.add_trace(
            go.Bar(
                x=sides["aggressor_side"],
                y=sides["trades"],
                marker_color=colors,
                text=sides["trades"],
                textposition="outside",
                name="Trades",
            )
        )
    fig.update_layout(title="Trade Count By Side", yaxis_title="Number of trades")
    return plot_layout(fig, height=320, y_tickformat="d")


def plot_trade_prices(trades: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not trades.empty:
        for side, color in [("BID", BLUE), ("ASK", RED)]:
            subset = trades[trades["aggressor_side"] == side]
            if not subset.empty:
                fig.add_trace(
                    go.Histogram(
                        x=subset["price"],
                        marker_color=color,
                        opacity=0.78,
                        name=side,
                    )
                )
    fig.update_layout(
        title="Execution Price Distribution",
        barmode="overlay",
        xaxis_title="Execution price",
        yaxis_title="Number of trades",
    )
    return plot_layout(fig, height=320, y_tickformat="d")


def plot_drawdown(equity: pd.DataFrame) -> go.Figure:
    curve = add_time_column(equity[["timestamp", "equity"]])
    curve["peak"] = curve["equity"].cummax()
    curve["drawdown"] = (curve["peak"] - curve["equity"]) / curve["peak"].replace(0, pd.NA)
    curve["drawdown_pct"] = curve["drawdown"].fillna(0) * 100

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=curve["datetime"],
            y=curve["drawdown_pct"],
            mode="lines",
            fill="tozeroy",
            line={"color": RED_SOFT, "width": 2.2, "shape": "hv"},
            fillcolor="rgba(207, 77, 92, 0.22)",
            hovertemplate="Date=%{x}<br>Drawdown=%{y:.6f}%<extra></extra>",
            name="Drawdown",
        )
    )
    fig.update_layout(title="Drawdown", yaxis_title="Drawdown (%)")
    return plot_layout(fig, height=360, time_axis=True, y_tickformat=".6f")


def plot_exposure(risk: dict[str, str]) -> go.Figure:
    values = [
        as_float(risk.get("gross_exposure")),
        as_float(risk.get("net_exposure")),
    ]
    fig = go.Figure(
        go.Bar(
            x=["Gross Exposure", "Net Exposure"],
            y=values,
            marker_color=[BLUE, RED if values[1] < 0 else GREEN],
            text=[format_money(v) for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(title="Exposure", yaxis_title="Value")
    return plot_layout(fig, height=360, y_tickformat=",.2f")


def plot_strategy_comparison(comparison: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not comparison.empty:
        fig.add_trace(
            go.Bar(
                x=comparison["strategy"],
                y=comparison["total_pnl"],
                marker_color=[GREEN if v >= 0 else RED for v in comparison["total_pnl"]],
                text=[format_money(v) for v in comparison["total_pnl"]],
                textposition="outside",
                name="Total P&L",
            )
        )
    fig.update_layout(title="Reference Strategy Comparison", yaxis_title="Total P&L")
    return plot_layout(fig, height=360, y_tickformat=",.2f")


def plot_strategy_sharpe(comparison: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not comparison.empty:
        fig.add_trace(
            go.Bar(
                x=comparison["strategy"],
                y=comparison["sharpe_ratio_annualized"],
                marker_color=BLUE_SOFT,
                text=[format_ratio(v) for v in comparison["sharpe_ratio_annualized"]],
                textposition="outside",
                name="Sharpe",
            )
        )
    fig.update_layout(title="Reference Annualized Sharpe", yaxis_title="Sharpe")
    return plot_layout(fig, height=360, y_tickformat=".2f")


def csv_download(label: str, df: pd.DataFrame, file_name: str) -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        use_container_width=True,
    )


def show_overview(outputs: dict[str, pd.DataFrame], risk: dict[str, str]) -> None:
    if not risk:
        add_empty_state("No Simulation Output", "Run the C++ engine from the sidebar to generate dashboard data.")
        return

    show_kpis(risk)

    equity = outputs["equity"]
    comparison = outputs["comparison"]

    if not equity.empty:
        st.plotly_chart(
            plot_equity_and_pnl(equity),
            use_container_width=True,
            key="overview_equity_pnl",
        )
        left, right = st.columns([1, 1])
        with left:
            st.plotly_chart(
                plot_position(equity),
                use_container_width=True,
                key="overview_position",
            )
        with right:
            st.plotly_chart(
                plot_drawdown(equity),
                use_container_width=True,
                key="overview_drawdown",
            )

    if not comparison.empty:
        st.subheader("Reference Results")
        left, right = st.columns([1, 1])
        with left:
            st.plotly_chart(
                plot_strategy_comparison(comparison),
                use_container_width=True,
                key="overview_strategy_comparison",
            )
        with right:
            st.plotly_chart(
                plot_strategy_sharpe(comparison),
                use_container_width=True,
                key="overview_strategy_sharpe",
            )


def show_market(outputs: dict[str, pd.DataFrame]) -> None:
    market = outputs["market"]
    trades = outputs["trades"]

    if market.empty:
        add_empty_state("No Market Data", "Run a simulation to generate market snapshots and strategy trades.")
        return

    st.plotly_chart(
        plot_market_and_trades(market, trades),
        use_container_width=True,
        key="market_and_trades",
    )

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(
            plot_trade_distribution(trades),
            use_container_width=True,
            key="trade_distribution",
        )
    with right:
        st.plotly_chart(
            plot_trade_prices(trades),
            use_container_width=True,
            key="trade_prices",
        )

    if not trades.empty:
        st.subheader("Latest Trades")
        displayed_trades = add_time_column(trades)
        display_columns = [
            "trade_id",
            "datetime",
            "aggressor_side",
            "price",
            "quantity",
            "strategy_name",
            "position_after",
            "cash_after",
            "equity_after",
        ]
        st.dataframe(
            displayed_trades[display_columns].tail(20).sort_values("trade_id", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


def show_risk(outputs: dict[str, pd.DataFrame], risk: dict[str, str]) -> None:
    if not risk:
        add_empty_state("No Risk Report", "Run a simulation to generate the final risk report.")
        return

    left, right = st.columns([1, 1])
    with left:
        st.plotly_chart(
            plot_exposure(risk),
            use_container_width=True,
            key="risk_exposure",
        )
    with right:
        if not outputs["equity"].empty:
            st.plotly_chart(
                plot_drawdown(outputs["equity"]),
                use_container_width=True,
                key="risk_drawdown",
            )

    summary = pd.DataFrame(
        [
            ("Final mark price", format_money(as_float(risk.get("final_mark_price")))),
            ("Final position", format_int(as_float(risk.get("final_position")))),
            ("Cash", format_money(as_float(risk.get("cash")))),
            ("Realized P&L", format_money(as_float(risk.get("realized_pnl")))),
            ("Total P&L", format_money(as_float(risk.get("total_pnl")))),
            ("Gross exposure", format_money(as_float(risk.get("gross_exposure")))),
            ("Net exposure", format_money(as_float(risk.get("net_exposure")))),
            ("Number of trades", format_int(as_float(risk.get("number_of_trades")))),
            ("Annualized Sharpe", format_ratio(as_float(risk.get("sharpe_ratio_annualized")))),
            ("Annualized volatility", f"{as_float(risk.get('annualized_volatility')):.8f}"),
            ("Max drawdown", f"{as_float(risk.get('max_drawdown')):.8f}"),
            ("Win rate", f"{as_float(risk.get('win_rate')) * 100:.2f}%"),
            ("Average win", format_money(as_float(risk.get("average_win")))),
            ("Average loss", format_money(as_float(risk.get("average_loss")))),
            ("Risk rejects", format_int(as_float(risk.get("risk_rejects")))),
            ("Liquidity rejects", format_int(as_float(risk.get("liquidity_rejects")))),
        ],
        columns=["Metric", "Value"],
    )

    st.subheader("Risk Report")
    st.dataframe(summary, use_container_width=True, hide_index=True)


def show_data(outputs: dict[str, pd.DataFrame]) -> None:
    tabs = st.tabs(["Market Data", "Trades", "Equity Curve", "Risk Report", "Reference Comparison"])
    data_map = [
        ("market_data.csv", outputs["market"]),
        ("trades.csv", outputs["trades"]),
        ("equity_curve.csv", outputs["equity"]),
        ("risk_report.csv", outputs["risk"]),
        ("strategy_comparison.csv", outputs["comparison"]),
    ]

    for tab, (file_name, df) in zip(tabs, data_map):
        with tab:
            if df.empty:
                add_empty_state("No Data", f"`{file_name}` is not available yet.")
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
                csv_download(f"Download {file_name}", df, file_name)


def sidebar(datasets: Iterable[Path]) -> tuple[Path | None, str, bool, bool, bool]:
    st.sidebar.title("Run Control")

    dataset_list = list(datasets)
    dataset_names = [path.name for path in dataset_list]
    default_index = dataset_names.index("test_events.csv") if "test_events.csv" in dataset_names else 0
    selected_dataset_name = st.sidebar.selectbox(
        "Market scenario",
        dataset_names,
        index=default_index if dataset_names else None,
        format_func=lambda name: f"{name} - {DATASET_DESCRIPTIONS.get(name, 'CSV market event file')}",
    )
    selected_dataset = None
    if selected_dataset_name:
        selected_dataset = next(path for path in dataset_list if path.name == selected_dataset_name)
        st.sidebar.caption(DATASET_DESCRIPTIONS.get(selected_dataset_name, "CSV market event file"))

    strategy = st.sidebar.selectbox(
        "Strategy",
        list(STRATEGIES.keys()),
        format_func=lambda key: f"{key} - {STRATEGIES[key]}",
    )

    build_first = st.sidebar.checkbox("Build before run", value=not BINARY_PATH.exists())

    run_clicked = st.sidebar.button("Run Simulation", use_container_width=True)
    build_clicked = st.sidebar.button("Rebuild C++ Engine", use_container_width=True)

    if selected_dataset:
        st.sidebar.divider()
        st.sidebar.caption("Market event preview")
        preview = read_csv(selected_dataset).head(5)
        st.sidebar.dataframe(preview, hide_index=True, use_container_width=True)

    return selected_dataset, strategy, build_first, run_clicked, build_clicked


def main() -> None:
    apply_theme()

    datasets = available_datasets()
    selected_dataset, strategy, build_first, run_clicked, build_clicked = sidebar(datasets)

    hero(selected_dataset.name if selected_dataset else "none", strategy)

    if "last_log" not in st.session_state:
        st.session_state.last_log = ""
    if "last_status" not in st.session_state:
        st.session_state.last_status = None

    if build_clicked:
        with st.spinner("Building C++ engine..."):
            ok, log = configure_and_build()
        st.session_state.last_log = log
        st.session_state.last_status = "Build succeeded." if ok else "Build failed."
        if ok:
            st.success(st.session_state.last_status)
        else:
            st.error(st.session_state.last_status)

    if run_clicked:
        if selected_dataset is None:
            st.error("No dataset found in the data directory.")
        else:
            with st.spinner("Running C++ simulation..."):
                ok, log = run_simulation(selected_dataset, strategy, build_first)
            st.cache_data.clear()
            st.session_state.last_log = log
            st.session_state.last_status = "Simulation completed." if ok else "Simulation failed."
            if ok:
                st.success(st.session_state.last_status)
            else:
                st.error(st.session_state.last_status)

    outputs = read_outputs()
    risk = risk_dict(outputs["risk"])

    page = st.tabs(["Overview", "Market & Trades", "Risk", "Data Explorer"])
    with page[0]:
        show_overview(outputs, risk)
    with page[1]:
        show_market(outputs)
    with page[2]:
        show_risk(outputs, risk)
    with page[3]:
        show_data(outputs)

    if st.session_state.last_log:
        with st.expander("Last C++ Command Log", expanded=False):
            st.code(st.session_state.last_log, language="text")


if __name__ == "__main__":
    main()
