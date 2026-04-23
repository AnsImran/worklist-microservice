"""Live Worklist — auto-refreshes every 5 seconds."""

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils import api_client
from utils.style import STATUS_COLORS

st.set_page_config(page_title="Worklist", page_icon=":hospital:", layout="wide")

# Auto-refresh every 5 seconds
st_autorefresh(interval=5000, key="worklist_refresh")

st.title("Live Worklist")

# Filters in sidebar
with st.sidebar:
    st.header("Filters")
    modality_filter = st.selectbox(
        "Modality", ["All", "CT", "CR", "DX", "MR", "US", "NM"]
    )
    status_filter = st.selectbox(
        "Status",
        ["All", "Introduced", "Assigned", "Dictating", "Pending Approval"],
    )
    priority_range = st.slider("Priority Range", 1, 10, (1, 10))

# Fetch data
data = api_client.get_worklist(
    modality=modality_filter if modality_filter != "All" else None,
    status=status_filter if status_filter != "All" else None,
    priority_min=priority_range[0],
    priority_max=priority_range[1],
    limit=500,
)

if "error" in data:
    st.error(f"API error: {data['error']}")
    st.stop()

studies = data.get("studies", [])
total = data.get("total", 0)

st.caption(f"Showing {len(studies)} of {total} active studies (refreshes every 5s)")

if not studies:
    st.info("No active studies match the current filters.")
    st.stop()

# Build dataframe
df = pd.DataFrame(studies)

# Select and order columns
display_cols = [
    "accession_number", "patient_name", "mrn", "modality",
    "study_description", "priority", "status", "rvu",
    "study_introduced_at", "assigned_radiologist",
]
available = [c for c in display_cols if c in df.columns]
df = df[available]

# Rename for display
df = df.rename(columns={
    "accession_number": "Accession #",
    "patient_name": "Patient",
    "mrn": "MRN",
    "modality": "Modality",
    "study_description": "Description",
    "priority": "Priority",
    "status": "Status",
    "rvu": "RVU",
    "study_introduced_at": "Introduced At",
    "assigned_radiologist": "Radiologist",
})

# Sort by priority descending
df = df.sort_values("Priority", ascending=False).reset_index(drop=True)

# Color-code status
def highlight_status(row):
    color = STATUS_COLORS.get(row["Status"], "#9E9E9E")
    return [f"background-color: {color}20" for _ in row]


styled = df.style.apply(highlight_status, axis=1)

st.dataframe(
    styled,
    use_container_width=True,
    height=600,
)
