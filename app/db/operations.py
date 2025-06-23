# app/db/operations.py
import re
from datetime import date
from app.db.database import get_db
from app.core.models import DailyLog, SetLog, WorkoutSession, CompletedExercise, PyObjectId
from app.core.logging_config import log


async def get_or_create_daily_log(user_id: str) -> DailyLog:
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(
        f"💾 DATABASE: Searching for daily log for user '{user_id}' on date '{today_str}'."
    )

    log_data = await db.daily_logs.find_one({"user_id": user_id, "date": today_str})

    if log_data:
        log.info("✅ SUCCESS: Found existing daily log.")
        return DailyLog(**log_data)
    else:
        log.warning(f"Log not found. Creating a new daily log for user '{user_id}'.")
        new_log = DailyLog(user_id=user_id, date=today_str)
        await db.daily_logs.insert_one(new_log.model_dump(by_alias=True))
        log.info("✅ SUCCESS: New daily log created.")
        return new_log


async def find_exercise_in_plan(exercise_query: str) -> dict | None:
    db = get_db()
    query_regex = re.compile(f"^{re.escape(exercise_query)}", re.IGNORECASE)
    log.info(f"\U0001F4BE DATABASE: Searching for exercise matching query: '{exercise_query}'.")

    plan = await db.workout_definitions.find_one(
        {
            "exercises": {
                "$elemMatch": {"$or": [{"name": query_regex}, {"aliases": query_regex}]}
            }
        }
    )

    if not plan:
        log.warning(f"No workout day found containing an exercise matching '{exercise_query}'.")
        return None

    for exercise in plan["exercises"]:
        is_match = False
        if re.match(query_regex, exercise["name"]):
            is_match = True
        else:
            for alias in exercise.get("aliases", []):
                if re.match(query_regex, alias):
                    is_match = True
                    break
        if is_match:
            log.info(f"✅ SUCCESS: Found exercise '{exercise['name']}' within day '{plan['day_name']}'.")
            return exercise

    log.warning(f"Exercise matching '{exercise_query}' not found in any plan (this should be rare).")
    return None


async def log_set(
    user_id: str, exercise_name: str, exercise_id: object, set_log: SetLog
):
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(f"💾 DATABASE: Logging set for '{exercise_name}' for user '{user_id}'.")

    update_result = await db.daily_logs.update_one(
        {"user_id": user_id, "date": today_str, "workout_session": None},
        {"$set": {"workout_session": WorkoutSession().model_dump()}},
    )
    if update_result.modified_count > 0:
        log.info("New workout session created for the day.")

    daily_log = await db.daily_logs.find_one(
        {
            "user_id": user_id,
            "date": today_str,
            "workout_session.completed_exercises.name": exercise_name,
        }
    )

    if daily_log:
        log.info(f"Appending set to existing exercise '{exercise_name}'.")
        await db.daily_logs.update_one(
            {
                "user_id": user_id,
                "date": today_str,
                "workout_session.completed_exercises.name": exercise_name,
            },
            {
                "$push": {
                    "workout_session.completed_exercises.$.sets": set_log.model_dump()
                }
            },
        )
    else:
        log.info(f"First set for new exercise '{exercise_name}'. Creating entry.")
        completed_exercise = CompletedExercise(
            exercise_id=PyObjectId(str(exercise_id)), name=exercise_name, sets=[set_log]
        )
        await db.daily_logs.update_one(
            {"user_id": user_id, "date": today_str},
            {
                "$push": {
                    "workout_session.completed_exercises": completed_exercise.model_dump()
                }
            },
        )

    updated_log = await get_or_create_daily_log(user_id)
    if updated_log.workout_session and updated_log.workout_session.completed_exercises:
        for ex in updated_log.workout_session.completed_exercises:
            if ex.name == exercise_name:
                num_sets = len(ex.sets)
                log.info(
                    f"✅ SUCCESS: Set logged. Total sets for '{exercise_name}' today: {num_sets}."
                )
                return num_sets
    return 0
