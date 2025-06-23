import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import os
import sys
from dotenv import load_dotenv
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


@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data(_client):
    """Loads all daily logs from the database."""
    db = _client[settings.DB_NAME]
    logs = list(db.daily_logs.find({}))
    if not logs:
        return pd.DataFrame()

    # Flatten the nested data into a structured DataFrame
    flat_data = []
    for log in logs:
        if log.get("workout_session") and log["workout_session"].get(
            "completed_exercises"
        ):
            for exercise in log["workout_session"]["completed_exercises"]:
                for s_idx, set_data in enumerate(exercise["sets"]):
                    flat_data.append(
                        {
                            "date": pd.to_datetime(log["date"]),
                            "exercise_name": exercise["name"],
                            "set_number": s_idx + 1,
                            "weight": set_data["weight"],
                            "reps": set_data["reps"],
                            "rpe": set_data.get("rpe"),
                            "volume": set_data["weight"] * set_data["reps"],
                        }
                    )
    return pd.DataFrame(flat_data)


# --- Ollama Integration ---
def get_ollama_insight(data_json: str):
    """Sends workout data to local Ollama for analysis."""
    system_prompt = f"""
    You are Astra, an expert AI strength and conditioning coach. Your user, Himansh, has been logging his workouts.
    Analyze the following JSON data which represents his recent performance.
    Your task is to provide ONE SINGLE, actionable, and encouraging insight based on the data. 
    Focus on trends, potential plateaus, or areas of exceptional progress. Be specific. Do not be generic.
    Today's Date: {datetime.now().strftime('%Y-%m-%d')}
    """

    user_prompt = f"Here is my recent workout data in JSON format:\n{data_json}"

    try:
        # THE FIX: Use the /api/chat endpoint and the corrected payload structure
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "gemma3:latest",  # Use a model you have installed
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
    st.markdown(
        "Your central command center for tracking progress and gaining insights."
    )

    client = get_mongo_client()
    df = load_data(client)

    if df.empty:
        st.warning("No workout data found. Go log some sets via WhatsApp!")
        return

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")
    all_exercises = sorted(df["exercise_name"].unique())
    selected_exercises = st.sidebar.multiselect(
        "Select Exercises for Volume Trend",
        options=all_exercises,
        default=[
            ex
            for ex in all_exercises
            if "Press" in ex or "Squat" in ex or "Row" in ex or "Pulldown" in ex
        ][
            :3
        ],  # Sensible defaults
    )

    # --- Main Layout ---
    col1, col2 = st.columns(2)

    # --- 1. Total Volume Trend ---
    with col1:
        st.subheader("📈 Total Volume Trend")
        if selected_exercises:
            filtered_df = df[df["exercise_name"].isin(selected_exercises)]
            volume_by_day = (
                filtered_df.groupby(["date", "exercise_name"])["volume"]
                .sum()
                .reset_index()
            )
            fig = px.line(
                volume_by_day,
                x="date",
                y="volume",
                color="exercise_name",
                title="Workout Volume (Weight x Reps x Sets) Over Time",
                labels={
                    "date": "Date",
                    "volume": "Total Volume (lbs/kg)",
                    "exercise_name": "Exercise",
                },
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(
                "Select one or more exercises from the sidebar to see the volume trend."
            )

    # --- 2. Personal Record (PR) Tracker ---
    with col2:
        st.subheader("🏆 Personal Records (by Weight)")
        pr_df = df.loc[df.groupby("exercise_name")["weight"].idxmax()]
        pr_df = (
            pr_df[["exercise_name", "weight", "reps", "date"]]
            .rename(
                columns={
                    "exercise_name": "Exercise",
                    "weight": "Max Weight",
                    "reps": "Reps at Max",
                    "date": "Date Set",
                }
            )
            .sort_values(by="Exercise")
            .reset_index(drop=True)
        )
        st.dataframe(pr_df, use_container_width=True)

    st.divider()

    # --- 3. Workout Consistency Heatmap ---
    st.subheader("🗓️ Workout Consistency")
    df["day"] = df["date"].dt.date
    consistency = df.groupby("day").size().reset_index(name="sets")
    consistency["year"] = pd.to_datetime(consistency["day"]).dt.year
    # Create a full date range for the heatmap
    date_range = pd.to_datetime(
        pd.date_range(start=consistency["day"].min(), end=consistency["day"].max())
    )
    calendar_df = pd.DataFrame(index=date_range)
    calendar_df["sets"] = (
        calendar_df.index.to_series()
        .dt.date.map(consistency.set_index("day")["sets"])
        .fillna(0)
    )

    # Using Plotly for a GitHub-style heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=calendar_df["sets"],
            x=calendar_df.index,
            y=[""],  # Fake y-axis
            colorscale="Greens",
            showscale=False,
        )
    )
    fig.update_layout(
        title="Workout Days Heatmap", yaxis_showticklabels=False, yaxis_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 4. Ollama AI Insights ---
    st.subheader("🤖 Astra's AI Insight")
    if st.button("Analyze My Recent Performance"):
        with st.spinner("Astra is thinking... Analyzing your last 10 workouts..."):
            # Prepare recent data for the LLM
            recent_data = df.tail(100).to_json(orient="records", date_format="iso")
            insight = get_ollama_insight(recent_data)
            st.info(insight)


if __name__ == "__main__":
    main()
