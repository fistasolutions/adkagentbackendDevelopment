from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError

# Load environment variables from .env file
load_dotenv()

# Database connection string
DB_CONNECTION_STRING = "postgresql://postgres.dmagxacchospnbmybret:AtdzZ3PTHpfyNMHM@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

# Function to get a DB connection
def get_connection():
    try:
        connection = psycopg2.connect(DB_CONNECTION_STRING)
        print("✅ Database connection established successfully!")
        return connection
    except OperationalError as oe:
        print(f"❌ Operational error: {oe}")
        raise
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        raise
