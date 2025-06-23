# app/api/security.py

from fastapi import Request, HTTPException
from twilio.request_validator import RequestValidator
from app.core.config import settings
from app.core.logging_config import log

# Initialize the validator once with your Twilio Auth Token
validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)

async def validate_twilio_request(request: Request):
    """
    A FastAPI dependency to validate that a request is genuinely from Twilio.
    """
    try:
        # Get the full URL of the request, including query parameters
        url = str(request.url)
        
        # Twilio sends form data, so we need to parse it to validate
        form_data = await request.form()
        
        # Get the signature from the request headers
        twilio_signature = request.headers.get("X-Twilio-Signature")
        
        if not twilio_signature:
            log.error("🔒 SECURITY: Request rejected. Missing X-Twilio-Signature header.")
            raise HTTPException(status_code=400, detail="Missing Twilio signature.")

        # Use the validator to check if the request is valid
        if not validator.validate(url, dict(form_data), twilio_signature):
            client_ip = getattr(request.client, 'host', 'unknown')
            log.error(f"🔒 SECURITY: Invalid Twilio signature. Request from '{client_ip}' rejected.")
            raise HTTPException(status_code=403, detail="Invalid Twilio signature.")
        
        log.info("✅ 🔒 SECURITY: Twilio request signature validated successfully.")
        
    except Exception as e:
        log.error(f"❌ 🔒 SECURITY: An unexpected error occurred during Twilio validation: {e}")
        raise HTTPException(status_code=500, detail="Error during request validation.")

    return True # If validation succeeds, the request can proceed
