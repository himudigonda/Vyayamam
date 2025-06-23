# app/core/models.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId


# This is a helper class to allow Pydantic to work with MongoDB's ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


# --- Models for data stored within documents ---


class SetLog(BaseModel):
    """Represents a single set performed by the user."""

    weight: float
    reps: int
    rpe: Optional[int] = None
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CompletedExercise(BaseModel):
    """Represents all sets performed for a single exercise in a session."""

    exercise_id: PyObjectId  # Reference to the exercise in workout_definitions
    name: str
    sets: List[SetLog] = []
    personal_record_achieved: bool = False


class Readiness(BaseModel):
    """Captures the user's subjective readiness metrics for the day."""

    sleep_hours: Optional[float] = None
    stress_level: Optional[int] = Field(
        None, ge=1, le=10
    )  # Validation: must be between 1 and 10
    soreness: list = []  # Can be a list of sore muscle groups


class WorkoutSession(BaseModel):
    """Contains all data related to a single workout session."""

    status: str = "in-progress"  # "in-progress", "completed", "skipped"
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    session_grade: Optional[str] = None
    ai_summary: Optional[str] = None
    completed_exercises: List[CompletedExercise] = []


# --- Top-level model representing a full document in the `daily_logs` collection ---


class DailyLog(BaseModel):
    """The main document structure for logging daily data."""

    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str  # For now, can be the user's phone number
    date: str  # YYYY-MM-DD format for easy querying
    readiness: Readiness = Field(default_factory=Readiness)
    workout_session: Optional[WorkoutSession] = None

    class Config:
        """Tells Pydantic to allow serializing MongoDB's ObjectId."""

        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
