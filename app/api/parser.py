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
SLEEP_PATTERN = re.compile(r"^/sleep\s+(\d+\.?\d*)$", re.IGNORECASE)
STRESS_PATTERN = re.compile(r"^/stress\s+([1-9]|10)$", re.IGNORECASE)
SORENESS_PATTERN = re.compile(r"^/soreness\s+(.+)$", re.IGNORECASE)

async def parse_message(message: str) -> Dict[str, Any] | None:
    message = message.strip()
    log.info(f"🧠 PARSING: Interpreting message: '{message}'")

    if message.lower() == "/list all":
        log.info("✅ 🧠 PARSED: Command 'list_all_exercises'.")
        return {"command": "list_all_exercises"}
    if message.lower() == "/list":
        log.info("✅ 🧠 PARSED: Command 'list_todays_exercises'.")
        return {"command": "list_todays_exercises"}
    if message.lower() == "/help":
        log.info("✅ 🧠 PARSED: Command 'get_help'.")
        return {"command": "get_help"}
    if message.lower().startswith("/ping"):
        log.info("✅ 🧠 PARSED: Command 'ping'.")
        return {"command": "ping"}
    if message.lower().startswith("/ask"):
        question = message[5:].strip()
        if not question:
            log.error("❌ 🧠 PARSING FAILED: Empty question after /ask command.")
            return {"error": "empty_question"}
        log.info(f"✅ 🧠 PARSED: Command 'ask_ai' with question: '{question}'.")
        return {"command": "ask_ai", "question": question}
    if message.lower() in ["/start workout", "/start"]:
        log.info("✅ 🧠 PARSED: Command 'start_workout'.")
        return {"command": "start_workout"}
    if message.lower() in ["/end workout", "/done", "/end"]:
        log.info("✅ 🧠 PARSED: Command 'end_workout'.")
        return {"command": "end_workout"}
    sleep_match = SLEEP_PATTERN.match(message)
    if sleep_match:
        sleep_hours = float(sleep_match.group(1))
        log.info(f"✅ 🧠 PARSED: Readiness command 'sleep' with value: {sleep_hours}.")
        return {"command": "log_readiness", "metric": "sleep_hours", "value": sleep_hours}
    stress_match = STRESS_PATTERN.match(message)
    if stress_match:
        stress_level = int(stress_match.group(1))
        log.info(f"✅ 🧠 PARSED: Readiness command 'stress' with value: {stress_level}.")
        return {"command": "log_readiness", "metric": "stress_level", "value": stress_level}
    soreness_match = SORENESS_PATTERN.match(message)
    if soreness_match:
        sore_area = soreness_match.group(1).strip()
        log.info(f"✅ 🧠 PARSED: Readiness command 'soreness' with value: '{sore_area}'.")
        return {"command": "log_readiness", "metric": "soreness", "value": sore_area}
    if message.lower() in ["next", "what's next?", "next exercise"]:
        log.info("✅ 🧠 PARSED: Command 'get_next_exercise'.")
        return {"command": "get_next_exercise"}
    if message.lower() in ["done", "end workout"]:
        log.info("✅ 🧠 PARSED: Command 'end_workout'.")
        return {"command": "end_workout"}
    match = LOG_PATTERN.match(message)
    if not match:
        log.warning(f"🧠 PARSING: Message does not match any known command or log pattern.")
        return None
    data = match.groupdict()
    exercise_query = data["exercise_name"].strip()
    exercise_definition = await find_exercise_in_plan(exercise_query)
    if not exercise_definition:
        log.error(f"❌ 🧠 PARSING FAILED: Exercise not found for query '{exercise_query}'.")
        return {"error": "exercise_not_found", "query": exercise_query}
    try:
        set_log = SetLog(
            weight=float(data["weight"]),
            reps=int(data["reps"]),
            rpe=int(data["rpe"]) if data["rpe"] else None,
            notes=data["notes"].strip() if data["notes"] else None,
        )
        log.info(f"✅ 🧠 PARSED: Log set for '{exercise_definition['name']}'.")
        return {
            "command": "log_set",
            "exercise_name": exercise_definition["name"],
            "exercise_id": exercise_definition["exercise_id"],
            "set_log": set_log,
            "target_sets": exercise_definition["target_sets"],
        }
    except (ValueError, TypeError) as e:
        log.error(f"❌ 🧠 PARSING FAILED: Invalid data format for set log. Details: {e}")
        return {"error": "invalid_data_format"}
