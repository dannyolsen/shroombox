import os
import json
import logging
import logging.config
from logging.handlers import RotatingFileHandler

def setup_logging(default_level=logging.INFO, config_path='config/logging_config.json'):
    """Set up logging configuration from a JSON file or with sensible defaults."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Try to load config file
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Update file paths to be absolute
        for handler in config.get('handlers', {}).values():
            if 'filename' in handler:
                handler['filename'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), handler['filename'])
                
        # Apply configuration
        logging.config.dictConfig(config)
        print(f"Loaded logging configuration from {config_path}")
    else:
        # Set up basic configuration
        print(f"Logging config file not found at {config_path}, using defaults")
        
        # Configure root logger
        logging.basicConfig(
            level=default_level,
            format='%(levelname)s: %(message)s'
        )
        
        # Set up file handler for main logger
        logger = logging.getLogger('shroombox')
        logger.setLevel(default_level)
        
        # Remove existing handlers to avoid duplicates
        if logger.handlers:
            logger.handlers.clear()
            
        # Add file handler
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'main.log'),
            maxBytes=1024*1024,  # 1MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(console_handler)
        
        # Make logger not buffer output
        logger.propagate = False

def get_logger(name):
    """Get a logger with the given name."""
    return logging.getLogger(name) 