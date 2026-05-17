# -*- coding: utf-8 -*-
import os
import time
import logging
from functools import wraps
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "debug.log")

def setup_logger(name=__name__):
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        logger.addHandler(ch)
    
    return logger

logger = setup_logger("knrag")

def timed_log(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        caller = kwargs.pop("_caller", None)
        func_name = func.__name__
        
        logger.debug(f"[{func_name}] Called")
        
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        
        logger.debug(f"[{func_name}] Completed in {elapsed:.2f}s")
        return result
    return wrapper

def log_chunk(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        chunk_info = kwargs.pop("_chunk_info", None)
        if chunk_info:
            snippet = chunk_info[:200].replace("\n", " ")
            logger.debug(f"Chunk snippet: \"{snippet}...\"")
        return func(*args, **kwargs)
    return wrapper

def get_logger():
    return logger