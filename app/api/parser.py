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


async def parse_message(message: str) -> Dict[str, Any] | None:
    message = message.strip()
    log.info(f"🧠 PARSING: Received message for parsing: '{message}'")

    # --- Check for Commands First ---
    # NEW: Check for /ping command
    if message.lower().startswith("/ping"):
        log.info("✅ SUCCESS: Parsed command 'ping'.")
        return {"command": "ping"}
    # NEW: Check for /ask command
    if message.lower().startswith("/ask"):
        question = message[5:].strip()  # Get everything after "/ask "
        if not question:
            return {"error": "empty_question"}
        log.info(f"✅ SUCCESS: Parsed command 'ask_ai' with question: '{question}'.")
        return {"command": "ask_ai", "question": question}

    if message.lower() in ["next", "what's next?", "next exercise"]:
        log.info("✅ SUCCESS: Parsed command 'get_next_exercise'.")
        return {"command": "get_next_exercise"}
    if message.lower() in ["done", "end workout"]:
        log.info("✅ SUCCESS: Parsed command 'end_workout'.")
        return {"command": "end_workout"}

    match = LOG_PATTERN.match(message)
    if not match:
        log.warning("Message does not match command or log pattern.")
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
