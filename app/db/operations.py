# app/db/operations.py

import re
from datetime import datetime, date
from app.db.database import get_db
from app.core.models import DailyLog, SetLog, WorkoutSession, CompletedExercise


async def get_or_create_daily_log(user_id: str) -> DailyLog:
    """
    Finds the daily log for the current day for a given user.
    If it doesn't exist, a new one is created.
    """
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")

    log_data = await db.daily_logs.find_one({"user_id": user_id, "date": today_str})

    if log_data:
        return DailyLog(**log_data)
    else:
        new_log = DailyLog(user_id=user_id, date=today_str)
        await db.daily_logs.insert_one(new_log.model_dump(by_alias=True))
        return new_log


async def find_exercise_in_plan(exercise_query: str) -> dict | None:
    """
    Finds a specific exercise in the workout definitions based on its name or alias.
    Uses a case-insensitive regex for robust matching.
    """
    db = get_db()
    # Create a regex to find the exercise name at the start of the query, case-insensitive
    # This allows matching "smith press" from a query like "smith press 100 8"
    query_regex = re.compile(f"^{re.escape(exercise_query)}", re.IGNORECASE)

    # Search in both the name and aliases fields
    workout_plan = await db.workout_definitions.find_one(
        {
            "$or": [
                {"exercises.name": {"$regex": query_regex}},
                {"exercises.aliases": {"$regex": query_regex}},
            ]
        }
    )

    if workout_plan:
        for exercise in workout_plan["exercises"]:
            # Check main name
            if re.match(query_regex, exercise["name"]):
                return exercise
            # Check aliases
            for alias in exercise.get("aliases", []):
                if re.match(query_regex, alias):
                    return exercise
    return None


async def log_set(
    user_id: str, exercise_name: str, exercise_id: object, set_log: SetLog
):
    """
    Logs a new set for a user's current daily log.
    This is the most complex operation, using MongoDB's update capabilities.
    """
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")

    # Ensure a workout session exists for today
    await db.daily_logs.update_one(
        {"user_id": user_id, "date": today_str, "workout_session": None},
        {"$set": {"workout_session": WorkoutSession().model_dump()}},
    )

    # Find if this exercise is already being tracked in today's log
    daily_log_data = await db.daily_logs.find_one(
        {
            "user_id": user_id,
            "date": today_str,
            "workout_session.completed_exercises.name": exercise_name,
        }
    )

    if daily_log_data:
        # If exercise exists, just push the new set to its 'sets' array
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
        # If it's the first set for this exercise today, create the entry
        completed_exercise = CompletedExercise(
            exercise_id=exercise_id, name=exercise_name, sets=[set_log]
        )
        await db.daily_logs.update_one(
            {"user_id": user_id, "date": today_str},
            {
                "$push": {
                    "workout_session.completed_exercises": completed_exercise.model_dump()
                }
            },
        )

    # Return the number of sets completed for this exercise today for the response message
    updated_log = await get_or_create_daily_log(user_id)
    for ex in updated_log.workout_session.completed_exercises:
        if ex.name == exercise_name:
            return len(ex.sets)
    return 0
