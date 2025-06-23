# app/api/whatsapp.py
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from app.api.parser import parse_message
from app.db.operations import log_set, get_or_create_daily_log
from app.core.logging_config import log

router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
    log.info(f"📥 INCOMING: Received message from {From}")
    log.info(f"📲 MESSAGE: '{Body}'")
    
    user_phone_number = From
    message_body = Body
    
    await get_or_create_daily_log(user_id=user_phone_number)
    parsed_data = await parse_message(message_body)
    
    response_message = ""

    if not parsed_data:
        response_message = "Sorry, I didn't understand that. Please use the format:\n'exercise weight reps [rpe #] [notes ...]'\nOr a command like 'next'."
    elif "error" in parsed_data:
        if parsed_data["error"] == "exercise_not_found":
            response_message = f"❌ Could not find an exercise matching '{parsed_data['query']}'. Please check the name and try again."
        else:
            response_message = "❌ There was an error in the format of your log. Please check the weight/reps/rpe."
    elif parsed_data["command"] == "log_set":
        num_sets_done = await log_set(user_id=user_phone_number, exercise_name=parsed_data["exercise_name"], exercise_id=parsed_data["exercise_id"], set_log=parsed_data["set_log"])
        target_sets = parsed_data["target_sets"]
        response_message = f"✅ Set {num_sets_done}/{target_sets} for {parsed_data['exercise_name']} logged.\n({parsed_data['set_log'].weight} lbs/kg x {parsed_data['set_log'].reps} reps)"
        if num_sets_done >= target_sets:
            response_message += "\n\nAll sets complete! Type 'next' for the next exercise."
    else:
        response_message = f"✅ Command '{parsed_data['command']}' received. This feature is coming soon!"

    safe_response = response_message.replace('\n', ' ')
    log.info(f"📤 OUTGOING: Sending reply: '{safe_response}'")
    twiml_response = MessagingResponse()
    twiml_response.message(response_message)
    
    return Response(content=str(twiml_response), media_type="application/xml")
