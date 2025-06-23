# app/db/operations.py
import re
from datetime import date, timedelta
from app.db.database import get_db
from app.core.models import DailyLog, SetLog, WorkoutSession, CompletedExercise, PyObjectId
from app.core.logging_config import log
from typing import Any 


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


async def get_next_exercise_details(user_id: str) -> dict | None:
    """
    Determines the next exercise for the user based on today's plan and progress.
    Fetches historical data for coaching context.
    """
    db = get_db()
    today_weekday = date.today().weekday() + 1  # Monday is 1, Sunday is 7

    log.info(f"🧠 COACHING: Getting next exercise for user '{user_id}' on weekday {today_weekday}.")

    # 1. Get today's workout plan
    todays_plan = await db.workout_definitions.find_one({"day_of_week": today_weekday})
    if not todays_plan or not todays_plan.get("exercises"):
        log.warning("No workout plan found for today.")
        return {"message": "No workout scheduled for today. Enjoy your rest!"}

    # 2. Get today's progress
    daily_log = await get_or_create_daily_log(user_id)
    completed_exercises_today = daily_log.workout_session.completed_exercises if daily_log.workout_session else []
    
    last_completed_order = 0
    if completed_exercises_today:
        completed_names = {ex.name for ex in completed_exercises_today}
        # Find the highest 'order' number from the plan that has been completed
        for ex_def in todays_plan["exercises"]:
            if ex_def["name"] in completed_names and ex_def["order"] > last_completed_order:
                last_completed_order = ex_def["order"]
    
    log.info(f"Last completed exercise order was {last_completed_order}.")

    # 3. Determine the next exercise
    next_exercise_def = None
    for ex_def in sorted(todays_plan["exercises"], key=lambda x: x["order"]):
        if ex_def["order"] > last_completed_order:
            next_exercise_def = ex_def
            break
            
    if not next_exercise_def:
        log.info("✅ SUCCESS: All exercises for today are complete.")
        return {"message": "🎉 Workout complete! You've finished all exercises for today. Great work!"}

    log.info(f"Next exercise determined: '{next_exercise_def['name']}'.")
    exercise_id = next_exercise_def["exercise_id"]

    # 4. Find last session's stats for this exercise
    last_session = await db.daily_logs.find(
        {"user_id": user_id, "workout_session.completed_exercises.exercise_id": exercise_id},
        sort=[("date", -1)],
        limit=1
    ).to_list(1)

    last_performance = "No previous data."
    if last_session:
        for ex in last_session[0]["workout_session"]["completed_exercises"]:
            if ex["exercise_id"] == exercise_id and ex["sets"]:
                last_set = ex["sets"][-1] # Get the last set
                last_performance = f"{last_set['weight']} lbs/kg x {last_set['reps']} reps"
                break
    
    # 5. Find all-time PR for this exercise
    pipeline = [
        {"$match": {"user_id": user_id, "workout_session.completed_exercises.exercise_id": exercise_id}},
        {"$unwind": "$workout_session.completed_exercises"},
        {"$match": {"workout_session.completed_exercises.exercise_id": exercise_id}},
        {"$unwind": "$workout_session.completed_exercises.sets"},
        {"$group": {"_id": None, "pr_weight": {"$max": "$workout_session.completed_exercises.sets.weight"}}}
    ]
    pr_result = await db.daily_logs.aggregate(pipeline).to_list(1)
    
    personal_record = "No PR set yet."
    target_weight = "Set a baseline!"
    pr_weight = 0
    if pr_result:
        pr_weight = pr_result[0]['pr_weight']
        personal_record = f"{pr_weight} lbs/kg"
        target_weight = f"{pr_weight + 2.5} lbs/kg (Progressive Overload)"

    return {
        "message": "next_exercise",
        "details": {
            "name": next_exercise_def["name"],
            "target": f"{next_exercise_def['target_sets']} sets of {next_exercise_def['target_reps']} reps",
            "last_performance": last_performance,
            "personal_record": personal_record,
            "target_weight": target_weight
        }
    }


# --- AI Coach Integration ---
async def get_recent_workouts_summary(user_id: str, limit: int = 5) -> list:
    """
    Retrieves a summary of the most recent workout sessions for a user.
    """
    db = get_db()
    log.info(f"💾 DATABASE: Fetching summary of last {limit} workouts for user '{user_id}'.")
    
    pipeline = [
        {"$match": {"user_id": user_id, "workout_session": {"$ne": None}}},
        {"$sort": {"date": -1}},
        {"$limit": limit},
        # Project only the necessary fields to keep the payload small
        {
            "$project": {
                "_id": 0,
                "date": 1,
                "workout_session.status": 1,
                "workout_session.completed_exercises.name": 1,
                "workout_session.completed_exercises.sets.weight": 1,
                "workout_session.completed_exercises.sets.reps": 1,
                "workout_session.completed_exercises.sets.rpe": 1
            }
        }
    ]
    
    recent_logs = await db.daily_logs.aggregate(pipeline).to_list(length=limit)
    log.info(f"✅ SUCCESS: Found {len(recent_logs)} recent workout logs.")
    return recent_logs


async def log_readiness(user_id: str, metric: str, value: Any):
    """
    Logs a subjective readiness metric (sleep, stress, or soreness) for the user.
    """
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(f"\U0001F4BE DATABASE: Logging readiness metric '{metric}' with value '{value}' for user '{user_id}'.")
    
    # Ensure the daily log exists
    await get_or_create_daily_log(user_id)
    
    update_doc = {}
    # Soreness is a list, so we push to it. Others are simple sets.
    if metric == "soreness":
        update_doc["$push"] = {"readiness.soreness": value}
    else:
        # e.g., "readiness.sleep_hours" or "readiness.stress_level"
        update_doc["$set"] = {f"readiness.{metric}": value}

    result = await db.daily_logs.update_one(
        {"user_id": user_id, "date": today_str},
        update_doc,
        upsert=False # We don't upsert because get_or_create handles creation
    )
    
    if result.modified_count > 0:
        log.info("✅ SUCCESS: Readiness data updated in the daily log.")
    else:
        log.warning("Could not update readiness data. The daily log might not exist or the value is the same.")
