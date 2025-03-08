import os
import logging
import asyncio
from typing import Dict, Any, Optional
from utils import logging_setup

logger = logging_setup.get_logger('shroombox.env')

class EnvManager:
    """Manages reading and writing to .env file."""
    
    def __init__(self, env_path: str = None):
        """Initialize the environment variables manager.
        
        Args:
            env_path: Path to the .env file. If None, uses default path.
        """
        if env_path is None:
            # Use path relative to the project root
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.env_path = os.path.join(script_dir, '.env')
        else:
            self.env_path = env_path
            
        logger.info(f"Environment manager initialized with path: {self.env_path}")
        
        # Lock for thread-safe file operations
        self._file_lock = asyncio.Lock()
    
    async def load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from the .env file.
        
        Returns:
            Dict containing the environment variables
        """
        try:
            async with self._file_lock:
                logger.debug(f"Loading environment variables from: {self.env_path}")
                
                # Check if file exists
                if not os.path.exists(self.env_path):
                    logger.warning(f".env file not found at: {self.env_path}")
                    return {}
                
                env_vars = {}
                with open(self.env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        
                        # Parse key-value pairs
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
                
                # Mask sensitive values in logs
                masked_vars = {k: '********' if 'password' in k.lower() or 'token' in k.lower() else v 
                              for k, v in env_vars.items()}
                logger.debug(f"Loaded environment variables: {masked_vars}")
                
                return env_vars
        except Exception as e:
            logger.error(f"Error loading environment variables: {e}")
            return {}
    
    async def save_env_vars(self, env_vars: Dict[str, str]) -> bool:
        """Save environment variables to the .env file.
        
        Args:
            env_vars: Dict containing the environment variables to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with self._file_lock:
                logger.info(f"Saving environment variables to: {self.env_path}")
                
                # Create a backup of the file first if it exists
                if os.path.exists(self.env_path):
                    backup_path = f"{self.env_path}.bak"
                    try:
                        with open(self.env_path, 'r') as src:
                            with open(backup_path, 'w') as dst:
                                dst.write(src.read())
                        logger.info(f"Created backup at {backup_path}")
                    except Exception as e:
                        logger.warning(f"Failed to create backup: {e}")
                
                # Get existing comments and empty lines to preserve them
                existing_comments = []
                existing_keys = set()
                
                if os.path.exists(self.env_path):
                    with open(self.env_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                existing_comments.append(line)
                            elif '=' in line:
                                key = line.split('=', 1)[0].strip()
                                existing_keys.add(key)
                
                # Write to a temporary file first
                temp_path = f"{self.env_path}.tmp"
                with open(temp_path, 'w') as f:
                    # Write existing comments
                    for comment in existing_comments:
                        f.write(f"{comment}\n")
                    
                    # Write environment variables
                    for key, value in env_vars.items():
                        f.write(f"{key}={value}\n")
                
                # Rename the temporary file to the actual .env file
                os.replace(temp_path, self.env_path)
                
                # Mask sensitive values in logs
                masked_vars = {k: '********' if 'password' in k.lower() or 'token' in k.lower() else v 
                              for k, v in env_vars.items()}
                logger.info(f"Successfully saved environment variables: {masked_vars}")
                
                return True
        except Exception as e:
            logger.error(f"Error saving environment variables: {e}")
            return False
    
    async def update_env_vars(self, updates: Dict[str, str]) -> bool:
        """Update specific environment variables while preserving the rest.
        
        Args:
            updates: Dict containing the environment variables to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Load current environment variables
            current_env_vars = await self.load_env_vars()
            
            # Update with new values
            current_env_vars.update(updates)
            
            # Save updated environment variables
            return await self.save_env_vars(current_env_vars)
        except Exception as e:
            logger.error(f"Error updating environment variables: {e}")
            return False
    
    async def get_env_var(self, key: str) -> Optional[str]:
        """Get a specific environment variable.
        
        Args:
            key: The environment variable key
            
        Returns:
            str: The environment variable value, or None if not found
        """
        env_vars = await self.load_env_vars()
        return env_vars.get(key)
    
    async def set_env_var(self, key: str, value: str) -> bool:
        """Set a specific environment variable.
        
        Args:
            key: The environment variable key
            value: The environment variable value
            
        Returns:
            bool: True if successful, False otherwise
        """
        return await self.update_env_vars({key: value})
    
    async def env_file_exists(self) -> bool:
        """Check if the .env file exists.
        
        Returns:
            bool: True if the file exists, False otherwise
        """
        return os.path.exists(self.env_path)

# Create a singleton instance
env_manager = EnvManager() 