import os

ENVIRONMENT = os.getenv('ENV_TYPE', 'development')

# Custom Login Configurations
PASSWORD_SALT = os.getenv("PASSWORD_SALT")
TOKEN_SALT = os.getenv("TOKEN_SALT")

# MongoDB Configurations
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "llm-code")

# Redis Configurations
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# S3 Configurations
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")

# LLM / Bedrock Configurations
BEDROCK_API_KEY = os.getenv("BEDROCK_API_KEY")
BEDROCK_BASE_URL = os.getenv("BEDROCK_BASE_URL")
BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "zai.glm-4.7")