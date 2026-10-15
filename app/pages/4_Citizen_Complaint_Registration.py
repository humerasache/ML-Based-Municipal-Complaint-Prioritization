# app/pages/4_Citizen_Complaint_Registration.py

from pathlib import Path
import sqlite3
import joblib
import pandas as pd
import streamlit as st
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "feature_engineered_complaints.csv"
DATABASE_PATH = PROJECT_ROOT / "data" / "municipal_complaints.db"
SEVERITY_MODEL_PATH = PROJECT_ROOT / "models" / "final_severity_model.joblib"
PRIORITY_MODEL_PATH = PROJECT_ROOT / "models" / "complaint_priority_model.joblib"

#st.write("Project root:", PROJECT_ROOT)
#st.write("Priority model path:", PRIORITY_MODEL_PATH)
#st.write("Priority model exists:", PRIORITY_MODEL_PATH.is_file())

st.set_page_config(page_title="Register Complaint", page_icon="📝", layout="wide")

st.title("Municipal Complaint Prioritization")
st.subheader("📝 Citizen Complaint Registration")
st.caption("Register a municipal complaint and receive a predicted severity level.")

@st.cache_data
def load_reference_data():
    return pd.read_csv(DATA_PATH)

@st.cache_resource
def load_model(path):
    if path.exists():
        return joblib.load(path)
    return None

def get_connection():
    return sqlite3.connect(DATABASE_PATH)

def get_subcategories(data, category=None):
    if "category" not in data.columns or "sub_category" not in data.columns:
        return []

    data = data.copy()

    data["category"] = data["category"].astype(str).str.strip()
    data["sub_category"] = data["sub_category"].astype(str).str.strip()

    if category is not None:
        filtered = data.loc[
            data["category"].str.casefold() == str(category).strip().casefold(),
            "sub_category"
        ]
    else:
        filtered = data["sub_category"]

    return sorted(
        filtered[filtered.ne("") & filtered.ne("nan")].unique().tolist()
    )



def predict_model(model, values):
    if model is None:
        return None, "Model file not found."

    try:
        input_df = pd.DataFrame([values])

        # Prepare input specifically for the priority model
        if "severity" in input_df.columns and "status" in input_df.columns:
            expected_columns = [
                "severity",
                "status",
                "public_safety_risk",
                "people_affected",
                "vulnerable_population_ratio",
                "complaint_age_days",
            ]

            input_df = input_df.reindex(columns=expected_columns)

            # Categorical features must remain strings
            input_df["severity"] = input_df["severity"].astype(str)
            input_df["status"] = input_df["status"].astype(str)

            # Numerical features must be numeric
            numeric_columns = [
                "public_safety_risk",
                "people_affected",
                "vulnerable_population_ratio",
                "complaint_age_days",
            ]

            for col in numeric_columns:
                input_df[col] = pd.to_numeric(
                    input_df[col], errors="raise"
                )

        # Run prediction
        prediction = model.predict(input_df)[0]

        # Return both values expected by the calling code
        return prediction, None

    except Exception as exc:
        return None, str(exc)


try:
    reference_data = load_reference_data()
except Exception as exc:
    st.error(f"Could not load complaint reference data: {exc}")
    st.stop()

severity_model = load_model(SEVERITY_MODEL_PATH)
priority_model = load_model(PRIORITY_MODEL_PATH)

categories = sorted(reference_data["category"].dropna().astype(str).unique())
wards = sorted(reference_data["ward"].dropna().astype(str).unique())

st.info("Fields marked with * are required.")
st.subheader("Complaint Details")

col1, col2 = st.columns(2)

with col1:
    citizen_id = st.text_input(
        "Citizen ID *",
        placeholder="Example: P0001"
    ).strip()

    category = st.selectbox(
        "Complaint Category *",
        categories,
        key="complaint_category"
    )

    subcategories = get_subcategories(reference_data, category)
    if not subcategories:
        subcategories = get_subcategories(reference_data)

    sub_category = st.selectbox(
        "Complaint Subcategory *",
        subcategories if subcategories else ["Other"],
        key="complaint_subcategory"
    )

    ward = st.selectbox("Ward *", wards)

with col2:
    people_affected = st.number_input(
        "Estimated People Affected *",
        min_value=1,
        max_value=1000000,
        value=1,
        step=1
    )

    vulnerable_population = st.number_input(
        "Vulnerable People Affected",
        min_value=0,
        max_value=1000000,
        value=0,
        step=1
    )

    public_safety_risk = st.selectbox(
        "Public Safety Risk *",
        ["Low", "Medium", "High"]
    )

    recurrence_indicator = st.selectbox(
        "Has This Issue Recurred? *",
        ["No", "Yes"]
    )

submitted = st.button(
    "Register Complaint",
    type="primary",
    use_container_width=True
)

if submitted:
    if not citizen_id:
        st.error("Please enter your Citizen ID.")
        st.stop()

    if vulnerable_population > people_affected:
        st.error("Vulnerable people affected cannot exceed total people affected.")
        st.stop()

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            connection.row_factory = sqlite3.Row

            existing_tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

            table_names = [row["name"] for row in existing_tables]

            if "complaints" not in table_names:
                st.error(
                    "The complaints table does not exist. "
                    "Please use your existing database initialization."
                )
                st.stop()

            columns = [
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(complaints)"
                ).fetchall()
            ]

            complaint_id = f"C{pd.Timestamp.now().strftime('%Y%m%d%H%M%S%f')}"
            reported_date_text = date.today().isoformat()

            ratio = (
                vulnerable_population / people_affected
                if people_affected > 0 else 0
            )

            # Only features provided by the registration form are used here.
            # Additional model features must be supplied by the existing pipeline.
            features = {
                "category": category,
                "sub_category": sub_category,
                "ward": ward,
                "reported_date": reported_date_text,
                "people_affected": int(people_affected),
                "vulnerable_population": int(vulnerable_population),
                "public_safety_risk": public_safety_risk,
                "recurrence_indicator": (
                    1 if recurrence_indicator == "Yes" else 0
                ),
                "vulnerable_population_ratio": ratio,
                "complaint_age_days": 0,
                "is_active_complaint": 1,
                "ward_complaint_load": 0,
            }

            # Step 1: Predict severity
            severity_prediction, severity_error = predict_model(
            severity_model, features
            )

            # Step 2: Predict priority using severity and status
            if severity_prediction is not None:
                priority_features = {
                    "severity": str(severity_prediction),
                    "status": "Registered",

                    # Convert the form selection to the numeric scale
                    # used by the priority model during training.
                    "public_safety_risk": {
                        "Low": 0.0,
                        "Medium": 0.5,
                        "High": 1.0,
                    }[features["public_safety_risk"]],

                    "people_affected": features["people_affected"],
                    "vulnerable_population_ratio": features["vulnerable_population_ratio"],
                    "complaint_age_days": features["complaint_age_days"],
                }

                # Ensure numerical inputs are numeric
                numeric_columns = [
                    "public_safety_risk",
                    "people_affected",
                    "vulnerable_population_ratio",
                    "complaint_age_days",
                ]


                priority_prediction, priority_error = predict_model(
                    priority_model, priority_features
                )

            
            else:
                priority_prediction = None
                priority_error = (
                    f"Priority prediction skipped: {severity_error}"
            )

            st.write("Priority model loaded:", priority_model is not None)
            st.write("Priority prediction:", priority_prediction)
            st.write("Priority prediction error:", priority_error)

            record = {
                "complaint_id": complaint_id,
                "citizen_id": citizen_id,
                "category": category,
                "sub_category": sub_category,
                "ward": ward,
                "reported_date": reported_date_text,
                "status": "Registered",
                "people_affected": int(people_affected),
                "vulnerable_population": int(vulnerable_population),
                "public_safety_risk": public_safety_risk,
                "recurrence_indicator": (
                    1 if recurrence_indicator == "Yes" else 0
                ),
                "vulnerable_population_ratio": ratio,
                "complaint_age_days": 0,
                "is_active_complaint": 1,
                "ward_complaint_load": 0,
            }

            if severity_prediction is not None:
                record["severity"] = str(severity_prediction)

            if priority_prediction is not None:
                score = float(priority_prediction)

                if "predicted_priority_score" in columns:
                    record["predicted_priority_score"] = score

                # Use the same priority-level thresholds as the ranking notebook.
                if "priority_level" in columns:
                    if score >= 80:
                        record["priority_level"] = "Urgent"
                    elif score >= 60:
                        record["priority_level"] = "High"
                    elif score >= 40:
                        record["priority_level"] = "Medium"
                    else:
                        record["priority_level"] = "Low"

            # Insert only fields supported by the existing database schema.
            insert_record = {
                key: value
                for key, value in record.items()
                if key in columns
            }

            if "complaint_id" not in insert_record:
                st.error(
                    "The existing complaints table does not contain "
                    "a complaint_id column."
                )
                st.stop()

            fields = list(insert_record.keys())
            placeholders = ", ".join(["?"] * len(fields))
            field_names = ", ".join(f'"{field}"' for field in fields)

            connection.execute(
                f"INSERT INTO complaints ({field_names}) "
                f"VALUES ({placeholders})",
                [insert_record[field] for field in fields]
            )

             # Recalculate ranks for all complaints with a predicted score.
            if "priority_rank" in columns and "predicted_priority_score" in columns:
                connection.execute("""
                    WITH ranked AS (
                        SELECT
                            complaint_id,
                            ROW_NUMBER() OVER (
                                ORDER BY predicted_priority_score DESC, reported_date ASC
                            ) AS new_rank
                        FROM complaints
                        WHERE predicted_priority_score IS NOT NULL
                        AND status NOT IN ('Resolved', 'Closed')
                    )
                    UPDATE complaints
                    SET priority_rank = (
                        SELECT new_rank
                        FROM ranked
                        WHERE ranked.complaint_id = complaints.complaint_id
                    )
                    WHERE complaint_id IN (SELECT complaint_id FROM ranked)
                """)


           

        st.success("Complaint registered successfully!")

        st.write("### Complaint Receipt")
        st.write(f"**Complaint ID:** {complaint_id}")
        st.write(f"**Category:** {category}")
        st.write(f"**Subcategory:** {sub_category}")
        st.write(f"**Ward:** {ward}")
        st.write(f"**Status:** Registered")

        if severity_prediction is not None:
            st.metric("Predicted Severity", str(severity_prediction))
        else:
            st.warning(
                "The complaint was saved, but severity prediction was "
                f"unavailable. {severity_error}"
            )

        if priority_prediction is not None:
            st.metric("Predicted Priority Score", f"{float(priority_prediction):.2f}")
        elif priority_model is None:
            st.caption(
                "Priority prediction is not enabled because "
                "complaint_priority_model.joblib was not found."
            )
        else:
            st.caption(f"Priority prediction unavailable: {priority_error}")

    except sqlite3.IntegrityError as exc:
        st.error(f"Could not register complaint because of a database constraint: {exc}")
    except Exception as exc:
        st.error(f"An error occurred while registering the complaint: {exc}")