"""History — archived (completed/cancelled) studies."""

import pandas as pd
import streamlit as st

from utils import api_client

st.set_page_config(page_title="History", page_icon=":books:", layout="wide")

st.title("Study History")

# Filters
with st.sidebar:
    st.header("Filters")
    modality_filter = st.selectbox(
        "Modality", ["All", "CT", "CR", "DX", "MR", "US", "NM"]
    )
    status_filter = st.selectbox("Final Status", ["All", "Approved", "Cancelled"])
    patient_filter = st.text_input("Patient Name (partial match)")

col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Date From", value=None)
with col2:
    date_to = st.date_input("Date To", value=None)

if st.button("Refresh", type="primary"):
    st.rerun()

# Fetch data
data = api_client.get_history(
    modality=modality_filter if modality_filter != "All" else None,
    status=status_filter if status_filter != "All" else None,
    patient_name=patient_filter or None,
    date_from=date_from.isoformat() + "T00:00:00Z" if date_from else None,
    date_to=date_to.isoformat() + "T23:59:59Z" if date_to else None,
    limit=500,
)

if "error" in data:
    st.error(f"API error: {data['error']}")
    st.stop()

studies = data.get("studies", [])
total = data.get("total", 0)

st.caption(f"Showing {len(studies)} of {total} archived studies")

if not studies:
    st.info("No archived studies match the current filters.")
    st.stop()

df = pd.DataFrame(studies)

display_cols = [
    "accession_number", "patient_name", "mrn", "modality",
    "study_description", "priority", "status", "rvu",
    "study_introduced_at", "assigned_radiologist",
]
available = [c for c in display_cols if c in df.columns]
df = df[available]

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

st.dataframe(df, use_container_width=True, height=600)
