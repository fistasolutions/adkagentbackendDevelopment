from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

# Load environment variables from .env file
load_dotenv()

# Fetch DB credentials from environment
DB_USER = "postgres"
DB_PASSWORD = "AtdzZ3PTHpfyNMHM"
DB_HOST = "db.dmagxacchospnbmybret.supabase.co"
DB_PORT = "5432"
DB_NAME = "postgres"


# Function to get a DB connection
def get_connection():
    try:
        connection = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
        )
        print("✅ Database connection established successfully!")
        return connection
    except OperationalError as oe:
        print(f"❌ Operational error: {oe}")
        raise
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        raise
