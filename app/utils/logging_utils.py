"""Logging utilities for options analytics application"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from django.conf import settings


def get_logger(name):
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    # Create logger with appropriate name
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Set log level from settings
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Configure handlers
    # 1. Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # 2. File handler (if log file is configured)
    log_file = getattr(settings, 'LOG_FILE', None)
    if log_file:
        # Ensure the directory exists
        log_dir = os.path.dirname(log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Create rotating file handler (max 10MB, up to 5 backup files)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(level)
        
        # Format for file logs (more detailed)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(process)d] - %(threadName)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Format for console logs (more concise)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


def setup_logging():
    """
    Setup application-wide logging configuration
    """
    # Configure log directory if needed
    log_dir = getattr(settings, 'LOG_DIR', os.path.join(settings.BASE_DIR, 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    
    # Set default log file path if not explicitly set
    if not hasattr(settings, 'LOG_FILE'):
        setattr(settings, 'LOG_FILE', os.path.join(log_dir, 'options_analytics.log'))
    
    # Set default log level if not explicitly set
    if not hasattr(settings, 'LOG_LEVEL'):
        setattr(settings, 'LOG_LEVEL', 'INFO')
    
    # Get log level from settings
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers to avoid duplicates
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Add console handler to root logger
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Configure main log file
    log_file = getattr(settings, 'LOG_FILE')
    file_handler = TimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=14  # Keep two weeks of logs
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(process)d] - %(threadName)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Configure Django-specific logging
    if 'django' in settings.INSTALLED_APPS:
        # Set specific log level for django
        django_level = getattr(logging, getattr(settings, 'DJANGO_LOG_LEVEL', 'WARNING').upper(), logging.WARNING)
        
        # Django request logger
        django_file = os.path.join(log_dir, 'django_requests.log')
        django_handler = TimedRotatingFileHandler(
            django_file,
            when='midnight',
            interval=1,
            backupCount=7
        )
        django_handler.setLevel(django_level)
        django_handler.setFormatter(file_formatter)
        
        django_logger = logging.getLogger('django.request')
        django_logger.setLevel(django_level)
        django_logger.addHandler(django_handler)
        
        # Django DB logger for SQL queries (usually only in DEBUG mode)
        if settings.DEBUG:
            sql_file = os.path.join(log_dir, 'django_sql.log')
            sql_handler = RotatingFileHandler(
                sql_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=3
            )
            sql_handler.setLevel(logging.DEBUG)
            sql_handler.setFormatter(file_formatter)
            
            sql_logger = logging.getLogger('django.db.backends')
            sql_logger.setLevel(logging.DEBUG)
            sql_logger.addHandler(sql_handler)
    
    # Log that logging has been configured
    logging.info("Logging configured successfully")
    
    return root_logger