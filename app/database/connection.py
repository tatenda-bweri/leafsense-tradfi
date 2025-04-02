"""Database connection utilities for the options analytics platform"""

import psycopg2
from psycopg2.extras import execute_values
import os
from django.conf import settings
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

def create_db_connection():
    """
    Create and return a connection to TimescaleDB database
    using settings from Django settings or environment variables
    
    Returns:
        Connection object to database
    """
    try:
        # Get DB config from settings
        db_config = settings.DATABASES['default']
        
        # Create connection with these parameters
        connection = psycopg2.connect(
            dbname=db_config['NAME'],
            user=db_config['USER'],
            password=db_config['PASSWORD'],
            host=db_config['HOST'],
            port=db_config['PORT']
        )
        
        # Set autocommit mode to True
        connection.autocommit = True
        
        logger.debug("Database connection established successfully")
        return connection
        
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        raise Exception(f"Failed to connect to database: {str(e)}")

def create_cursor(connection):
    """
    Create and return a cursor from a connection
    
    Args:
        connection: Database connection object
        
    Returns:
        Cursor object for executing queries
    """
    try:
        # Create cursor with dictionary factory
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return cursor
    except psycopg2.Error as e:
        logger.error(f"Error creating cursor: {str(e)}")
        raise Exception(f"Failed to create database cursor: {str(e)}")

def close_connection(connection, cursor=None):
    """
    Safely close database connection and cursor
    
    Args:
        connection: Database connection to close
        cursor: Optional cursor to close
    """
    try:
        # Close cursor if provided
        if cursor is not None:
            cursor.close()
            logger.debug("Database cursor closed")
            
        # Close connection
        if connection is not None:
            connection.close()
            logger.debug("Database connection closed")
            
    except psycopg2.Error as e:
        logger.error(f"Error closing database connection: {str(e)}")