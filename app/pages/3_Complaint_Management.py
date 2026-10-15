
import streamlit as st
import pandas as pd
from datetime import datetime
from database import get_connection, create_tables

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Complaint Management",
    page_icon="🗂️",
    layout="wide",
)

st.title("Municipal Complaint Prioritization")
st.subheader("Complaint Management")
st.caption("Search complaints, assign workers, and track progress")
st.set_page_config(
    page_title="Complaint Management",
    page_icon="🗂️",
    layout="wide",
)

# --------------------------------------------------
# Initialize database and management tables
# --------------------------------------------------
create_tables()

with get_connection() as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS complaint_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            worker_name TEXT NOT NULL,
            department TEXT,
            assigned_at TEXT NOT NULL,
            assignment_notes TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS complaint_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            notes TEXT,
            updated_at TEXT NOT NULL
        )
    """)

# --------------------------------------------------
# Search complaints
# --------------------------------------------------
st.subheader("Find a Complaint")

search_value = st.text_input(
    "Search by Complaint ID or Citizen ID",
    placeholder="Enter complaint ID or citizen ID",
)

with get_connection() as connection:
    if search_value.strip():
        search_term = f"%{search_value.strip()}%"
        complaints = pd.read_sql_query(
            """
            SELECT *
            FROM complaints
            WHERE complaint_id LIKE ?
               OR citizen_id LIKE ?
            ORDER BY priority_rank ASC
            """,
            connection,
            params=(search_term, search_term),
        )
    else:
        complaints = pd.read_sql_query(
            """
            SELECT *
            FROM complaints
            ORDER BY priority_rank ASC
            LIMIT 100
            """,
            connection,
        )

if complaints.empty:
    st.warning(
        "No matching complaints found in the application database."
    )
    st.stop()

# --------------------------------------------------
# Select and view complaint
# --------------------------------------------------
st.subheader("Complaint Details")

complaint_ids = complaints["complaint_id"].astype(str).tolist()

selected_id = st.selectbox(
    "Select Complaint",
    complaint_ids,
)

selected_complaint = complaints[
    complaints["complaint_id"].astype(str) == selected_id
].iloc[0]

detail_columns = [
    "complaint_id",
    "citizen_id",
    "category",
    "sub_category",
    "ward",
    "reported_date",
    "status",
    "severity",
    "priority_rank",
    "priority_level",
    "complaint_age_days",
    "people_affected",
]

available_columns = [
    column for column in detail_columns
    if column in complaints.columns
]

st.dataframe(
    selected_complaint[available_columns].to_frame(
        name="Complaint Details"
    ),
    use_container_width=True,
)

st.divider()

# --------------------------------------------------
# Assign a worker
# --------------------------------------------------
st.subheader("Assign Responsible Worker")

with get_connection() as connection:
    assignments = pd.read_sql_query(
        """
        SELECT *
        FROM complaint_assignments
        WHERE complaint_id = ?
        ORDER BY assignment_id DESC
        """,
        connection,
        params=(selected_id,),
    )

if not assignments.empty:
    latest_assignment = assignments.iloc[0]
    st.info(
        f"Current/latest assignment: "
        f"{latest_assignment['worker_name']} "
        f"({latest_assignment['department'] or 'Department not specified'})"
    )
else:
    st.info("No worker has been assigned to this complaint yet.")

with st.form("assignment_form"):
    worker_name = st.text_input(
        "Worker / Officer Name",
        placeholder="Enter responsible worker's name",
    )

    department = st.text_input(
        "Department",
        placeholder="e.g. Public Health, Water Supply, Electrical",
    )

    assignment_notes = st.text_area(
        "Assignment Notes",
        placeholder="Describe the assigned task",
    )

    assign_button = st.form_submit_button(
        "Save Assignment",
        type="primary",
    )

    if assign_button:
        if not worker_name.strip():
            st.error("Please enter a worker or officer name.")
        else:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO complaint_assignments (
                        complaint_id,
                        worker_name,
                        department,
                        assigned_at,
                        assignment_notes
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        selected_id,
                        worker_name.strip(),
                        department.strip(),
                        datetime.now().isoformat(timespec="seconds"),
                        assignment_notes.strip(),
                    ),
                )

            st.success(f"Assignment saved for complaint {selected_id}.")
            st.rerun()

st.divider()

# --------------------------------------------------
# Update complaint status
# --------------------------------------------------
st.subheader("Update Complaint Progress")

current_status = str(selected_complaint["status"])

allowed_statuses = [
    "Registered",
    "Verified",
    "Assigned",
    "In Progress",
    "Resolved",
    "Closed",
]

if current_status not in allowed_statuses:
    allowed_statuses.insert(0, current_status)

with st.form("status_form"):
    new_status = st.selectbox(
        "New Status",
        allowed_statuses,
        index=allowed_statuses.index(current_status),
    )

    progress_notes = st.text_area(
        "Progress / Resolution Notes",
        placeholder="Describe the action taken or resolution",
    )

    update_button = st.form_submit_button(
        "Save Progress",
        type="primary",
    )

    if update_button:
        if new_status == current_status:
            st.info("The complaint already has this status.")
        else:
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE complaints
                    SET status = ?
                    WHERE complaint_id = ?
                    """,
                    (new_status, selected_id),
                )

                connection.execute(
                    """
                    INSERT INTO complaint_history (
                        complaint_id,
                        previous_status,
                        new_status,
                        notes,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        selected_id,
                        current_status,
                        new_status,
                        progress_notes.strip(),
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )

            st.success(
                f"Complaint {selected_id} updated to {new_status}."
            )
            st.rerun()

st.divider()

# --------------------------------------------------
# Assignment history
# --------------------------------------------------
st.subheader("Assignment History")

with get_connection() as connection:
    assignment_history = pd.read_sql_query(
        """
        SELECT
            worker_name,
            department,
            assigned_at,
            assignment_notes
        FROM complaint_assignments
        WHERE complaint_id = ?
        ORDER BY assignment_id DESC
        """,
        connection,
        params=(selected_id,),
    )

if assignment_history.empty:
    st.caption("No assignment history available.")
else:
    st.dataframe(
        assignment_history,
        use_container_width=True,
        hide_index=True,
    )

# --------------------------------------------------
# Status history
# --------------------------------------------------
st.subheader("Complaint Status History")

with get_connection() as connection:
    status_history = pd.read_sql_query(
        """
        SELECT
            previous_status,
            new_status,
            notes,
            updated_at
        FROM complaint_history
        WHERE complaint_id = ?
        ORDER BY history_id DESC
        """,
        connection,
        params=(selected_id,),
    )

if status_history.empty:
    st.caption("No status updates recorded through this page yet.")
else:
    st.dataframe(
        status_history,
        use_container_width=True,
        hide_index=True,
    )