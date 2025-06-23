from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    A Pydantic model to manage application settings.
    It automatically reads environment variables from a .env file.
    """

    # --- MongoDB Configuration ---
    # The full connection string for your local MongoDB instance.
    MONGO_URI: str

    # The name of the database to use within MongoDB.
    DB_NAME: str

    # --- Twilio Credentials ---
    # Your Twilio Account SID, found on your Twilio console dashboard.
    TWILIO_ACCOUNT_SID: str

    # Your Twilio Auth Token, also from the console. Treat this like a password.
    TWILIO_AUTH_TOKEN: str

    # The Twilio-provided WhatsApp number (e.g., "whatsapp:+14155238886").
    TWILIO_PHONE_NUMBER: str

    # Your personal WhatsApp number, which will receive messages.
    # Must be verified in the Twilio sandbox.
    ADMIN_PHONE_NUMBER: str

    # Pydantic settings configuration.
    # The `model_config` dict tells Pydantic where to find the .env file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Create a single, reusable instance of the Settings class.
# Other parts of our application will import this `settings` object.
settings = Settings()
