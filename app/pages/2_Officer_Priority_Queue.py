
import streamlit as st
import pandas as pd
from database import get_connection, create_tables
from datetime import date

st.set_page_config(
    page_title="Municipal Complaint Prioritization",
    layout="wide"
)

st.title("Municipal Complaint Prioritization")
st.subheader("Complaint Ranking")
st.caption("Smart complaint ranking.")

# Connect to the database
create_tables()

with get_connection() as connection:
    df = pd.read_sql_query("""
        SELECT
            priority_rank,
            complaint_id,
            citizen_id,
            category,
            sub_category,
            ward,
            reported_date,
            status,
            people_affected,
            vulnerable_population,
            public_safety_risk,
            recurrence_indicator,
            severity,
            complaint_age_days,
            priority_level
        FROM complaints
        WHERE status NOT IN ('Resolved', 'Closed')
        ORDER BY priority_rank ASC
    """, connection)

# Summary metrics
col1, col2, col3 = st.columns(3)
col1.metric("Pending Complaints", len(df))
col2.metric(
    "High / Urgent",
    df["priority_level"].isin(["High", "Urgent"]).sum()
    if not df.empty else 0
)
col3.metric(
    "Wards Affected",
    df["ward"].nunique() if not df.empty else 0
)

st.divider()

# Filters
col1, col2, col3 = st.columns(3)

with col1:
    wards = ["All"] + sorted(df["ward"].dropna().unique().tolist())
    selected_ward = st.selectbox("Filter by Ward", wards)

with col2:
    severities = ["All"] + sorted(
        df["severity"].dropna().unique().tolist()
    )
    selected_severity = st.selectbox("Filter by Severity", severities)

with col3:
    statuses = ["All"] + sorted(
        df["status"].dropna().unique().tolist()
    )
    selected_status = st.selectbox("Filter by Status", statuses)

filtered_df = df.copy()

if selected_ward != "All":
    filtered_df = filtered_df[filtered_df["ward"] == selected_ward]

if selected_severity != "All":
    filtered_df = filtered_df[
        filtered_df["severity"] == selected_severity
    ]

if selected_status != "All":
    filtered_df = filtered_df[
        filtered_df["status"] == selected_status
    ]


search_id = st.text_input(
    "Search by Complaint ID or Citizen ID",
    placeholder="e.g. C006349 or P0001"
)

if search_id.strip():
    search_value = search_id.strip().lower()

    filtered_df = filtered_df[
        filtered_df["complaint_id"].astype(str).str.lower().str.contains(
            search_value, na=False
        )
        |
        filtered_df["citizen_id"].astype(str).str.lower().str.contains(
            search_value, na=False
        )
    ]

st.subheader("Ranked Complaints")

if filtered_df.empty:
    st.info("No complaints match these filters.")
else:
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )

# Update Complaint Status section goes here
st.divider()
st.subheader("Update Complaint Status")

if not filtered_df.empty:
    complaint_ids = filtered_df["complaint_id"].tolist()

    selected_id = st.selectbox(
        "Select Complaint",
        complaint_ids
    )

    current_status = filtered_df.loc[
        filtered_df["complaint_id"] == selected_id, "status"
    ].iloc[0]

    allowed_statuses = [
        "Registered",
        "Verified",
        "Assigned",
        "In Progress",
        "Resolved",
        "Closed",
    ]

    selected_status = st.selectbox(
        "New Status",
        allowed_statuses,
        index=(
            allowed_statuses.index(current_status)
            if current_status in allowed_statuses else 0
        ),
    )

    if st.button("Save Status", type="primary"):
        if selected_status == current_status:
            st.info("The complaint already has this status.")
        else:
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE complaints
                    SET status = ?
                    WHERE complaint_id = ?
                    """,
                    (selected_status, selected_id),
                )

            st.success(
                f"Complaint {selected_id} updated to {selected_status}."
            )
            st.rerun()
else:
    st.info("No complaints available to update.")