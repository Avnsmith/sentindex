"""
Configuration management for Sentindex.

Loads configuration from YAML files and environment variables.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config file (defaults to config.yaml)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self.get('database', {})
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration."""
        return self.get('redis', {})
    
    def get_kafka_config(self) -> Dict[str, Any]:
        """Get Kafka configuration."""
        return self.get('kafka', {})
    
    def get_index_config(self, index_name: str) -> Dict[str, Any]:
        """Get index configuration."""
        indices = self.get('indices', {})
        return indices.get(index_name, {})
    
    def get_data_source_config(self, source_name: str) -> Dict[str, Any]:
        """Get data source configuration."""
        sources = self.get('data_sources', {})
        return sources.get(source_name, {})
    
    def get_sentient_config(self) -> Dict[str, Any]:
        """Get Sentient LLM configuration."""
        return self.get('sentient', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration."""
        return self.get('monitoring', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return self.get('security', {})
    
    def substitute_env_vars(self, value: str) -> str:
        """
        Substitute environment variables in string values.
        
        Args:
            value: String that may contain ${VAR_NAME} patterns
            
        Returns:
            String with environment variables substituted
        """
        if not isinstance(value, str):
            return value
        
        import re
        
        def replace_env_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))
        
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, value)
    
    def get_with_env_substitution(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with environment variable substitution.
        
        Args:
            key: Configuration key
            default: Default value
            
        Returns:
            Configuration value with env vars substituted
        """
        value = self.get(key, default)
        
        if isinstance(value, str):
            return self.substitute_env_vars(value)
        elif isinstance(value, dict):
            return {k: self.substitute_env_vars(v) if isinstance(v, str) else v 
                   for k, v in value.items()}
        elif isinstance(value, list):
            return [self.substitute_env_vars(v) if isinstance(v, str) else v 
                   for v in value]
        
        return value


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config():
    """Reload configuration from file."""
    global _config_instance
    _config_instance = None
    return get_config()


# Environment variable helpers
def get_env_var(key: str, default: str = None, required: bool = False) -> str:
    """
    Get environment variable with validation.
    
    Args:
        key: Environment variable name
        default: Default value
        required: Whether the variable is required
        
    Returns:
        Environment variable value
        
    Raises:
        ValueError: If required variable is not set
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"Required environment variable {key} is not set")
    
    return value


# Common environment variables
REQUIRED_ENV_VARS = [
    "ALPHAVANTAGE_API_KEY",
    "EIA_API_KEY", 
    "SENTIENT_API_KEY",
    "SECRET_KEY"
]


def validate_environment():
    """Validate that all required environment variables are set."""
    missing_vars = []
    
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")


# Example usage
if __name__ == "__main__":
    try:
        config = get_config()
        
        print("Database config:", config.get_database_config())
        print("Index config:", config.get_index_config("gold_silver_oil_crypto"))
        print("Sentient config:", config.get_sentient_config())
        
        # Test environment variable substitution
        test_value = config.substitute_env_vars("${ALPHAVANTAGE_API_KEY}")
        print("Env var substitution test:", test_value)
        
    except Exception as e:
        print(f"Configuration error: {e}")
