import os
from dotenv import load_dotenv
import mysql.connector

# Load the variables from your local .env file
load_dotenv()

def create_connection():
    """
    Create and return a new MySQL connection using environment variables.
    """
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),        
        port=int(os.environ.get("DB_PORT", 3307)), # Port must be an integer
        user=os.environ.get("DB_USER", "myraaflix"),
        password=os.environ.get("DB_PASSWORD", "PORTFOLIO_MODE_FALLBACK"),
        database=os.environ.get("DB_NAME", "myraaflix"),
        charset='utf8mb4',       
        collation='utf8mb4_general_ci'
    )

# initial global connection (safeguarded for online portfolio deployment)
try:
    connection = create_connection()
except mysql.connector.Error as e:
    # If it fails online, we print it out but don't let it crash the whole server
    print(f"⚠️ Local MySQL connection skipped or unavailable: {e}")
    connection = None