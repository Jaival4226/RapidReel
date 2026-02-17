from app.db.session import engine
from app.db.base import Base  
from app.db import models     

def init_db():
    print("⏳ Creating Database Tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database Tables Created.")

if __name__ == "__main__":
    init_db()