# app/db/operations.py
import re
from datetime import date, timedelta, datetime
from app.db.database import get_db
from app.core.models import DailyLog, SetLog, WorkoutSession, CompletedExercise, PyObjectId
from app.core.logging_config import log
from thefuzz import process
from typing import Any, Dict


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


# --- REPLACE the existing `find_exercise_in_plan` function with this new, more flexible version ---
async def find_exercise_in_plan(exercise_query: str) -> Dict[str, Any] | None:
    """
    Finds the best matching exercise from ALL plans using fuzzy string matching,
    making the logger flexible for any day.
    """
    db = get_db()
    log.info(f"🧠 FUZZY SEARCH: Searching for exercise matching '{exercise_query}' across ALL plans.")
    
    # --- THE FIX: Instead of finding one plan, find ALL plans ---
    plans_cursor = db.workout_definitions.find({})
    all_plans = await plans_cursor.to_list(length=10) # 10 is plenty for our 7-day plans
    
    if not all_plans:
        log.warning(f"No workout definitions found in the database at all.")
        return None

    # Create a list of all possible names and aliases from every plan
    choices = {}
    for plan in all_plans:
        for exercise in plan.get("exercises", []):
            # The official name is a choice
            choices[exercise["name"]] = exercise
            # All aliases are also choices
            for alias in exercise.get("aliases", []):
                choices[alias] = exercise
                
    # Use process.extractOne to find the best match from the master list
    best_match = process.extractOne(exercise_query, choices.keys())
    
    # We can be slightly more confident now that we're searching everything.
    if best_match and best_match[1] >= 85:
        found_string = best_match[0]
        score = best_match[1]
        matched_exercise = choices[found_string]
        log.info(f"✅ SUCCESS: Fuzzy match found! '{exercise_query}' -> '{matched_exercise['name']}' with score {score}.")
        return matched_exercise
    
    log.warning(f"❌ No confident exercise match found for '{exercise_query}'. Best guess was '{best_match[0]}' with score {best_match[1]}'.")
    return None


async def log_set(
    user_id: str, exercise_name: str, exercise_id: object, set_log: SetLog
):
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(f"\U0001F4BE DATABASE: Logging set for '{exercise_name}' for user '{user_id}'.")

    # --- Section 1: Create session if it doesn't exist ---
    update_result = await db.daily_logs.update_one(
        {"user_id": user_id, "date": today_str, "workout_session": None},
        {"$set": {"workout_session": WorkoutSession().model_dump()}},
    )
    if update_result.modified_count > 0:
        log.info("New workout session created for the day.")

    # --- Section 2: Check if this is the first set for this exercise today ---
    daily_log = await db.daily_logs.find_one(
        {
            "user_id": user_id,
            "date": today_str,
            "workout_session.completed_exercises.name": exercise_name,
        }
    )

    # --- Section 3: Add the set to the database ---
    if daily_log:
        # Append set to existing exercise entry for today
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
        # First set for this exercise today, create a new entry in the list
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

    # --- NEW: Section 4: Check for and flag new Personal Records ---
    # Find the all-time max weight for this exercise, EXCLUDING today's log
    pipeline = [
        {"$match": {"user_id": user_id, "date": {"$ne": today_str}}},
        {"$unwind": "$workout_session.completed_exercises"},
        {"$match": {"workout_session.completed_exercises.exercise_id": PyObjectId(str(exercise_id))}},
        {"$unwind": "$workout_session.completed_exercises.sets"},
        {"$group": {"_id": None, "max_weight": {"$max": "$workout_session.completed_exercises.sets.weight"}}}
    ]
    pr_cursor = db.daily_logs.aggregate(pipeline)
    pr_result = await pr_cursor.to_list(length=1)
    
    previous_pr = pr_result[0]['max_weight'] if pr_result else 0
    log.info(f"Checking PR for {exercise_name}. Current set: {set_log.weight}. Previous PR: {previous_pr}")

    if set_log.weight > previous_pr:
        log.info(f"\U0001F3C6 NEW PERSONAL RECORD ACHIEVED FOR {exercise_name}! Previous: {previous_pr}, New: {set_log.weight}")
        # Update the flag for this exercise in today's session
        await db.daily_logs.update_one(
            {"user_id": user_id, "date": today_str, "workout_session.completed_exercises.name": exercise_name},
            {"$set": {"workout_session.completed_exercises.$.personal_record_achieved": True}}
        )

    # --- Section 5: Return the number of sets completed today ---
    updated_log_data = await db.daily_logs.find_one({"user_id": user_id, "date": today_str})
    if not updated_log_data or not isinstance(updated_log_data, dict):
        return 0
    updated_log = DailyLog(**updated_log_data)
    if updated_log.workout_session:
        for ex in updated_log.workout_session.completed_exercises:
            if ex.name == exercise_name:
                num_sets = len(ex.sets)
                log.info(f"✅ SUCCESS: Set logged. Total sets for '{exercise_name}' today: {num_sets}.")
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

async def update_workout_status(user_id: str, status: str) -> dict:
    """
    Updates the status of a workout session (e.g., starts or completes it).
    """
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(f"💾 DATABASE: Updating workout status to '{status}' for user '{user_id}'.")
    
    # Ensure the daily log exists
    daily_log = await get_or_create_daily_log(user_id)
    
    if status == "started":
        # If a session already exists, do nothing but confirm. Otherwise, create it.
        if daily_log.workout_session:
            log.info("Workout session already in progress.")
            return {"status": "success", "message": "Workout already in progress."}
        
        update_op = {"$set": {"workout_session": WorkoutSession().model_dump()}}
        result = await db.daily_logs.update_one(
            {"user_id": user_id, "date": today_str}, update_op
        )
        if result.modified_count > 0:
            return {"status": "success", "message": "Workout started."}

    elif status == "completed":
        # Can only complete a session that exists
        if not daily_log.workout_session:
            return {"status": "error", "message": "No workout in progress to end."}
            
        update_op = {
            "$set": {
                "workout_session.status": "completed",
                "workout_session.end_time": datetime.utcnow(),
            }
        }
        result = await db.daily_logs.update_one(
            {"user_id": user_id, "date": today_str}, update_op
        )
        if result.modified_count > 0:
            return {"status": "success", "message": "Workout completed."}
        else:
            # This might happen if user types /end twice
            return {"status": "success", "message": "Workout was already marked as complete."}

    return {"status": "error", "message": "Invalid status update."}

# --- MODIFY THIS FUNCTION ---
async def grade_and_summarize_session(user_id: str) -> dict:
    """
    Grades the workout, gets an AI summary, and finalizes the session in the DB.
    """
    # --- ADD THE IMPORT HERE, INSIDE THE FUNCTION ---
    from app.api.ai_coach import get_ai_session_summary

    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    log.info(f"\U0001F4CA GRADING: Starting session analysis for user '{user_id}'.")

    # 1. Fetch data
    daily_log_data = await db.daily_logs.find_one({"user_id": user_id, "date": today_str})
    if not daily_log_data or not daily_log_data.get("workout_session"):
        return {"status": "error", "message": "No workout in progress to grade."}
    
    daily_log = DailyLog(**daily_log_data)
    session = daily_log.workout_session
    if not session or not getattr(session, 'completed_exercises', None):
        return {"status": "error", "message": "No completed exercises to grade."}

    today_weekday = datetime.strptime(today_str, "%Y-%m-%d").weekday() + 1
    plan = await db.workout_definitions.find_one({"day_of_week": today_weekday})

    # 2. Grade the session
    grade = "N/A"
    if plan and plan.get("exercises"):
        plan_exercises = {ex["name"] for ex in plan["exercises"]}
        completed_exercises = {ex.name for ex in session.completed_exercises}
        adherence = len(completed_exercises.intersection(plan_exercises)) / len(plan_exercises) if plan_exercises else 0
        pr_count = sum(1 for ex in session.completed_exercises if hasattr(ex, 'personal_record_achieved') and ex.personal_record_achieved)

        if adherence >= 0.9:
            grade = "A" if pr_count == 0 else "A+"
        elif adherence >= 0.7:
            grade = "B"
        elif adherence >= 0.5:
            grade = "C"
        elif adherence > 0:
            grade = "D"
        else:
            grade = "F"
        log.info(f"Calculated Grade: {grade} (Adherence: {adherence:.2f}, PRs: {pr_count})")
    else:
        log.warning("No workout plan for today. Cannot calculate a grade.")

    # 3. Get AI summary
    if hasattr(session, 'model_dump'):
        session_dict_for_ai = session.model_dump(exclude={"status", "start_time", "end_time"})
    else:
        # fallback: convert to dict, remove keys if present
        session_dict_for_ai = dict(session)
        for k in ["status", "start_time", "end_time"]:
            session_dict_for_ai.pop(k, None)
    ai_summary = await get_ai_session_summary(session_dict_for_ai)

    # 4. Update database
    update_op = {
        "$set": {
            "workout_session.status": "completed",
            "workout_session.end_time": datetime.utcnow(),
            "workout_session.session_grade": grade,
            "workout_session.ai_summary": ai_summary,
        }
    }
    await db.daily_logs.update_one({"_id": daily_log.id}, update_op)
    log.info("\u2705 SUCCESS: Session finalized in DB with grade and AI summary.")

    return {"status": "success", "grade": grade, "summary": ai_summary}

# --- ADD THIS NEW FUNCTION ---
async def get_todays_exercises() -> list[str]:
    """
    Retrieves a list of official exercise names for the current day's workout plan.
    """
    db = get_db()
    today_weekday = date.today().weekday() + 1
    log.info(f"💾 DATABASE: Fetching exercise list for weekday {today_weekday}.")
    
    plan = await db.workout_definitions.find_one({"day_of_week": today_weekday})
    
    if not plan or not plan.get("exercises"):
        return []
        
    # Return a sorted list of the official names
    exercise_names = sorted([ex["name"] for ex in plan["exercises"]], key=lambda name: [ex for ex in plan["exercises"] if ex["name"] == name][0]["order"])
    return exercise_names

# --- ADD THIS NEW FUNCTION at the end of the file ---
async def get_all_exercises() -> list[str]:
    """
    Retrieves a list of all unique, loggable exercise names from all workout plans.
    """
    db = get_db()
    log.info("💾 DATABASE: Fetching a list of ALL exercises from the workout definitions.")
    all_plans = await db.workout_definitions.find({}).to_list(length=10)  # Get all 7 day plans
    unique_exercise_names = set()
    for plan in all_plans:
        for exercise in plan.get("exercises", []):
            unique_exercise_names.add(exercise["name"])
    # Return a sorted list for clean presentation
    return sorted(list(unique_exercise_names))
