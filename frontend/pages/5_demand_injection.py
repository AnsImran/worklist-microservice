"""Demand Injection — submit custom studies into the worklist."""

import streamlit as st

from utils import api_client

st.set_page_config(page_title="Demand Injection", page_icon=":syringe:", layout="wide")

st.title("Demand Injection")
st.markdown(
    "Submit a custom study into the worklist with specific characteristics and timing. "
    "The system will pick it up within 30-60 seconds."
)

st.divider()

# Study characteristics
st.subheader("Study Characteristics")
st.caption("All fields are optional. Anything left blank will be randomly generated.")

col1, col2 = st.columns(2)
with col1:
    patient_name = st.text_input("Patient Name", placeholder="e.g., Smith, John A")
    modality = st.selectbox("Modality", ["(Random)", "CT", "CR", "DX", "MR", "US", "NM"])
with col2:
    study_description = st.text_input("Study Description", placeholder="e.g., CT BRAIN STROKE W/O CONTRAST")
    priority = st.slider("Priority (1 = lowest, 10 = highest)", 1, 10, 5)

# Lifecycle overrides
st.divider()
st.subheader("Lifecycle Timing (optional)")
st.caption(
    "Control exactly how fast this study moves through each stage. "
    "Values are in **real seconds**. Leave at 0 to use default random timing."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    intro_to_assigned = st.number_input(
        "Introduced to Assigned (sec)", min_value=0, value=0, step=10,
        help="How many seconds after appearing before it gets assigned. 0 = random default."
    )
with col2:
    assigned_to_dictating = st.number_input(
        "Assigned to Dictating (sec)", min_value=0, value=0, step=10,
        help="How many seconds after assignment before dictating starts. 0 = random default."
    )
with col3:
    dictating_to_pending = st.number_input(
        "Dictating to Pending Approval (sec)", min_value=0, value=0, step=10,
        help="How many seconds of dictating time. 0 = random default."
    )
with col4:
    pending_to_approved = st.number_input(
        "Pending Approval to Approved (sec)", min_value=0, value=0, step=10,
        help="How many seconds in approval queue. 0 = random default."
    )

# Cancellation
st.divider()
cancel_at = st.selectbox(
    "Cancel at Stage (optional)",
    ["(Don't cancel)", "Introduced", "Assigned", "Dictating", "Pending Approval"],
    help="If set, the study will be cancelled at this stage instead of being approved.",
)

# Submit
st.divider()
if st.button("Submit Demand", type="primary", use_container_width=True):
    payload: dict = {}

    # Build study object
    study: dict = {}
    if patient_name:
        study["patient_name"] = patient_name
    if modality != "(Random)":
        study["modality"] = modality
    if study_description:
        study["study_description"] = study_description
    study["priority"] = priority

    if study:
        payload["study"] = study

    # Build lifecycle overrides (only non-zero values)
    overrides: dict = {}
    if intro_to_assigned > 0:
        overrides["Introduced_to_Assigned"] = intro_to_assigned
    if assigned_to_dictating > 0:
        overrides["Assigned_to_Dictating"] = assigned_to_dictating
    if dictating_to_pending > 0:
        overrides["Dictating_to_Pending_Approval"] = dictating_to_pending
    if pending_to_approved > 0:
        overrides["Pending_Approval_to_Approved"] = pending_to_approved

    if overrides:
        payload["lifecycle_overrides"] = overrides

    if cancel_at != "(Don't cancel)":
        payload["cancel_at_stage"] = cancel_at

    # Submit
    result = api_client.create_demand(payload)

    if "error" in result:
        st.error(f"Failed: {result['error']}")
    else:
        study = result.get("study", {})
        accession = study.get("accession_number", "unknown")
        patient = study.get("patient_name", "unknown")
        st.success(f"Study created: **{accession}** — {patient}")
        with st.expander("Study details"):
            st.json(study)
