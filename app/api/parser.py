# app/api/parser.py
import re
from typing import Dict, Any
from app.db.operations import find_exercise_in_plan
from app.core.models import SetLog
from app.core.logging_config import log

LOG_PATTERN = re.compile(
    r"^(?P<exercise_name>.+?)\s+(?P<weight>\d+\.?\d*)\s+(?P<reps>\d+)(\s+rpe\s+(?P<rpe>\d+))?(\s+notes\s+(?P<notes>.+))?$",
    re.IGNORECASE,
)

# --- NEW: Regex for readiness commands ---
SLEEP_PATTERN = re.compile(r"^/sleep\s+(\d+\.?\d*)$", re.IGNORECASE)
STRESS_PATTERN = re.compile(r"^/stress\s+([1-9]|10)$", re.IGNORECASE) # Validates 1-10
SORENESS_PATTERN = re.compile(r"^/soreness\s+(.+)$", re.IGNORECASE)


async def parse_message(message: str) -> Dict[str, Any] | None:
    message = message.strip()
    log.info(f"\U0001F9E0 PARSING: Received message for parsing: '{message}'")

    # --- Check for Commands First ---
    if message.lower() == "/list":
        log.info("✅ SUCCESS: Parsed command 'list_exercises'.")
        return {"command": "list_exercises"}
        
    if message.lower() == "/help":
        log.info("✅ SUCCESS: Parsed command 'help'.")
        return {"command": "get_help"}

    if message.lower().startswith("/ping"):
        log.info("✅ SUCCESS: Parsed command 'ping'.")
        return {"command": "ping"}
        
    if message.lower().startswith("/ask"):
        question = message[5:].strip()
        if not question:
            return {"error": "empty_question"}
        log.info(f"✅ SUCCESS: Parsed command 'ask_ai' with question: '{question}'.")
        return {"command": "ask_ai", "question": question}

    # --- NEW: Check for workout state commands ---
    if message.lower() in ["/start workout", "/start"]:
        log.info("✅ SUCCESS: Parsed command 'start_workout'.")
        return {"command": "start_workout"}

    if message.lower() in ["/end workout", "/done", "/end"]:
        log.info("✅ SUCCESS: Parsed command 'end_workout'.")
        return {"command": "end_workout"}

    # --- NEW: Check for readiness commands ---
    sleep_match = SLEEP_PATTERN.match(message)
    if sleep_match:
        sleep_hours = float(sleep_match.group(1))
        log.info(f"✅ SUCCESS: Parsed readiness command 'sleep' with value: {sleep_hours}.")
        return {"command": "log_readiness", "metric": "sleep_hours", "value": sleep_hours}
        
    stress_match = STRESS_PATTERN.match(message)
    if stress_match:
        stress_level = int(stress_match.group(1))
        log.info(f"✅ SUCCESS: Parsed readiness command 'stress' with value: {stress_level}.")
        return {"command": "log_readiness", "metric": "stress_level", "value": stress_level}

    soreness_match = SORENESS_PATTERN.match(message)
    if soreness_match:
        sore_area = soreness_match.group(1).strip()
        log.info(f"✅ SUCCESS: Parsed readiness command 'soreness' with value: '{sore_area}'.")
        return {"command": "log_readiness", "metric": "soreness", "value": sore_area}
    
    if message.lower() in ["next", "what's next?", "next exercise"]:
        log.info("✅ SUCCESS: Parsed command 'get_next_exercise'.")
        return {"command": "get_next_exercise"}
        
    if message.lower() in ["done", "end workout"]:
        log.info("✅ SUCCESS: Parsed command 'end_workout'.")
        return {"command": "end_workout"}

    # --- Fallback to workout log parsing ---
    match = LOG_PATTERN.match(message)
    if not match:
        log.warning("Message does not match any command or log pattern.")
        return None

    data = match.groupdict()
    exercise_query = data["exercise_name"].strip()

    exercise_definition = await find_exercise_in_plan(exercise_query)
    if not exercise_definition:
        log.error(f"❌ ERROR: Exercise not found in plan for query '{exercise_query}'.")
        return {"error": "exercise_not_found", "query": exercise_query}

    try:
        set_log = SetLog(
            weight=float(data["weight"]),
            reps=int(data["reps"]),
            rpe=int(data["rpe"]) if data["rpe"] else None,
            notes=data["notes"].strip() if data["notes"] else None,
        )
        log.info(f"✅ SUCCESS: Parsed set log for '{exercise_definition['name']}'.")
        return {
            "command": "log_set",
            "exercise_name": exercise_definition["name"],
            "exercise_id": exercise_definition["exercise_id"],
            "set_log": set_log,
            "target_sets": exercise_definition["target_sets"],
        }
    except (ValueError, TypeError) as e:
        log.error(f"❌ ERROR: Invalid data format for set log. Details: {e}")
        return {"error": "invalid_data_format"}
