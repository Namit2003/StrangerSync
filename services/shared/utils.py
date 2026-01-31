"""
Shared utility functions for all microservices
"""
import os
from dotenv import load_dotenv

load_dotenv()

def get_service_config():
    """Get common service configuration"""
    return {
        "database_host": os.getenv("DATABASE_HOST", "localhost"),
        "database_port": os.getenv("DATABASE_PORT", "5432"),
        "database_name": os.getenv("DATABASE_NAME", "strangersync"),
        "database_user": os.getenv("DATABASE_USER", "postgres"),
        "database_password": os.getenv("DATABASE_PASSWORD", "postgres"),
        "redis_host": os.getenv("REDIS_HOST", "localhost"),
        "redis_port": os.getenv("REDIS_PORT", "6379"),
    }

def get_admin_credentials():
    """Get admin credentials from environment"""
    return {
        "username": os.getenv("ADMIN_USERNAME", "admin"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123")
    }
