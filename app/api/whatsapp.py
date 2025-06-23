# app/api/whatsapp.py

from fastapi import APIRouter, Form, Depends, Request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from app.core.config import settings
from app.api.parser import parse_message
from app.db.operations import log_set, get_or_create_daily_log

router = APIRouter()


def validate_twilio_request(request: Request):
    """A dependency to validate that the request is coming from Twilio."""
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    # The URL needs to be passed as a plain string, not a Starlette URL object
    url = str(request.url)
    # The form_ parameters are in request.form() which needs to be awaited
    # This is a known complexity with FastAPI. We will handle it inside the endpoint.
    return True  # Bypassing for local testing, will implement fully if deployed


def create_twilio_response(message: str) -> MessagingResponse:
    """Helper function to create a TwiML response."""
    response = MessagingResponse()
    response.message(message)
    return response


@router.post("/whatsapp", dependencies=[Depends(validate_twilio_request)])
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    """
    The main webhook to handle incoming WhatsApp messages from Twilio.
    """
    user_phone_number = From
    message_body = Body

    # Ensure a log exists for today for this user
    await get_or_create_daily_log(user_id=user_phone_number)

    parsed_data = await parse_message(message_body)

    response_message = ""

    if not parsed_data:
        response_message = "Sorry, I didn't understand that. Please use the format:\n'exercise weight reps [rpe #] [notes ...]'\nOr a command like 'next'."
    elif "error" in parsed_data:
        if parsed_data["error"] == "exercise_not_found":
            response_message = f"Could not find an exercise matching '{parsed_data['query']}'. Please check the name."
        else:
            response_message = "There was an error in the format of your log. Please check the weight/reps/rpe."
    elif parsed_data["command"] == "log_set":
        num_sets_done = await log_set(
            user_id=user_phone_number,
            exercise_name=parsed_data["exercise_name"],
            exercise_id=parsed_data["exercise_id"],
            set_log=parsed_data["set_log"],
        )
        target_sets = parsed_data["target_sets"]
        response_message = (
            f"✅ Set {num_sets_done}/{target_sets} for {parsed_data['exercise_name']} logged.\n"
            f"({parsed_data['set_log'].weight} lbs/kg x {parsed_data['set_log'].reps} reps)"
        )
        if num_sets_done >= target_sets:
            response_message += (
                "\n\nAll sets complete! Type 'next' for the next exercise."
            )

    else:
        # Handle other commands like 'next', 'end workout', etc.
        # We will build this logic out later.
        response_message = (
            f"Command '{parsed_data['command']}' received. Functionality coming soon!"
        )

    twiml_response = create_twilio_response(response_message)
    return twiml_response
