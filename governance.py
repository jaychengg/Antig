import time
import json
import os
from datetime import datetime

class FinazonGovernance:
    _instance = None
    
    # Constants
    DAILY_LIMIT_APP = 850
    DAILY_LIMIT_API = 1000
    RPM_LIMIT = 18.0
    BURST_LIMIT = 6
    POWER_SAVE_THRESHOLD = 150
    STATE_FILE = "governance_state.json"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FinazonGovernance, cls).__new__(cls)
            cls._instance._init_state()
        return cls._instance
    
    def _init_state(self):
        self.state = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "daily_requests": 0,
            "tickers": {} # {ticker: count}
        }
        self.last_req_time = 0
        self.tokens = self.RPM_LIMIT
        self.last_token_update = time.time()
        self._load_state()
        
    def _load_state(self):
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    saved = json.load(f)
                    # Check if date changed
                    if saved.get("date") == datetime.now().strftime("%Y-%m-%d"):
                        self.state = saved
                    else:
                        print("📅 New Day: Resetting Governance Budget")
                        # State resets automatically due to _init_state defaults if dates mismatch?
                        # No, we need to explicitly reset if loaded date is old
                        if saved.get("date") != datetime.now().strftime("%Y-%m-%d"):
                             self.state["date"] = datetime.now().strftime("%Y-%m-%d")
                             self.state["daily_requests"] = 0
                             self.state["tickers"] = {}
            except Exception as e:
                print(f"⚠️ Governance Load Error: {e}")
                
    def _save_state(self):
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.state, f)
        except Exception as e:
            print(f"⚠️ Governance Save Error: {e}")
            
    def _refill_tokens(self):
        now = time.time()
        elapsed = now - self.last_token_update
        # Refill rate: 18 tokens / 60 seconds = 0.3 tokens/sec
        refill = elapsed * (self.RPM_LIMIT / 60.0)
        self.tokens = min(self.BURST_LIMIT, self.tokens + refill)
        self.last_token_update = now
        
    def allow_request(self, ticker):
        # 1. Daily Gate
        if self.state["daily_requests"] >= self.DAILY_LIMIT_APP:
            return False, "Daily Budget Exceeded"
            
        # 2. Per Ticker Gate (30/day)
        ticker_usage = self.state["tickers"].get(ticker, 0)
        if ticker_usage >= 30:
             return False, f"Ticker Limit ({ticker}) Exceeded"
             
        # 3. Rate Limit (Token Bucket)
        self._refill_tokens()
        if self.tokens >= 1:
            self.tokens -= 1
            self.state["daily_requests"] += 1
            self.state["tickers"][ticker] = ticker_usage + 1
            self._save_state()
            return True, "OK"
        else:
            return False, "Rate Limited (RPM)"
            
    def is_power_saving(self):
        remaining = self.DAILY_LIMIT_APP - self.state["daily_requests"]
        return remaining < self.POWER_SAVE_THRESHOLD
        
    def get_status(self):
        self._refill_tokens()
        return {
            "used": self.state["daily_requests"],
            "remaining": self.DAILY_LIMIT_APP - self.state["daily_requests"],
            "rpm_tokens": round(self.tokens, 1),
            "power_save": self.is_power_saving()
        }

# Global Instance
gov = FinazonGovernance()
