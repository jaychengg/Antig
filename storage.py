
import streamlit as st
import sqlalchemy
from sqlalchemy import create_engine, text
import logging
import uuid
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("storage")

# Global Engine Pool
_db_engine = None

class StorageError(Exception):
    pass

def init_connection():
    """
    Initialize Cloud SQL connection using streamlit secrets.
    Expects [postgres] section in secrets.toml with:
    host, port, dbname, user, password
    """
    global _db_engine
    if _db_engine:
        return _db_engine

    try:
        # Check secrets
        if "postgres" not in st.secrets:
            raise StorageError("Missing [postgres] section in .streamlit/secrets.toml")
        
        conf = st.secrets["postgres"]
        
        # Build Connection String
        # url = f"postgresql+pg8000://{conf['user']}:{conf['password']}@{conf['host']}:{conf['port']}/{conf['dbname']}"
        
        # Using sqlalchemy.engine.url for safety
        db_url = sqlalchemy.engine.URL.create(
            drivername="postgresql+pg8000",
            username=conf["user"],
            password=conf["password"],
            host=conf["host"],
            port=conf["port"],
            database=conf["dbname"],
        )
        
        _db_engine = create_engine(db_url, pool_pre_ping=True)
        logger.info("✅ Cloud SQL Connection Established")
        return _db_engine

    except Exception as e:
        logger.error(f"❌ DB Connection Failed: {e}")
        return None

def check_db_status():
    """
    Returns (status_bool, message)
    """
    engine = init_connection()
    if not engine:
        return False, "Configuration Missing or Connection Failed"
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Online"
    except Exception as e:
        return False, str(e)

# =========================================================
# 📝 CRUD Operations
# =========================================================

def list_trades(user_id, ticker=None):
    engine = init_connection()
    if not engine: return []
    
    try:
        query = "SELECT * FROM trades WHERE user_id = :user_id"
        params = {"user_id": user_id}
        
        if ticker:
            query += " AND ticker = :ticker"
            params["ticker"] = ticker
            
        query += " ORDER BY datetime DESC"
        
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            # Convert to list of dicts
            trades = [dict(row._mapping) for row in result]
            return trades
    except Exception as e:
        logger.error(f"list_trades Error: {e}")
        return []

def add_trade(trade_data):
    """
    trade_data: dict with user_id, ticker, datetime, action, shares, price, fee, note
    """
    engine = init_connection()
    if not engine: raise StorageError("DB Offline")
    
    try:
        # Validate ID
        if "id" not in trade_data:
            trade_data["id"] = str(uuid.uuid4())
            
        stmt = text("""
            INSERT INTO trades (id, user_id, ticker, datetime, action, shares, price, fee, note)
            VALUES (:id, :user_id, :ticker, :datetime, :action, :shares, :price, :fee, :note)
        """)
        
        with engine.begin() as conn:
            conn.execute(stmt, trade_data)
            
        return True
    except Exception as e:
        logger.error(f"add_trade Error: {e}")
        raise e

def delete_trade(trade_id, user_id):
    engine = init_connection()
    if not engine: raise StorageError("DB Offline")
    
    try:
        stmt = text("DELETE FROM trades WHERE id = :id AND user_id = :user_id")
        with engine.begin() as conn:
            result = conn.execute(stmt, {"id": trade_id, "user_id": user_id})
            return result.rowcount > 0
    except Exception as e:
        logger.error(f"delete_trade Error: {e}")
        raise e
