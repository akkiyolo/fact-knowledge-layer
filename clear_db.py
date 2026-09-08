import os
import psycopg
from app.config import get_settings

def clear_db():
    print("Clearing Render Database...")
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                print("Deleting relations...")
                cur.execute("DELETE FROM relations;")
                print("Deleting claims...")
                cur.execute("DELETE FROM claims;")
                print("Deleting documents...")
                cur.execute("DELETE FROM documents;")
            conn.commit()
        print("Database cleared successfully! Fresh start.")
    except Exception as e:
        print(f"Failed to clear db: {e}")

if __name__ == "__main__":
    clear_db()
