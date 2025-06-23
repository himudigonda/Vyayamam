# app/api/whatsapp.py
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from app.api.parser import parse_message
from app.db.operations import (
    log_set, 
    get_or_create_daily_log, 
    get_next_exercise_details, 
    log_readiness, 
    grade_and_summarize_session,
    get_todays_exercises
)
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
        # --- NEW: Add new commands to the help message ---
        response_message = "Sorry, I didn't understand that. Please use one of the formats:\n\n*Log a set:*\n`exercise weight reps`\n\n*Commands:*\n`next`\n`/ask [question]`\n`/sleep [hours]`\n`/stress [1-10]`\n`/soreness [area]`"
    elif "error" in parsed_data:
        if parsed_data["error"] == "exercise_not_found":
            response_message = f"❌ Could not find an exercise matching '{parsed_data['query']}'. Please check the name and try again."
        elif parsed_data["error"] == "empty_question":
            response_message = "🤖 Please ask a question after the /ask command. For example:\n`/ask how is my chest progressing?`"
        else:
            response_message = "❌ There was an error in the format of your log. Please check the weight/reps/rpe."
    
    # --- ADD THIS NEW LOGIC BLOCK ---
    elif parsed_data["command"] == "log_readiness":
        metric = parsed_data["metric"]
        value = parsed_data["value"]
        
        await log_readiness(user_id=user_phone_number, metric=metric, value=value)
        
        # Create a user-friendly response
        if metric == "sleep_hours":
            response_message = f"✅ Sleep logged: {value} hours. Sweet dreams! 😴"
        elif metric == "stress_level":
            response_message = f"✅ Stress level logged as {value}/10. Remember to take it easy if you need to. 🙏"
        elif metric == "soreness":
            response_message = f"✅ Soreness in '{value}' logged. Make sure to stretch and recover! 💪"
    # --- END OF NEW BLOCK ---

    # --- NEW: Handle workout state management ---
    elif parsed_data["command"] == "start_workout":
        # Inform user to use /end workout for summary, but keep old logic for now
        response_message = "🔥 Workout started! Let's get to it. Your first exercise is waiting. Type `next` to see it."
    elif parsed_data["command"] == "end_workout":
        result = await grade_and_summarize_session(user_id=user_phone_number)
        if result["status"] == "success":
            response_message = (
                f"🎉 *Workout Complete!* 🎉\n\n"
                f"*> Session Grade: {result['grade']}*\n\n"
                f"*Astra's Summary:*\n_{result['summary']}_\n\n"
                "Amazing work today. Your data has been saved. Time to rest, recover, and refuel! 💪"
            )
        else:
            # This handles the case where there's no workout to end.
            response_message = f"🤔 Hmm, {result['message']}"
    # --- END OF NEW BLOCKS ---

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
    # --- ADD THIS NEW BLOCK after the /help block ---
    elif parsed_data["command"] == "list_exercises":
        exercise_list = await get_todays_exercises()
        if not exercise_list:
            response_message = "Looks like there's no workout scheduled for today. Enjoy your rest day! 🌴"
        else:
            response_message = "📋 *Today's Workout Plan:*\n\n"
            response_message += "\n".join(f"• `{name}`" for name in exercise_list)
            response_message += "\n\n_You can log these with slight variations, I'll do my best to understand!_"
    
    elif parsed_data["command"] == "get_help":
        response_message = (
            "🤖 *Welcome to Vyayamam AI!* Here's what you can do:\n\n"
            "1️⃣ *Log a Workout Set*\n"
            "Use the format: `exercise weight reps`\n"
            "_Example:_\n`smith incline 120 8`\n\n"
            "You can also add optional notes or RPE:\n"
            "`leg press 300 10 rpe 8`\n"
            "`db rows 50 12 notes felt strong`\n\n"
            "2️⃣ *Get Workout Guidance*\n"
            "Type `next` to see your next planned exercise, including your last performance and PR.\n\n"
            "3️⃣ *Manage Your Session*\n"
            "• `/start` - Officially begin your workout session.\n"
            "• `/end` - Finish your session to get a grade and an AI-powered summary.\n\n"
            "4️⃣ *Log Daily Readiness*\n"
            "• `/sleep [hours]` - _e.g., /sleep 7.5_\n"
            "• `/stress [1-10]` - _e.g., /stress 3_\n"
            "• `/soreness [area]` - _e.g., /soreness back_\n\n"
            "5️⃣ *Chat with Your AI Coach*\n"
            "Use `/ask` followed by your question.\n"
            "_Examples:_\n"
            "`/ask how is my squat progressing?`\n"
            "`/ask what should I focus on for my chest?`\n\n"
            "6️⃣ *Check System Status*\n"
            "Type `/ping` to see if the system is online.\n\n"
            "7️⃣ *View Your Dashboard*\n"
            "Don't forget to check the web dashboard for detailed charts and trends!"
        )
    else:
        response_message = f"✅ Command '{parsed_data['command']}' received. This feature is coming soon!"
    
    # --- THE FIX: Use our new smart response handler ---
    twiml_response = create_smart_response(response_message)
    
    return Response(content=str(twiml_response), media_type="application/xml")
