import os
from dotenv import load_dotenv
import mysql.connector

# Load the variables from your local .env file
load_dotenv()

def create_connection():
    """
    Create and return a new MySQL connection using environment variables.
    """
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", 3307))
    user = os.environ.get("DB_USER", "myraaflix")
    
    # Safely check for either DB_PASSWORD or DB_PASS
    pwd = os.environ.get("DB_PASSWORD") or os.environ.get("DB_PASS", "PORTFOLIO_MODE_FALLBACK")
    db_name = os.environ.get("DB_NAME", "myraaflix")

    print("\n" + "="*50)
    print("🔍 DB CONNECTION DIAGNOSTICS")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   User: {user}")
    print(f"   Database: {db_name}")
    print(f"   Password Provided: {'YES' if pwd != 'PORTFOLIO_MODE_FALLBACK' else 'NO (Fallback active)'}")
    print("="*50 + "\n")

    return mysql.connector.connect(
        host=host,        
        port=port,
        user=user,
        password=pwd,
        database=db_name,
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