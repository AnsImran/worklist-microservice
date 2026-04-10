"""Worklist Frontend — Home Page."""

import streamlit as st

from utils import api_client

st.set_page_config(
    page_title="Worklist Frontend",
    page_icon=":hospital:",
    layout="wide",
)

st.title("Radiology Worklist")
st.markdown("Live simulation of a hospital PACS radiology worklist.")

# Health check
health = api_client.health_check()
if "error" in health:
    st.error(f"API is unreachable: {health['error']}")
    st.stop()

# Stats summary
stats = api_client.get_stats()
if "error" in stats:
    st.warning(f"Could not load stats: {stats['error']}")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Studies", stats.get("active_studies", 0))
    col2.metric("Archived Studies", stats.get("archived_studies", 0))
    col3.metric("Audit Entries", stats.get("audit_entries", 0))
    col4.metric("Uptime", f"{stats.get('uptime_seconds', 0) // 60} min")

    st.divider()

    # Active studies breakdown
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Active by Status")
        by_status = stats.get("active_by_status", {})
        if by_status:
            for status, count in by_status.items():
                st.write(f"**{status}**: {count}")
        else:
            st.write("No active studies yet.")

    with c2:
        st.subheader("Active by Modality")
        by_modality = stats.get("active_by_modality", {})
        if by_modality:
            for modality, count in by_modality.items():
                st.write(f"**{modality}**: {count}")
        else:
            st.write("No active studies yet.")

st.divider()
st.caption("Use the sidebar to navigate to Worklist, Statistics, Audit Log, History, or Demand Injection.")
