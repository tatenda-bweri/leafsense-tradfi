"""Application entry point for Django options analytics platform"""

# Set up the environment for Django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import sys
import argparse
import traceback
from django.core.wsgi import get_wsgi_application
from django.core.management import execute_from_command_line
from app.database.schema import initialize_database
from app.utils.logging_utils import setup_logging, get_logger
from app.etl.run import run_etl

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="LeafSense Options Analytics Platform")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Django command - passes through to Django's management commands
    django_parser = subparsers.add_parser('django', help='Run Django management commands')
    django_parser.add_argument('args', nargs='*', help='Arguments to pass to Django')
    
    # Database initialization command
    subparsers.add_parser('init_db', help='Initialize database schema')
    
    # ETL commands
    etl_parser = subparsers.add_parser('etl', help='ETL operations')
    etl_parser.add_argument('--run', action='store_true', help='Run ETL process once')
    
    # Server command (shortcut for django runserver)
    server_parser = subparsers.add_parser('server', help='Run development server')
    server_parser.add_argument('-p', '--port', type=int, default=8000, help='Port to run server on')
    server_parser.add_argument('-a', '--addr', default='127.0.0.1', help='Address to run server on')
    
    return parser.parse_args()

def main():
    """
    Main function to run the application
    """
    try:
        # Initialize logging
        logger = setup_logging()
        logger.info("Starting LeafSense Options Analytics Platform")
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            args = parse_args()
            
            # Handle commands
            if args.command == 'init_db':
                logger.info("Initializing database...")
                initialize_database()
                logger.info("Database initialized successfully")
                return
            
            elif args.command == 'etl':
                if args.run:
                    logger.info("Running ETL process...")
                    success = run_etl()
                    if success:
                        logger.info("ETL process completed successfully")
                    else:
                        logger.error("ETL process failed")
                        sys.exit(1)
                return
                
            elif args.command == 'server':
                # Use Django's management command directly instead of modifying sys.argv
                from django.core.management.commands.runserver import Command as RunserverCommand
                logger.info(f"Starting development server on {args.addr}:{args.port}")
                # Create and run the command
                cmd = RunserverCommand()
                options = {
                    'addrport': f"{args.addr}:{args.port}",
                    'use_ipv6': False,
                    'use_reloader': True,
                    'use_threading': True,
                    'verbosity': 1,
                    'use_static_handler': True,
                    'insecure_serving': False,
                    'skip_checks': False,  # Add missing required option
                    'pythonpath': None,
                    'no_color': False,
                    'force_color': False,
                    'settings': None,
                    'traceback': False,
                    'noreload': False,
                }
                cmd.handle(**options)
                return
            
            elif args.command == 'django':
                # Replace sys.argv with the Django command arguments
                sys.argv = [sys.argv[0]] + args.args
        
        # Initialize Django application
        application = get_wsgi_application()
        
        # Execute Django command
        execute_from_command_line(sys.argv)
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error in main application: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()