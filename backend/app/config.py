"""
Configuration Management
Unified load configuration from the .env file in the project root directory
"""

import os
from dotenv import load_dotenv

# Load the .env file in the project root directory
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If there is no .env in the root directory, try to load environment variables (for production environment)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON configuration - Disable ASCII escaping, allow Chinese to display directly (instead of \uXXXX format)
    JSON_AS_ASCII = False
    
    # LLM configuration (use OpenAI format uniformly)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    GRAPHITI_API_KEY = os.environ.get('GRAPHITI_API_KEY')
    GRAPHITI_BASE_URL = os.environ.get('GRAPHITI_BASE_URL')
    GRAPHITI_MODEL_NAME = os.environ.get('GRAPHITI_MODEL_NAME')
    SIMULATION_LLM_API_KEY = os.environ.get('SIMULATION_LLM_API_KEY') or GRAPHITI_API_KEY or LLM_API_KEY
    SIMULATION_LLM_BASE_URL = os.environ.get('SIMULATION_LLM_BASE_URL') or GRAPHITI_BASE_URL or LLM_BASE_URL
    SIMULATION_LLM_MODEL_NAME = os.environ.get('SIMULATION_LLM_MODEL_NAME') or GRAPHITI_MODEL_NAME or LLM_MODEL_NAME
    SIMULATION_LLM_TIMEOUT_SECONDS = int(os.environ.get('SIMULATION_LLM_TIMEOUT_SECONDS', '90'))
    SIMULATION_PROFILE_MAX_TOKENS = int(os.environ.get('SIMULATION_PROFILE_MAX_TOKENS', '900'))
    SIMULATION_CONFIG_MAX_TOKENS = int(os.environ.get('SIMULATION_CONFIG_MAX_TOKENS', '2200'))
    REPORT_LLM_API_KEY = os.environ.get('REPORT_LLM_API_KEY') or GRAPHITI_API_KEY or LLM_API_KEY
    REPORT_LLM_BASE_URL = os.environ.get('REPORT_LLM_BASE_URL') or GRAPHITI_BASE_URL or LLM_BASE_URL
    REPORT_LLM_MODEL_NAME = os.environ.get('REPORT_LLM_MODEL_NAME') or GRAPHITI_MODEL_NAME or LLM_MODEL_NAME
    REPORT_LLM_TIMEOUT_SECONDS = int(os.environ.get('REPORT_LLM_TIMEOUT_SECONDS', '120'))
    REPORT_INTERVIEW_MAX_AGENTS = int(os.environ.get('REPORT_INTERVIEW_MAX_AGENTS', '3'))
    REPORT_INTERVIEW_TIMEOUT_SECONDS = int(os.environ.get('REPORT_INTERVIEW_TIMEOUT_SECONDS', '420'))
    REPORT_INTERVIEW_PLATFORM = os.environ.get('REPORT_INTERVIEW_PLATFORM', 'reddit')  # 'reddit', 'twitter', or 'both'
    REPORT_INTERVIEW_MAX_QUESTIONS = int(os.environ.get('REPORT_INTERVIEW_MAX_QUESTIONS', '3'))
    
    # Cloud LLM provider API keys (for model selector)
    NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    KIMI_API_KEY = os.environ.get('KIMI_API_KEY')

    # Zep configuration
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown', 'csv'}
    
    # Text processing configuration
    DEFAULT_CHUNK_SIZE = int(os.environ.get('DEFAULT_CHUNK_SIZE', '500'))
    DEFAULT_CHUNK_OVERLAP = int(os.environ.get('DEFAULT_CHUNK_OVERLAP', '50'))
    
    # OASIS simulation configuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS platform available action configuration
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY not configured")
        return errors
