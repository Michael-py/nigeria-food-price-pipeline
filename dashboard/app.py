"""Streamlit dashboard for Nigeria Food Price Intelligence.

Run with: streamlit run dashboard/app.py --server.headless true
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="Nigeria Food Price Intelligence",
    page_icon="🇳🇬",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_engine():
    import os

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "food_prices")
    user = os.getenv("POSTGRES_USER", "michael_dairo")
    password = os.getenv("POSTGRES_PASSWORD", "f19PT5F9BpSecure2026")
    if host == "postgres":
        host = "localhost"
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")


@st.cache_data(ttl=300)
def load_daily_prices():
    engine = get_engine()
    df = pd.read_sql(
        "SELECT price_date, market_name, commodity_name, category, unit_name, price_ngn "
        "FROM public_marts.fct_daily_prices ORDER BY price_date",
        engine,
    )
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df


@st.cache_data(ttl=300)
def load_markets_dim():
    engine = get_engine()
    return pd.read_sql("SELECT * FROM public_marts.dim_markets", engine)


# --- Sidebar ---
st.sidebar.title("🇳🇬 Nigeria Food Price Intelligence")
st.sidebar.markdown("_Real-time monitoring & ML forecasting_")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "📈 Price Trends",
        "🗺️ Market Comparison",
        "📊 State Averages",
        "🔮 Forecasts",
        "✅ Data Quality",
    ],
)

# Load shared data
daily = load_daily_prices()
markets_dim = load_markets_dim()

# Enrich daily with state info
daily_enriched = daily.merge(
    markets_dim[["market_name", "state", "geopolitical_zone"]],
    on="market_name",
    how="left",
)

# All commodities and markets (with harmonized names)
all_commodities = sorted(daily["commodity_name"].unique())
all_markets = sorted(daily["market_name"].unique())

# --- PAGES ---

if page == "📈 Price Trends":
    st.title("📈 Price Trends")
    st.markdown(
        "Track how food prices have changed over time. "
        "Select a commodity and markets to compare price movements."
    )

    col1, col2 = st.columns(2)
    with col1:
        selected_commodity = st.selectbox("Commodity", all_commodities)
    with col2:
        # Show markets with state for context
        market_state_map = dict(zip(markets_dim["market_name"], markets_dim["state"]))
        market_labels = [
            f"{m} ({market_state_map.get(m, 'Unknown')})" if market_state_map.get(m) else m
            for m in all_markets
        ]
        selected_idxs = st.multiselect(
            "Markets (with State)",
            range(len(all_markets)),
            default=list(range(min(3, len(all_markets)))),
            format_func=lambda i: market_labels[i],
            max_selections=10,
        )
        selected_markets = [all_markets[i] for i in selected_idxs]

    # Get unit for display
    unit_row = daily[daily["commodity_name"] == selected_commodity]["unit_name"].mode()
    unit = unit_row.iloc[0] if not unit_row.empty else "KG"

    # Filter
    mask = (daily["commodity_name"] == selected_commodity) & (
        daily["market_name"].isin(selected_markets)
    )
    filtered = daily[mask]

    if filtered.empty:
        st.warning("No data for this selection.")
    else:
        # Enrich with state
        filtered_display = filtered.merge(
            markets_dim[["market_name", "state"]], on="market_name", how="left"
        )
        filtered_display["label"] = filtered_display.apply(
            lambda r: (
                f"{r['market_name']} ({r['state']})"
                if pd.notna(r.get("state"))
                else r["market_name"]
            ),
            axis=1,
        )

        fig = px.line(
            filtered_display,
            x="price_date",
            y="price_ngn",
            color="label",
            title=f"{selected_commodity} — Price Over Time (NGN per {unit})",
            labels={
                "price_ngn": f"Price (₦/{unit})",
                "price_date": "Date",
                "label": "Market (State)",
            },
        )
        fig.update_layout(height=500, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)


elif page == "🗺️ Market Comparison":
    st.title("🗺️ Market Comparison")
    st.markdown(
        "Compare the latest food prices across markets. "
        "Bars show the most recent price per market, coloured by geopolitical zone."
    )

    selected_commodity = st.selectbox("Commodity", all_commodities)
    unit_row = daily[daily["commodity_name"] == selected_commodity]["unit_name"].mode()
    unit = unit_row.iloc[0] if not unit_row.empty else "KG"

    commodity_data = daily[daily["commodity_name"] == selected_commodity]
    latest_date = commodity_data["price_date"].max()
    latest = commodity_data[commodity_data["price_date"] == latest_date].copy()

    # Enrich with state
    latest = latest.merge(
        markets_dim[["market_name", "state", "geopolitical_zone"]], on="market_name", how="left"
    )
    latest["display"] = latest.apply(
        lambda r: (
            f"{r['market_name']} ({r['state']})" if pd.notna(r.get("state")) else r["market_name"]
        ),
        axis=1,
    )

    if latest.empty:
        st.warning("No recent data.")
    else:
        fig = px.bar(
            latest.sort_values("price_ngn", ascending=True),
            x="price_ngn",
            y="display",
            orientation="h",
            color="geopolitical_zone",
            title=f"{selected_commodity} — Price per {unit} by Market ({latest_date.date()})",
            labels={
                "price_ngn": f"Price (₦/{unit})",
                "display": "Market (State)",
                "geopolitical_zone": "Zone",
            },
        )
        fig.update_layout(height=max(400, len(latest) * 25))
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Markets", len(latest))
        col2.metric("Average", f"₦{latest['price_ngn'].mean():,.0f}/{unit}")
        col3.metric(
            "Range", f"₦{latest['price_ngn'].min():,.0f} — ₦{latest['price_ngn'].max():,.0f}"
        )


elif page == "📊 State Averages":
    st.title("📊 Average Prices by State")
    st.markdown(
        "See how commodity prices compare across Nigerian states. "
        "This averages all market prices within each state."
    )

    selected_commodity = st.selectbox("Commodity", all_commodities)
    unit_row = daily[daily["commodity_name"] == selected_commodity]["unit_name"].mode()
    unit = unit_row.iloc[0] if not unit_row.empty else "KG"

    # Filter and enrich
    commodity_data = daily_enriched[daily_enriched["commodity_name"] == selected_commodity].copy()

    if commodity_data.empty or commodity_data["state"].isna().all():
        st.warning(
            "No state-level data available for this commodity. State mapping only covers markets in our seed data."
        )
    else:
        # State averages (latest 3 months)
        recent_cutoff = commodity_data["price_date"].max() - pd.DateOffset(months=3)
        recent = commodity_data[commodity_data["price_date"] >= recent_cutoff]

        state_avg = (
            recent.dropna(subset=["state"])
            .groupby(["state", "geopolitical_zone"])["price_ngn"]
            .agg(["mean", "count"])
            .reset_index()
            .rename(columns={"mean": "avg_price", "count": "observations"})
            .sort_values("avg_price", ascending=True)
        )

        if state_avg.empty:
            st.warning("Not enough data with state mapping for this commodity.")
        else:
            fig = px.bar(
                state_avg,
                x="avg_price",
                y="state",
                orientation="h",
                color="geopolitical_zone",
                title=f"{selected_commodity} — Average Price per {unit} by State (Last 3 months)",
                labels={
                    "avg_price": f"Avg Price (₦/{unit})",
                    "state": "State",
                    "geopolitical_zone": "Zone",
                },
            )
            fig.update_layout(height=max(400, len(state_avg) * 30))
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(
                f"_Prices averaged from {recent['price_date'].min().date()} to "
                f"{recent['price_date'].max().date()} across all markets in each state._"
            )

            # Table view
            st.subheader("Data Table")
            display_df = state_avg.copy()
            display_df["avg_price"] = display_df["avg_price"].apply(lambda x: f"₦{x:,.0f}")
            st.dataframe(
                display_df.rename(
                    columns={
                        "state": "State",
                        "geopolitical_zone": "Zone",
                        "avg_price": f"Avg Price (/{unit})",
                        "observations": "Data Points",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )


elif page == "🔮 Forecasts":
    st.title("🔮 Price Forecasts")
    st.markdown(
        "View predicted future prices based on historical patterns. "
        "The model uses past prices, seasonal trends, and momentum to forecast ahead."
    )

    features_path = Path("data/features/ml_features.csv")
    results_30d_path = Path("data/features/model_v2_30d_results.csv")

    if features_path.exists():
        features = pd.read_csv(features_path, parse_dates=["price_date"])

        forecast_commodities = sorted(features["commodity_name"].unique())
        selected = st.selectbox("Commodity", forecast_commodities)

        commodity_features = features[features["commodity_name"] == selected].copy()
        market_counts = commodity_features["market_name"].value_counts()

        if not market_counts.empty:
            best_market = market_counts.index[0]
            market_data = commodity_features[
                commodity_features["market_name"] == best_market
            ].copy()
            recent = market_data.tail(180)

            if not recent.empty:
                state_info = markets_dim[markets_dim["market_name"] == best_market]["state"].values
                state_label = (
                    f", {state_info[0]}" if len(state_info) > 0 and pd.notna(state_info[0]) else ""
                )
                st.markdown(
                    f"**Showing:** {best_market}{state_label} (market with most data for this commodity)"
                )

                fig = go.Figure()

                # Actual
                fig.add_trace(
                    go.Scatter(
                        x=recent["price_date"],
                        y=recent["price_ngn"],
                        mode="lines",
                        name="Actual Price",
                        line=dict(color="steelblue", width=2),
                    )
                )

                # 30-day trend
                if "roll_mean_30d" in recent.columns:
                    valid = recent.dropna(subset=["roll_mean_30d"])
                    fig.add_trace(
                        go.Scatter(
                            x=valid["price_date"],
                            y=valid["roll_mean_30d"],
                            mode="lines",
                            name="30-Day Trend",
                            line=dict(color="orange", width=2, dash="dash"),
                        )
                    )

                # Future projection (simple: extend the 30d trend)
                if "roll_mean_30d" in recent.columns and "mom_pct_change_30d" in recent.columns:
                    last_price = recent["price_ngn"].iloc[-1]
                    last_momentum = recent["mom_pct_change_30d"].iloc[-1]
                    if pd.notna(last_momentum):
                        future_dates = pd.date_range(
                            recent["price_date"].iloc[-1] + pd.Timedelta(days=1),
                            periods=30,
                            freq="D",
                        )
                        daily_change = last_momentum / 30
                        future_prices = [last_price * (1 + daily_change * i) for i in range(1, 31)]

                        fig.add_trace(
                            go.Scatter(
                                x=future_dates,
                                y=future_prices,
                                mode="lines",
                                name="30-Day Projection",
                                line=dict(color="green", width=2, dash="dot"),
                            )
                        )

                        # Confidence band
                        std = (
                            recent["roll_std_30d"].iloc[-1]
                            if "roll_std_30d" in recent.columns
                            else last_price * 0.1
                        )
                        if pd.isna(std):
                            std = last_price * 0.1
                        upper = [p + 1.96 * std for p in future_prices]
                        lower = [max(0, p - 1.96 * std) for p in future_prices]

                        fig.add_trace(
                            go.Scatter(
                                x=list(future_dates) + list(future_dates)[::-1],
                                y=upper + lower[::-1],
                                fill="toself",
                                fillcolor="rgba(0,200,0,0.1)",
                                line=dict(color="rgba(0,0,0,0)"),
                                name="95% Confidence",
                                showlegend=True,
                            )
                        )

                fig.update_layout(
                    title=f"{selected} — Price History & 30-Day Forecast",
                    xaxis_title="Date",
                    yaxis_title="Price (₦/KG)",
                    height=500,
                    hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown(
                    "**How to read this chart:**\n"
                    "- **Blue line** = actual recorded price\n"
                    "- **Orange dashed** = 30-day moving average (smoothed trend)\n"
                    "- **Green dotted** = projected price for the next 30 days (based on recent momentum)\n"
                    "- **Green shaded area** = 95% confidence range (price is likely to fall within this band)\n\n"
                    "If the projection goes up, the model expects prices to continue rising. "
                    "A wider confidence band means more uncertainty."
                )

                # Key metrics
                if len(recent) > 30:
                    current = recent["price_ngn"].iloc[-1]
                    prev_30 = recent["price_ngn"].iloc[-30]
                    change = ((current - prev_30) / prev_30) * 100

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Current Price", f"₦{current:,.0f}")
                    col2.metric("30-Day Change", f"{change:+.1f}%")
                    col3.metric(
                        "Trend", "Rising" if change > 2 else "Falling" if change < -2 else "Stable"
                    )
                    if pd.notna(last_momentum):
                        projected_30d = last_price * (1 + last_momentum)
                        col4.metric("30-Day Forecast", f"₦{projected_30d:,.0f}")

        # Technical comparison
        st.markdown("---")
        st.subheader("Model Accuracy (30-day horizon)")
        st.markdown(
            "How accurate is the model? We compare our ML predictions against a simple approach "
            "(just assuming the price stays the same). **Positive improvement** = ML is better."
        )

        if results_30d_path.exists():
            df_30d = pd.read_csv(results_30d_path)
            df_30d["Winner"] = df_30d["mape_improvement_pct"].apply(
                lambda x: "ML Model" if x > 0 else "Simple baseline"
            )
            st.dataframe(
                df_30d[["commodity", "naive_mape", "xgb_mape", "mape_improvement_pct", "Winner"]]
                .rename(
                    columns={
                        "commodity": "Commodity",
                        "naive_mape": "Simple Method Error (%)",
                        "xgb_mape": "ML Model Error (%)",
                        "mape_improvement_pct": "ML Improvement (%)",
                    }
                )
                .sort_values("ML Improvement (%)", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info("Run model training first: `python -m ml.training.train_v2`")


elif page == "✅ Data Quality":
    st.title("✅ Data Quality")
    st.markdown("Pipeline health: data volumes, freshness, and quality checks.")

    engine = get_engine()

    counts = pd.read_sql(
        text("""
        SELECT 'WFP' as source, count(*) as rows FROM raw.wfp_prices
        UNION ALL SELECT 'World Bank', count(*) FROM raw.worldbank_prices
        UNION ALL SELECT 'NBS', count(*) FROM raw.nbs_prices
        UNION ALL SELECT 'CBN (FX)', count(*) FROM raw.cbn_rates
        UNION ALL SELECT 'Weather', count(*) FROM raw.weather
    """),
        engine,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Raw Data", f"{counts['rows'].sum():,} rows")
    col2.metric("Data Sources", "5")
    col3.metric("Commodities (harmonized)", daily["commodity_name"].nunique())

    fig = px.bar(counts, x="source", y="rows", color="source", title="Rows per Source")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Data Freshness")
    freshness = pd.read_sql(
        text("""
        SELECT 'WFP' as source, max(price_date)::text as latest FROM raw.wfp_prices
        UNION ALL SELECT 'World Bank', max(price_date)::text FROM raw.worldbank_prices
        UNION ALL SELECT 'NBS', max(report_month)::text FROM raw.nbs_prices
    """),
        engine,
    )
    st.dataframe(
        freshness.rename(columns={"source": "Source", "latest": "Latest Data"}), hide_index=True
    )
