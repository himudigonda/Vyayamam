# app/api/ai_coach.py
import requests
import json
from app.core.logging_config import log

# THE FIX: Correct the API endpoint URL
OLLAMA_API_URL = "http://localhost:11434/api/chat"


async def get_ai_response(user_id: str, user_question: str) -> str:
    from app.db.operations import get_recent_workouts_summary

    log.info(f"🤖 AI COACH: Generating response for question: '{user_question}'")

    workout_history = await get_recent_workouts_summary(user_id, limit=5)
    if not workout_history:
        return "I don't have enough workout history for you yet. Please log a few more workouts before asking for analysis."

    workout_history_json = json.dumps(workout_history, indent=2)

    # --- NEW: WhatsApp-optimized, concise, anti-hallucination prompt ---
    system_prompt = (
        "You are Astra, an expert strength coach. "
        "Reply with a short, factual, actionable answer for WhatsApp. "
        "Use only the workout data provided. No hallucination. "
        "Use clear language, short paragraphs, and emojis. No markdown, no code blocks."
    )

    user_prompt = (
        f"Question: {user_question}\n"
        f"Workout data:\n{workout_history_json}"
    )

    log.info("🤖 AI COACH: Sending prompt to Ollama...")

    try:
        payload = {
            "model": "gemma3:latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()

        response_data = json.loads(response.text)
        ai_text = response_data.get("message", {}).get("content", "")

        log.info("✅ SUCCESS: Received response from Ollama.")
        return ai_text.strip()

    except requests.exceptions.RequestException as e:
        log.error(f"❌ ERROR: Could not connect to Ollama. Details: {e}")
        return "I'm having trouble connecting to my analysis engine right now. Please make sure the Ollama application is running on your computer."
    except Exception as e:
        log.error(
            f"❌ ERROR: An unexpected error occurred during AI processing. Details: {e}"
        )
        return "I encountered an unexpected issue while analyzing your data. Please try again."


# --- ADD THIS NEW FUNCTION ---
def _json_default(obj):
    # Handles ObjectId and datetime serialization for JSON
    from bson import ObjectId
    from datetime import datetime
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

async def get_ai_session_summary(session_data: dict) -> str:
    """
    Generates a brief, encouraging summary for a single completed workout session.
    """
    log.info("🤖 AI COACH: Generating end-of-session summary.")
    
    # Use custom default to handle ObjectId and datetime
    session_json = json.dumps(session_data, indent=2, default=_json_default)

    system_prompt = (
        "You are Astra, an expert strength coach. Your client just finished a workout. "
        "Your task is to provide a short (2-3 sentences), encouraging, and insightful summary. "
        "Directly address the user. Mention 1-2 specific positive achievements from the data, like a new PR or consistent volume. "
        "Your tone should be like a proud but professional coach. Use emojis."
    )

    user_prompt = f"Here is the data for the workout I just completed. Please give me a summary.\n\n{session_json}"

    try:
        payload = {
            "model": "gemma3:latest",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        response.raise_for_status()

        response_data = json.loads(response.text)
        summary = response_data.get("message", {}).get("content", "").strip()
        log.info(f"✅ SUCCESS: Generated AI session summary: '{summary[:50]}...'")
        return summary

    except requests.RequestException as e:
        log.error(f"❌ ERROR: Could not connect to Ollama for session summary. Details: {e}")
        return "Couldn't generate an AI summary this time, but great work on the session!"
    except Exception as e:
        log.error(f"❌ ERROR: An unexpected error occurred during summary generation. Details: {e}")
        return "An unexpected error occurred while creating the AI summary."
