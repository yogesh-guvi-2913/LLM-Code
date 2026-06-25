import os

ENVIRONMENT = os.getenv('ENV_TYPE', 'development')

# Custom Login Configurations
PASSWORD_SALT = os.getenv("PASSWORD_SALT")
TOKEN_SALT = os.getenv("TOKEN_SALT")

# PostgreSQL Configurations
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT"))
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
REPORT_DB = os.getenv("REPORT_DB")
COMBINE_DB = os.getenv('COMBINE_DB', 'hackathon-platform-combineDb')
CHAT_DB = os.getenv('CHAT_DB', 'hackathon-platform-chats')

# Redis Configurations
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))

# S3 Configurations
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")