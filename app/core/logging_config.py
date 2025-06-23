# app/core/logging_config.py
import sys
from loguru import logger

# Remove the default handler to have full control
logger.remove()

# Configure a new handler with a custom format and colors
# This format includes timestamp, level, file name, line number, and the message
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# You can also add a file logger for persistence
# logger.add("logs/vyayamam_{time}.log", rotation="1 day", retention="7 days", level="DEBUG")

# Export the configured logger
log = logger
