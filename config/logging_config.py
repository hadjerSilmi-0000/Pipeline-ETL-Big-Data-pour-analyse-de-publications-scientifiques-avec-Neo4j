import logging
import os

LOG_PATH = "logs"
os.makedirs(LOG_PATH, exist_ok=True)

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # format
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # handler fichier
    file_handler = logging.FileHandler(
        os.path.join(LOG_PATH, f"{name}.log"),
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger