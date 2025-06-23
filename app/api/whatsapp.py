# app/api/whatsapp.py
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from app.api.parser import parse_message
from app.db.operations import log_set, get_or_create_daily_log, get_next_exercise_details
from app.core.logging_config import log
from app.api.ai_coach import get_ai_response

router = APIRouter()

# --- NEW HELPER FUNCTION ---
def create_smart_response(long_message: str) -> MessagingResponse:
    """
    Creates a TwiML response, splitting the message into chunks if it's too long.
    """
    twiml_response = MessagingResponse()
    # A safe character limit for a single WhatsApp message
    CHAR_LIMIT = 1500 

    if len(long_message) <= CHAR_LIMIT:
        # Avoid backslash in f-string expression for compatibility
        log.info("📤 OUTGOING (Single): Sending reply: '%s'", long_message.replace('\n', ' '))
        twiml_response.message(long_message)
    else:
        log.warning(f"Message is too long ({len(long_message)} chars). Splitting into chunks.")
        paragraphs = long_message.split('\n\n')
        
        current_chunk = ""
        message_count = 0
        for i, p in enumerate(paragraphs):
            # If adding the next paragraph fits, add it
            if len(current_chunk) + len(p) + 2 <= CHAR_LIMIT:
                current_chunk += p + "\n\n"
            # If the paragraph itself is too long, we have to split it brute-force
            elif len(p) > CHAR_LIMIT:
                log.warning("Paragraph is too long, splitting mid-sentence.")
                # Send whatever we had before
                if current_chunk:
                    twiml_response.message(current_chunk.strip())
                    message_count += 1
                # Split the huge paragraph into smaller chunks
                words = p.split(' ')
                small_chunk = ""
                for word in words:
                    if len(small_chunk) + len(word) + 1 > CHAR_LIMIT:
                        twiml_response.message(small_chunk.strip())
                        message_count += 1
                        small_chunk = ""
                    small_chunk += word + " "
                if small_chunk:
                    twiml_response.message(small_chunk.strip())
                    message_count += 1
                current_chunk = ""
            # Otherwise, the paragraph doesn't fit, so send the current chunk and start a new one
            else:
                if current_chunk:
                    twiml_response.message(current_chunk.strip())
                    message_count += 1
                current_chunk = p + "\n\n"

        # Send any remaining part of the last chunk
        if current_chunk:
            twiml_response.message(current_chunk.strip())
            message_count += 1
            
        log.info(f"📤 OUTGOING (Multi-part): Sent {message_count} separate messages.")

    return twiml_response


@router.post("/whatsapp")
async def whatsapp_webhook(From: str = Form(...), Body: str = Form(...)):
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
        elif parsed_data["error"] == "empty_question":
            response_message = "🤖 Please ask a question after the /ask command. For example:\n`/ask how is my chest progressing?`"
        else:
            response_message = "❌ There was an error in the format of your log. Please check the weight/reps/rpe."
    elif parsed_data["command"] == "log_set":
        num_sets_done = await log_set(user_id=user_phone_number, exercise_name=parsed_data["exercise_name"], exercise_id=parsed_data["exercise_id"], set_log=parsed_data["set_log"])
        target_sets = parsed_data["target_sets"]
        response_message = f"✅ Set {num_sets_done}/{target_sets} for {parsed_data['exercise_name']} logged.\n({parsed_data['set_log'].weight} lbs/kg x {parsed_data['set_log'].reps} reps)"
        if num_sets_done >= target_sets:
            response_message += "\n\nAll sets complete! Type 'next' for the next exercise."
    elif parsed_data["command"] == "get_next_exercise":
        next_exercise_data = await get_next_exercise_details(user_id=user_phone_number)
        if next_exercise_data is not None:
            if next_exercise_data.get("message") == "next_exercise":
                details = next_exercise_data["details"]
                response_message = (
                    f"🔥 Time to work: {details['name']} 🔥\n\n"
                    f"🎯 Target: {details['target']}\n"
                    f"📈 Last Time: {details['last_performance']}\n"
                    f"🏆 Personal Record: {details['personal_record']}\n"
                    f"💪 Suggested Target: {details['target_weight']}"
                )
            else:
                response_message = next_exercise_data.get("message", "No workout information available.")
        else:
            response_message = "No workout information available."
    elif parsed_data["command"] == "ask_ai":
        question = parsed_data["question"]
        ai_response = await get_ai_response(user_id=user_phone_number, user_question=question)
        if not ai_response or not ai_response.strip():
            response_message = "🤖 Sorry, I couldn't generate a response right now. Please try again later."
        else:
            response_message = ai_response
    elif parsed_data["command"] == "ping":
        response_message = "🏓 Pong! The entire pipeline is alive and kicking.\n\nIf this were a real ping, you'd have just lost a life. 😜"
    else:
        response_message = f"✅ Command '{parsed_data['command']}' received. This feature is coming soon!"
    
    # --- THE FIX: Use our new smart response handler ---
    twiml_response = create_smart_response(response_message)
    
    return Response(content=str(twiml_response), media_type="application/xml")
