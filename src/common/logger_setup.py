import logging

def setup_logger(name, log_file, level=logging.INFO):
    """Sets up a logger with the specified name, log file, and level."""

    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger