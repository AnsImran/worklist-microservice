"""Audit Log — searchable event trail."""

import pandas as pd
import streamlit as st

from utils import api_client

st.set_page_config(page_title="Audit Log", page_icon=":clipboard:", layout="wide")

st.title("Audit Log")

# Filters
with st.sidebar:
    st.header("Filters")
    screen_filter = st.selectbox(
        "Event Type",
        ["All", "New Study", "Studies", "Assignment", "Demand"],
    )
    accession_filter = st.text_input("Accession Number")
    user_filter = st.text_input("User")

col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Date From", value=None)
with col2:
    date_to = st.date_input("Date To", value=None)

if st.button("Refresh", type="primary"):
    st.rerun()

# Fetch data
data = api_client.get_audit_log(
    screen=screen_filter if screen_filter != "All" else None,
    accession_number=accession_filter or None,
    user=user_filter or None,
    date_from=date_from.isoformat() + "T00:00:00Z" if date_from else None,
    date_to=date_to.isoformat() + "T23:59:59Z" if date_to else None,
    limit=500,
)

if "error" in data:
    st.error(f"API error: {data['error']}")
    st.stop()

entries = data.get("entries", [])
total = data.get("total", 0)

st.caption(f"Showing {len(entries)} of {total} entries")

if not entries:
    st.info("No audit entries match the current filters.")
    st.stop()

df = pd.DataFrame(entries)

display_cols = ["logged_date", "screen", "user", "patient_name", "accession_number", "log_description"]
available = [c for c in display_cols if c in df.columns]
df = df[available]

df = df.rename(columns={
    "logged_date": "Logged Date",
    "screen": "Event Type",
    "user": "User",
    "patient_name": "Patient",
    "accession_number": "Accession #",
    "log_description": "Description",
})

st.dataframe(df, use_container_width=True, height=600)
