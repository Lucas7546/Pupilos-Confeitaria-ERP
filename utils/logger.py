import logging
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "sistema.log")

os.makedirs(LOG_DIR, exist_ok=True)

# =========================================================
# CONFIG LOGGING
# =========================================================

logging.basicConfig(

    filename=LOG_FILE,

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s"
)

# =========================================================
# INFO
# =========================================================

def log_info(msg):

    logging.info(msg)

# =========================================================
# WARNING
# =========================================================

def log_warning(msg):

    logging.warning(msg)

# =========================================================
# ERROR
# =========================================================

def log_erro(msg):

    logging.error(msg)

# =========================================================
# CRITICAL
# =========================================================

def log_critico(msg):

    logging.critical(msg)