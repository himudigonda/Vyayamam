import os
import sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from bson import ObjectId  # <-- ADD THIS IMPORT

# --- This is a crucial step to allow the script to import from the 'app' directory ---
# We add the parent directory (vyayamam/) to the Python path.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------------------------

# Now we can import from our app's modules
from app.core.config import settings

# Your detailed Push/Pull/Legs workout plan
WORKOUT_PLAN_DATA = [
    {
        "day_of_week": 1,
        "day_name": "Push A",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Smith Machine Incline Press",
                "aliases": ["smith incline", "incline smith press"],
                "primary_muscle_groups": ["Chest", "Shoulders", "Triceps"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "8-12",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Shoulder Press",
                "aliases": ["db shoulder press", "seated dumbbell press"],
                "primary_muscle_groups": ["Shoulders"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "10-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Cable Crossover",
                "aliases": ["cable fly", "crossovers"],
                "primary_muscle_groups": ["Chest"],
                "order": 3,
                "target_sets": 3,
                "target_reps": "12-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Lateral Raises",
                "aliases": ["db lat raises", "side raises"],
                "primary_muscle_groups": ["Shoulders"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Cable Tricep Pushdowns",
                "aliases": ["tricep pushdowns", "rope pushdowns"],
                "primary_muscle_groups": ["Triceps"],
                "order": 5,
                "target_sets": 3,
                "target_reps": "12-15",
            },
        ],
    },
    {
        "day_of_week": 2,
        "day_name": "Pull A",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Lat Pulldowns",
                "aliases": ["lats pulldown"],
                "primary_muscle_groups": ["Back", "Biceps"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "8-12",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Rows",
                "aliases": ["db rows", "single arm row"],
                "primary_muscle_groups": ["Back"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "10-12",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Rowing Machine",
                "aliases": ["rower"],
                "primary_muscle_groups": ["Back", "Legs", "Cardio"],
                "order": 3,
                "target_sets": 1,
                "target_reps": "5 min",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Cable Face Pulls",
                "aliases": ["face pulls"],
                "primary_muscle_groups": ["Shoulders", "Back"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Bicep Curls",
                "aliases": ["db curls", "bicep curls"],
                "primary_muscle_groups": ["Biceps"],
                "order": 5,
                "target_sets": 3,
                "target_reps": "10-15",
            },
        ],
    },
    {
        "day_of_week": 3,
        "day_name": "Legs A",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Leg Press Machine",
                "aliases": ["leg press"],
                "primary_muscle_groups": ["Quads", "Glutes", "Hamstrings"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "10-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell RDLs",
                "aliases": ["rdl", "romanian deadlift"],
                "primary_muscle_groups": ["Hamstrings", "Glutes"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "12-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Kettlebell Goblet Squats",
                "aliases": ["goblet squat", "kb squat"],
                "primary_muscle_groups": ["Quads", "Glutes"],
                "order": 3,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Leg Extensions",
                "aliases": ["quad extensions"],
                "primary_muscle_groups": ["Quads"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Calf Raises",
                "aliases": ["standing calf raises"],
                "primary_muscle_groups": ["Calves"],
                "order": 5,
                "target_sets": 4,
                "target_reps": "15-25",
            },
        ],
    },
    # Thursday, Friday, Saturday plans... (add the rest of the PPL split here for completeness)
    {
        "day_of_week": 4,
        "day_name": "Push B",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Machine Chest Press",
                "aliases": ["chest press machine"],
                "primary_muscle_groups": ["Chest"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "8-12",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Seated Dumbbell Lateral Raises",
                "aliases": ["seated lat raises"],
                "primary_muscle_groups": ["Shoulders"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Smith Machine Shoulder Press",
                "aliases": ["smith shoulder press"],
                "primary_muscle_groups": ["Shoulders"],
                "order": 3,
                "target_sets": 3,
                "target_reps": "10-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Incline Dumbbell Flyes",
                "aliases": ["incline db fly"],
                "primary_muscle_groups": ["Chest"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "12-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Overhead Cable Tricep Extensions",
                "aliases": ["overhead tricep extension"],
                "primary_muscle_groups": ["Triceps"],
                "order": 5,
                "target_sets": 3,
                "target_reps": "12-15",
            },
        ],
    },
    {
        "day_of_week": 5,
        "day_name": "Pull B",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Pull-ups",
                "aliases": ["pullups"],
                "primary_muscle_groups": ["Back", "Biceps"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "To Failure",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Seated Cable Rows",
                "aliases": ["cable row"],
                "primary_muscle_groups": ["Back"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "10-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Pullovers",
                "aliases": ["db pullover"],
                "primary_muscle_groups": ["Back", "Chest"],
                "order": 3,
                "target_sets": 3,
                "target_reps": "12-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Hammer Curls",
                "aliases": ["db hammer curls"],
                "primary_muscle_groups": ["Biceps"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "10-15",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Boxing Bag",
                "aliases": ["heavy bag"],
                "primary_muscle_groups": ["Cardio", "Shoulders"],
                "order": 5,
                "target_sets": 1,
                "target_reps": "5 min",
            },
        ],
    },
    {
        "day_of_week": 6,
        "day_name": "Legs B",
        "exercises": [
            {
                "exercise_id": ObjectId(),
                "name": "Smith Machine Squats",
                "aliases": ["smith squat"],
                "primary_muscle_groups": ["Quads", "Glutes"],
                "order": 1,
                "target_sets": 4,
                "target_reps": "8-12",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Dumbbell Walking Lunges",
                "aliases": ["db lunges"],
                "primary_muscle_groups": ["Quads", "Glutes"],
                "order": 2,
                "target_sets": 3,
                "target_reps": "20 steps",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Hamstring Curls",
                "aliases": ["leg curls"],
                "primary_muscle_groups": ["Hamstrings"],
                "order": 3,
                "target_sets": 3,
                "target_reps": "15-20",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Bulgarian Split Squats",
                "aliases": ["bss", "split squats"],
                "primary_muscle_groups": ["Quads", "Glutes"],
                "order": 4,
                "target_sets": 3,
                "target_reps": "10-12/leg",
            },
            {
                "exercise_id": ObjectId(),
                "name": "Kettlebell Swings",
                "aliases": ["kb swings"],
                "primary_muscle_groups": ["Glutes", "Hamstrings", "Cardio"],
                "order": 5,
                "target_sets": 4,
                "target_reps": "20",
            },
        ],
    },
]


def seed_database():
    """
    Connects to the MongoDB database, clears existing workout definitions,
    and inserts the new, structured workout plan using settings from config.
    """
    print("--- Starting Database Seeding ---")

    try:
        # Now we directly use the imported `settings` object.
        # Pydantic has already loaded and validated everything from the .env file.
        mongo_uri = settings.MONGO_URI
        db_name = settings.DB_NAME
        print(f"Connecting to MongoDB using settings...")
        client = MongoClient(mongo_uri)
        client.admin.command('ismaster')
        print("✅ MongoDB connection successful.")
    except ConnectionFailure as e:
        print(f"🔴 ERROR: Could not connect to MongoDB.")
        print("Please ensure your local MongoDB server or Docker container is running.")
        print(f"Details: {e}")
        return
    except Exception as e:
        print(f"🔴 An unexpected error occurred. Have you created the 'app/core/config.py' file?")
        print(f"Details: {e}")
        return

    db = client[db_name]
    definitions_collection = db.workout_definitions

    # --- Step 1: Clear existing data ---
    print(f"Clearing existing data from '{definitions_collection.name}' collection...")
    result = definitions_collection.delete_many({})
    print(f"Deleted {result.deleted_count} existing workout definitions.")

    # --- Step 2: Insert the new data ---
    print("Inserting new workout plan data...")
    if WORKOUT_PLAN_DATA:
        result = definitions_collection.insert_many(WORKOUT_PLAN_DATA)
        print(f"Successfully inserted {len(result.inserted_ids)} new workout definitions.")
    else:
        print("No data to insert.")

    # --- Step 3: Create indexes for performance ---
    print("Creating index on 'day_of_week' for faster lookups...")
    definitions_collection.create_index("day_of_week")
    print("✅ Index created.")

    client.close()
    print("--- Database Seeding Complete ---")


if __name__ == "__main__":
    seed_database()
