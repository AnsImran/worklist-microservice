"""Statistics — charts and counts for the worklist."""

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils import api_client

st.set_page_config(page_title="Statistics", page_icon=":bar_chart:", layout="wide")

# Auto-refresh every 30 seconds
st_autorefresh(interval=30000, key="stats_refresh")

st.title("Worklist Statistics")

stats = api_client.get_stats()
if "error" in stats:
    st.error(f"API error: {stats['error']}")
    st.stop()

# Metric cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Studies", stats.get("active_studies", 0))
col2.metric("Archived Studies", stats.get("archived_studies", 0))
col3.metric("Audit Entries", stats.get("audit_entries", 0))
col4.metric("Uptime", f"{stats.get('uptime_seconds', 0) // 60} min")

st.divider()

# Charts
c1, c2 = st.columns(2)

with c1:
    st.subheader("Active Studies by Status")
    by_status = stats.get("active_by_status", {})
    if by_status:
        df_status = pd.DataFrame(
            list(by_status.items()), columns=["Status", "Count"]
        )
        status_order = ["Introduced", "Assigned", "Dictating", "Pending Approval"]
        df_status["Status"] = pd.Categorical(df_status["Status"], categories=status_order, ordered=True)
        df_status = df_status.sort_values("Status")
        fig = px.bar(
            df_status, x="Status", y="Count",
            color="Status",
            color_discrete_map={
                "Introduced": "#2196F3",
                "Assigned": "#FF9800",
                "Dictating": "#FFC107",
                "Pending Approval": "#9C27B0",
            },
        )
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active studies.")

with c2:
    st.subheader("Active Studies by Modality")
    by_modality = stats.get("active_by_modality", {})
    if by_modality:
        df_mod = pd.DataFrame(
            list(by_modality.items()), columns=["Modality", "Count"]
        )
        fig = px.pie(df_mod, names="Modality", values="Count", hole=0.4)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active studies.")

st.divider()

# Archived breakdown
st.subheader("Archived Studies by Final Status")
archived_status = stats.get("archived_by_status", {})
if archived_status:
    df_arch = pd.DataFrame(
        list(archived_status.items()), columns=["Status", "Count"]
    )
    fig = px.bar(
        df_arch, x="Status", y="Count",
        color="Status",
        color_discrete_map={"Approved": "#4CAF50", "Cancelled": "#F44336"},
    )
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No archived studies yet.")

# Priority distribution from live worklist
st.divider()
st.subheader("Priority Distribution (Active Studies)")
worklist = api_client.get_worklist(limit=1000)
studies = worklist.get("studies", [])
if studies:
    priorities = [s["priority"] for s in studies]
    df_pri = pd.DataFrame(priorities, columns=["Priority"])
    df_pri["Level"] = df_pri["Priority"].apply(
        lambda p: "STAT (10)" if p == 10 else "High (7-9)" if p >= 7 else "Medium (4-6)" if p >= 4 else "Low (1-3)"
    )
    counts = df_pri["Level"].value_counts().reset_index()
    counts.columns = ["Level", "Count"]
    level_order = ["Low (1-3)", "Medium (4-6)", "High (7-9)", "STAT (10)"]
    counts["Level"] = pd.Categorical(counts["Level"], categories=level_order, ordered=True)
    counts = counts.sort_values("Level")
    fig = px.bar(
        counts, x="Level", y="Count",
        color="Level",
        color_discrete_map={
            "Low (1-3)": "#4CAF50",
            "Medium (4-6)": "#FF9800",
            "High (7-9)": "#F44336",
            "STAT (10)": "#9C27B0",
        },
    )
    fig.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No active studies.")
