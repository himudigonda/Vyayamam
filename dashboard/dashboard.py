import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import os
import sys
import requests
import json
from datetime import datetime

# --- Allow importing from the parent directory ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings

# --- Page Configuration ---
st.set_page_config(
    page_title="Vyayamam Dashboard",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Database Connection ---
@st.cache_resource
def get_mongo_client():
    """Cached function to get a MongoDB client."""
    client = MongoClient(settings.MONGO_URI)
    return client


# --- MODIFIED: Enhanced data loading function for muscle groups ---
@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data(_client):
    """Loads and flattens data, now including muscle group mappings."""
    db = _client[settings.DB_NAME]

    # --- NEW: Fetch workout definitions to map exercises to muscle groups ---
    plan_definitions = list(db.workout_definitions.find({}))
    exercise_to_muscle_map = {}
    for day_plan in plan_definitions:
        for exercise in day_plan.get("exercises", []):
            # We take the first primary muscle group for simplicity in this chart
            if exercise.get("primary_muscle_groups"):
                exercise_to_muscle_map[exercise["name"]] = exercise["primary_muscle_groups"][0]

    logs = list(db.daily_logs.find({}))
    if not logs:
        return pd.DataFrame(), pd.DataFrame()  # Return two empty dataframes

    workout_data = []
    daily_data = []
    for log in logs:
        log_date = pd.to_datetime(log["date"])
        readiness = log.get("readiness", {})
        daily_data.append({"date": log_date, "sleep_hours": readiness.get("sleep_hours"), "stress_level": readiness.get("stress_level")})

        if log.get("workout_session") and log["workout_session"].get("completed_exercises"):
            for exercise in log["workout_session"]["completed_exercises"]:
                for s_idx, set_data in enumerate(exercise["sets"]):
                    workout_data.append({
                        "date": log_date,
                        "exercise_name": exercise["name"],
                        # --- NEW: Add muscle group to the dataframe ---
                        "muscle_group": exercise_to_muscle_map.get(exercise["name"], "Other"),
                        "set_number": s_idx + 1,
                        "weight": set_data["weight"],
                        "reps": set_data["reps"],
                        "rpe": set_data.get("rpe"),
                        "volume": set_data["weight"] * set_data["reps"],
                    })

    workout_df = pd.DataFrame(workout_data)
    daily_df = pd.DataFrame(daily_data).set_index('date')

    return workout_df, daily_df


# --- Ollama Integration (no changes needed here) ---
def get_ollama_insight(data_json: str):
    # ... (function remains the same)
    system_prompt = f"""
    You are Astra, an expert AI strength and conditioning coach. Your user, Himansh, has been logging his workouts.
    Analyze the following JSON data which represents his recent performance.
    Your task is to provide ONE SINGLE, actionable, and encouraging insight based on the data. 
    Focus on trends, potential plateaus, or areas of exceptional progress. Be specific. Do not be generic.
    Today's Date: {datetime.now().strftime('%Y-%m-%d')}
    """
    user_prompt = f"Here is my recent workout data in JSON format:\n{data_json}"
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "gemma3:latest",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        response_data = json.loads(response.text)
        return response_data.get("message", {}).get("content", "")
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Ollama: {e}. Make sure the Ollama application is running."


# --- Main Dashboard App ---
def main():
    st.title("🏋️ Vyayamam Performance Dashboard")
    st.markdown("Your central command center for tracking progress and gaining insights.")

    client = get_mongo_client()
    df_workouts, df_daily = load_data(client)

    if df_workouts.empty:
        st.warning("No workout data found. Go log some sets via WhatsApp!")
        return

    # --- Sidebar (no changes needed here) ---
    st.sidebar.header("Filters")
    all_exercises = sorted(df_workouts["exercise_name"].unique())
    selected_exercises = st.sidebar.multiselect(
        "Select Exercises for Volume Trend",
        options=all_exercises,
        default=[ex for ex in ["Smith Machine Incline Press", "Leg Press Machine", "Lat Pulldowns"] if ex in all_exercises]
    )

    # --- Top Section (Volume Trend & PRs) ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Total Volume Trend")
        if selected_exercises:
            filtered_df = df_workouts[df_workouts["exercise_name"].isin(selected_exercises)]
            volume_by_day = filtered_df.groupby(["date", "exercise_name"])["volume"].sum().reset_index()
            fig = px.line(
                volume_by_day, x="date", y="volume", color="exercise_name",
                title="Workout Volume (Weight x Reps x Sets) Over Time",
                labels={"date": "Date", "volume": "Total Volume (lbs/kg)", "exercise_name": "Exercise"}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select one or more exercises from the sidebar to see the volume trend.")
    
    with col2:
        st.subheader("🏆 Personal Records (by Weight)")
        pr_df = df_workouts.loc[df_workouts.groupby("exercise_name")["weight"].idxmax()]
        pr_df = pr_df[["exercise_name", "weight", "reps", "date"]].rename(
            columns={"exercise_name": "Exercise", "weight": "Max Weight", "reps": "Reps at Max", "date": "Date Set"}
        ).sort_values(by="Exercise").reset_index(drop=True)
        st.dataframe(pr_df, use_container_width=True, hide_index=True)

    st.divider()

    # --- NEW: Muscle Group Volume Section ---
    st.subheader("📊 Weekly Volume by Muscle Group")
    if 'muscle_group' in df_workouts.columns:
        # Resample data by week. 'W-MON' means weeks start on Monday.
        df_workouts['week'] = df_workouts['date'].dt.to_period('W-MON').apply(lambda p: p.start_time)
        
        weekly_muscle_volume = df_workouts.groupby(['week', 'muscle_group'])['volume'].sum().reset_index()

        fig_muscle = px.bar(
            weekly_muscle_volume,
            x='week',
            y='volume',
            color='muscle_group',
            title="Total Weekly Volume by Primary Muscle Group",
            labels={'week': 'Week', 'volume': 'Total Volume (lbs/kg)', 'muscle_group': 'Muscle Group'},
            color_discrete_map={
                "Chest": "#0099C6", "Back": "#34A853", "Shoulders": "#A23B72",
                "Quads": "#F47920", "Hamstrings": "#F15A24", "Biceps": "#9BC53D",
                "Triceps": "#662E91", "Cardio": "#E63946", "Other": "grey"
            }
        )
        st.plotly_chart(fig_muscle, use_container_width=True)
    else:
        st.info("Muscle group data not available for analysis.")

    st.divider()

    # --- Consistency Heatmap (no changes needed here) ---
    st.subheader("🗓️ Workout Consistency")
    df_workouts["day"] = df_workouts["date"].dt.date
    consistency = df_workouts.groupby("day").size().reset_index(name="sets")
    date_range = pd.to_datetime(pd.date_range(start=consistency["day"].min(), end=consistency["day"].max()))
    calendar_df = pd.DataFrame(index=date_range)
    calendar_df["sets"] = calendar_df.index.to_series().dt.date.map(consistency.set_index("day")["sets"]).fillna(0)
    fig_heatmap = go.Figure(data=go.Heatmap(z=calendar_df["sets"], x=calendar_df.index, y=[""], colorscale="Greens", showscale=False))
    fig_heatmap.update_layout(title="Workout Days Heatmap", yaxis_showticklabels=False, yaxis_visible=False)
    st.plotly_chart(fig_heatmap, use_container_width=True)

    st.divider()

    # --- Readiness vs Performance (no changes needed) ---
    st.subheader("🧘‍♂️ Readiness vs. Performance")

    # Calculate total daily volume
    daily_volume = df_workouts.groupby('date')['volume'].sum()

    # Merge with daily readiness data
    performance_df = pd.merge(daily_volume, df_daily, on='date', how='left').reset_index()
    performance_df = performance_df.dropna(subset=['sleep_hours', 'stress_level', 'volume'])

    if not performance_df.empty:
        # Create a dual-axis chart
        fig_corr = go.Figure()

        # Bar chart for Volume
        fig_corr.add_trace(
            go.Bar(
                x=performance_df["date"],
                y=performance_df["volume"],
                name="Workout Volume",
                marker_color="lightgreen",
            )
        )

        # Line chart for Sleep
        fig_corr.add_trace(
            go.Scatter(
                x=performance_df["date"],
                y=performance_df["sleep_hours"],
                name="Sleep (hours)",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="blue"),
            )
        )

        # Line chart for Stress
        fig_corr.add_trace(
            go.Scatter(
                x=performance_df["date"],
                y=performance_df["stress_level"],
                name="Stress (1-10)",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="red", dash="dash"),
            )
        )

        fig_corr.update_layout(
            title_text="How Readiness Affects Performance",
            xaxis_title="Date",
            yaxis_title="Total Workout Volume (lbs/kg)",
            yaxis=dict(side="left", showgrid=False),
            yaxis2=dict(
                title="Readiness Metrics",
                overlaying="y",
                side="right",
                range=[0, 11],  # Set range for sleep/stress axis
                showgrid=False,
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info(
            "Not enough readiness and workout data logged on the same days to show correlations."
        )

    st.divider()

    # --- AI Insights Section (no changes needed) ---
    st.subheader("🤖 Astra's AI Insight")
    if st.button("Analyze My Recent Performance"):
        with st.spinner("Astra is thinking... Analyzing your last 10 workouts..."):
            recent_data = df_workouts.tail(100).to_json(
                orient="records", date_format="iso"
            )
            insight = get_ollama_insight(recent_data)
            st.info(insight)


if __name__ == "__main__":
    main()
