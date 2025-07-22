import logging
import os
from datetime import datetime
import codecs # Import codecs for explicit encoding

# Define log file path relative to the project root
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True) # Ensure the logs directory exists

# Define log file name with current date
log_file_name = datetime.now().strftime('ai_news_agent_%Y-%m-%d.log')
LOG_FILE_PATH = os.path.join(LOG_DIR, log_file_name)

def setup_logging():
    """
    Sets up a centralized logging configuration for the application.
    Logs to console and a daily file.
    """
    # Create a logger
    logger = logging.getLogger('ai_news_agent')
    logger.setLevel(logging.INFO) # Set default logging level

    # Prevent adding multiple handlers if function is called multiple times
    if not logger.handlers:
        # Console handler
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        # Fix for UnicodeEncodeError on Windows: specify encoding for console
        if sys.stdout.encoding != 'UTF-8': # Check if stdout is already UTF-8 (e.g., in some modern terminals)
             c_handler.setStream(codecs.getwriter("utf-8")(sys.stdout.buffer))
        logger.addHandler(c_handler)

        # File handler
        # Fix for UnicodeEncodeError in file: specify encoding for FileHandler
        f_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8') # <--- Add encoding='utf-8' here
        f_handler.setLevel(logging.DEBUG) # Log more verbosely to file
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    return logger

# Initialize logger once
logger = setup_logging()

# No need to run __main__ block of utils.py if it's already running through main.py/streamlit_app.py
# Example usage:
# if __name__ == "__main__":
#     logger.info("This is an informational message.")
#     logger.warning("This is a warning message.")
#     logger.error("This is an error message.")
#     logger.debug("This is a debug message, only in file.")
#
#     module_logger = logging.getLogger('ai_news_agent.research_agent')
#     module_logger.info("Research agent started gathering data.")