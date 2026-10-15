import streamlit as st
import pandas as pd
import plotly.express as px
from database import PROJECT_ROOT

# --------------------------------------------------
# Page configuration
# --------------------------------------------------
st.set_page_config(
    page_title="Municipal Complaint Analytics",
    page_icon="📊",
    layout="wide",
)


def render_analytics_dashboard():
    # Consistent basic styling
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
            }
            h1, h2, h3 {
                font-weight: 650;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Municipal Complaint Prioritization")
    st.subheader("Analytics dashboard")
    st.caption("Overview of municipal complaints")

    # --------------------------------------------------
    # Load the complete feature-engineered dataset
    # --------------------------------------------------
    DATA_PATH = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "feature_engineered_complaints.csv"
    )

    @st.cache_data
    def load_data(path):
        data = pd.read_csv(path)

        data["reported_date"] = pd.to_datetime(
            data["reported_date"], errors="coerce"
        )

        for column in ["category", "sub_category", "ward", "status", "severity"]:
            data[column] = data[column].fillna("Unknown").astype(str).str.strip()

        return data

    try:
        df = load_data(str(DATA_PATH))
    except FileNotFoundError:
        st.error(f"Dataset not found: {DATA_PATH}")
        st.stop()
    except Exception as error:
        st.error(f"Could not load the dataset: {error}")
        st.stop()

    if df.empty:
        st.warning("The feature-engineered dataset contains no records.")
        st.stop()


    # --------------------------------------------------
    # Analytics filters — below Complaint Overview
    # --------------------------------------------------
    st.subheader("Complaint Overview")

    # Show overview metrics before filtering
    total_complaints = len(df)

    resolved_count = int(
        df["status"].str.casefold().eq("resolved").sum()
    )
    closed_count = int(
        df["status"].str.casefold().eq("closed").sum()
    )
    completed_count = int(
        df["status"].str.casefold().isin(["resolved", "closed"]).sum()
    )
    pending_count = total_complaints - completed_count

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Complaints", f"{total_complaints:,}")
    col2.metric("Pending Complaints", f"{pending_count:,}")
    col3.metric("Resolved", f"{resolved_count:,}")
    col4.metric("Closed", f"{closed_count:,}")

    st.divider()

    # Filters displayed below the overview cards
    st.subheader("Analytics Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        categories = ["All"] + sorted(df["category"].unique().tolist())
        selected_category = st.selectbox("Category", categories)

    with col2:
        subcategory_source = (
            df if selected_category == "All"
            else df[df["category"] == selected_category]
        )
        subcategories = [
            "All"
        ] + sorted(subcategory_source["sub_category"].unique().tolist())
        selected_subcategory = st.selectbox("Subcategory", subcategories)

    with col3:
        wards = ["All"] + sorted(df["ward"].unique().tolist())
        selected_ward = st.selectbox("Ward", wards)

    col1, col2 = st.columns(2)

    with col1:
        statuses = ["All"] + sorted(df["status"].unique().tolist())
        selected_status = st.selectbox("Status", statuses)

    with col2:
        severities = ["All"] + sorted(df["severity"].unique().tolist())
        selected_severity = st.selectbox("Severity", severities)

    # Apply filters to the analytics data
    filtered_df = df.copy()

    if selected_category != "All":
        filtered_df = filtered_df[
            filtered_df["category"] == selected_category
        ]

    if selected_subcategory != "All":
        filtered_df = filtered_df[
            filtered_df["sub_category"] == selected_subcategory
        ]

    if selected_ward != "All":
        filtered_df = filtered_df[
            filtered_df["ward"] == selected_ward
        ]

    if selected_status != "All":
        filtered_df = filtered_df[
            filtered_df["status"] == selected_status
        ]

    if selected_severity != "All":
        filtered_df = filtered_df[
            filtered_df["severity"] == selected_severity
        ]

    st.caption(f"Showing {len(filtered_df):,} of {len(df):,} complaints")
    st.divider()


    if filtered_df.empty:
        st.info("No complaints match the selected filters.")
        st.stop()

    # --------------------------------------------------
    # Category and subcategory analysis
    # --------------------------------------------------
    st.subheader("Complaint Distribution")

    col1, col2 = st.columns(2)

    with col1:
        category_counts = (
            filtered_df.groupby("category")
            .size()
            .reset_index(name="Complaints")
            .sort_values("Complaints", ascending=False)
        )

        fig_category = px.bar(
            category_counts,
            x="category",
            y="Complaints",
            title="Complaints by Category",
            labels={"category": "Category"},
            text="Complaints",
        )
        fig_category.update_layout(
            xaxis_title="Category",
            yaxis_title="Number of Complaints",
        )
        st.plotly_chart(fig_category, use_container_width=True)

    with col2:
        subcategory_counts = (
            filtered_df.groupby(["category", "sub_category"])
            .size()
            .reset_index(name="Complaints")
            .sort_values("Complaints", ascending=False)
        )

        fig_subcategory = px.bar(
            subcategory_counts,
            x="sub_category",
            y="Complaints",
            color="category",
            title="Complaints by Subcategory",
            labels={
                "sub_category": "Subcategory",
                "category": "Category",
            },
            text="Complaints",
        )
        fig_subcategory.update_layout(
            xaxis_title="Subcategory",
            yaxis_title="Number of Complaints",
            showlegend=True,
        )
        st.plotly_chart(fig_subcategory, use_container_width=True)

    # --------------------------------------------------
    # Ward analysis
    # --------------------------------------------------
    st.subheader("Ward Analysis")

    ward_counts = (
        filtered_df.groupby("ward")
        .size()
        .reset_index(name="Complaints")
        .sort_values("Complaints", ascending=False)
    )

    fig_ward = px.bar(
        ward_counts,
        x="ward",
        y="Complaints",
        title="Complaints by Ward",
        labels={"ward": "Ward"},
        text="Complaints",
    )
    fig_ward.update_layout(
        xaxis_title="Ward",
        yaxis_title="Number of Complaints",
    )
    st.plotly_chart(fig_ward, use_container_width=True)

    st.divider()

    # --------------------------------------------------
    # Status and severity analysis
    # --------------------------------------------------
    st.subheader("Status and Severity Analysis")

    col1, col2 = st.columns(2)

    with col1:
        status_counts = (
            filtered_df.groupby("status")
            .size()
            .reset_index(name="Complaints")
        )

        fig_status = px.pie(
            status_counts,
            names="status",
            values="Complaints",
            title="Complaint Status Distribution",
            hole=0.4,
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with col2:
        severity_counts = (
            filtered_df.groupby("severity")
            .size()
            .reset_index(name="Complaints")
        )

        fig_severity = px.bar(
            severity_counts,
            x="severity",
            y="Complaints",
            title="Complaints by Severity",
            text="Complaints",
        )
        fig_severity.update_layout(
            xaxis_title="Severity",
            yaxis_title="Number of Complaints",
        )
        st.plotly_chart(fig_severity, use_container_width=True)

    # --------------------------------------------------
    # Reporting trend
    # --------------------------------------------------
    st.subheader("Complaint Reporting Trend")

    trend_df = filtered_df.dropna(subset=["reported_date"]).copy()

    if not trend_df.empty:
        trend_df["Month"] = (
            trend_df["reported_date"].dt.to_period("M").astype(str)
        )

        monthly_counts = (
            trend_df.groupby("Month")
            .size()
            .reset_index(name="Complaints")
            .sort_values("Month")
        )

        fig_trend = px.line(
            monthly_counts,
            x="Month",
            y="Complaints",
            markers=True,
            title="Complaints Reported per Month",
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No valid reporting dates are available.")

    # --------------------------------------------------
    # Additional complaint indicators
    # --------------------------------------------------
    st.subheader("Additional Indicators")

    col1, col2, col3 = st.columns(3)

    if "is_active_complaint" in filtered_df.columns:
        active = filtered_df["is_active_complaint"].astype(str).str.lower()
        active_count = int(active.isin(["true", "1", "yes"]).sum())
        col1.metric("Active Complaints (Flag)", f"{active_count:,}")

    if "recurrence_indicator" in filtered_df.columns:
        recurring = pd.to_numeric(
            filtered_df["recurrence_indicator"], errors="coerce"
        ).fillna(0)
        col2.metric(
            "Recurring Complaints",
            f"{int((recurring > 0).sum()):,}",
        )

    if "people_affected" in filtered_df.columns:
        people = pd.to_numeric(
            filtered_df["people_affected"], errors="coerce"
        )
        col3.metric(
            "People Affected (Sum)",
            f"{int(people.sum()):,}" if people.notna().any() else "N/A",
        )

    # --------------------------------------------------
    # Detailed records
    # --------------------------------------------------
    st.divider()
    st.subheader("Complaint Records")

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Filtered Complaints",
        data=csv_data,
        file_name="filtered_complaint_analytics.csv",
        mime="text/csv",
    )


# Custom sidebar navigation
pages = [
    st.Page(
        render_analytics_dashboard,
        title="Analytics Dashboard",
        icon=":material/analytics:",
        default=True,
    ),
    st.Page(
        "pages/2_Officer_Priority_Queue.py",
        title="Complaint Ranking",
        icon=":material/format_list_numbered:",
    ),
    st.Page(
        "pages/3_Complaint_Management.py",
        title="Complaint Management",
        icon=":material/assignment:",
    ),
    st.Page(
        "pages/4_Citizen_Complaint_Registration.py",
        title="Citizen Complaint Registration",
        icon=":material/post_add:",
    ),
]

pg = st.navigation(pages)
pg.run()
