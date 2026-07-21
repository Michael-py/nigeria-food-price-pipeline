"""Streamlit dashboard for Nigeria Food Price Intelligence."""

import streamlit as st

st.set_page_config(
    page_title="Nigeria Food Price Intelligence",
    page_icon="🇳🇬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🇳🇬 Nigeria Food Price Intelligence")
st.markdown(
    """
    Real-time food price monitoring and forecasting across Nigerian commodity markets.

    **Select a page from the sidebar to explore:**
    - 📈 **Price Trends** — Historical price movements by commodity and market
    - 🔮 **Forecasts** — 7-day and 30-day price predictions
    - 🗺️ **Market Comparison** — Compare prices across Nigerian markets
    - ✅ **Data Quality** — Pipeline health and data freshness indicators
    """
)

st.sidebar.title("Navigation")
st.sidebar.info(
    "This dashboard is part of the Nigeria Food Price Intelligence Pipeline. "
    "Data is updated automatically via Apache Airflow."
)

# TODO: Implement dashboard pages in Week 9
st.warning("Dashboard under construction. See tasks.md Week 9 for implementation plan.")
