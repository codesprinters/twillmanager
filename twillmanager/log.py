# encoding: utf-8

from __future__ import absolute_import


import multiprocessing
import logging
import logging.handlers

logger = multiprocessing.get_logger()

def configure(config):
    logger.setLevel(logging.INFO)
    
    filename = config.get('log.worker_file', None)

    if filename:
        handler = logging.handlers.RotatingFileHandler(filename)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        




