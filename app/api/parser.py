# app/api/parser.py

import re
from typing import Dict, Any, Optional
from app.db.operations import find_exercise_in_plan
from app.core.models import SetLog

# Regex to capture exercise logs. It's designed to be flexible.
# It looks for patterns like: {exercise name} {weight} {reps} {optional: rpe #} {optional: notes ...}
LOG_PATTERN = re.compile(
    r"^(?P<exercise_name>.+?)\s+(?P<weight>\d+\.?\d*)\s+(?P<reps>\d+)"
    r"(\s+rpe\s+(?P<rpe>\d+))?(\s+notes\s+(?P<notes>.+))?$",
    re.IGNORECASE,
)


async def parse_message(message: str) -> Dict[str, Any] | None:
    """
    Parses the user's incoming message to determine the intent and extract entities.
    """
    message = message.strip()

    # --- Check for Commands First ---
    if message.lower() in ["next", "what's next?", "next exercise"]:
        return {"command": "get_next_exercise"}
    if message.lower() in ["done", "end workout"]:
        return {"command": "end_workout"}
    # Add more commands here like /status, /sleep, etc.

    # --- Attempt to Parse as a Workout Log ---
    match = LOG_PATTERN.match(message)
    if not match:
        return None  # Could not parse as a command or a log

    data = match.groupdict()
    exercise_query = data["exercise_name"].strip()

    # The parser collaborates with the database to identify the exercise
    exercise_definition = await find_exercise_in_plan(exercise_query)

    if not exercise_definition:
        return {"error": "exercise_not_found", "query": exercise_query}

    try:
        set_log = SetLog(
            weight=float(data["weight"]),
            reps=int(data["reps"]),
            rpe=int(data["rpe"]) if data["rpe"] else None,
            notes=data["notes"].strip() if data["notes"] else None,
        )
    except (ValueError, TypeError):
        return {"error": "invalid_data_format"}

    return {
        "command": "log_set",
        "exercise_name": exercise_definition["name"],
        "exercise_id": exercise_definition["_id"],
        "set_log": set_log,
        "target_sets": exercise_definition["target_sets"],
    }
