from datetime import datetime, date
import mysql.connector
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= DB FUNCTION =================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="atm_oops_db"
    )

# ================= MODELS =================
class User(BaseModel):
    username: str
    password: str
    
class RegisterUser(BaseModel):
    username: str
    password: str
    account_type: str
    pin : str
class Amount(BaseModel):
    username: str
    amount: int
    pin: str = ""

class Transfer(BaseModel):
    sender: str
    receiver: str
    amount: int

class ChangePassword(BaseModel):
    username: str
    old_password: str
    new_password: str

# =======Amount==============
class Account:
    def __init__(self, balance):
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        raise NotImplementedError

# =======saving account=====
class SavingAccount(Account):
    MIN_BALANCE = 5000

    def withdraw(self, amount):
        if self.balance - amount < self.MIN_BALANCE:
            return "Minimum balance ₹5000 required"
        self.balance -= amount
        return self.balance
# =======current account====
class CurrentAccount(Account):
    def withdraw(self, amount):
        if amount > self.balance:
            return "Insufficient balance"
        self.balance -= amount
        return self.balance
# =======FD account======
class FDAccount(Account):
    def __init__(self, balance, fd_start_date, fd_years):
        super().__init__(balance)
        self.fd_start_date = fd_start_date
        self.fd_years = fd_years

    def withdraw(self, amount):
        if not self.fd_start_date:
            return "FD start date not found"
        today = date.today()

        fd_date = self.fd_start_date

        if isinstance(fd_date, str):
            fd_date = datetime.strptime(fd_date, "%Y-%m-%d").date()
        maturity_year = fd_date.year + self.fd_years

        # FD mature thai?
        if today.year < maturity_year:
            return f"FD not matured. Withdraw after {maturity_year}"

        if amount > self.balance:
            return "Insufficient balance"

        self.balance -= amount
        return self.balance
    
def get_account(user):

    account_type = user["account_type"].lower().strip()

    if account_type == "saving":
        return SavingAccount(user["balance"])

    elif account_type == "current":
        return CurrentAccount(user["balance"])

    elif account_type == "fd":
        return FDAccount(
            user["balance"],
            user["fd_start_date"],
            user["fd_years"]
        )

    return None
# ================= HOME =================
@app.get("/")
def home():
    return {"msg": "API is running"}

# ================= REGISTER =================
@app.post("/register")
def register(user: RegisterUser):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if len(user.password) < 4:
        return {"msg": "Password must be at least 4 characters"}
    cursor.execute("SELECT * FROM users WHERE username=%s", (user.username,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return {"msg": "Username already exists"}
    fd_start = None
    fd_years = None

    if user.account_type.lower() == "fd":
        fd_start = date.today()
        fd_years = 5
    cursor.execute(
        "INSERT INTO users (username, password, balance,account_type,pin,fd_start_date, fd_years) VALUES (%s, %s, %s,%s,%s,%s,%s)",
        (user.username, user.password, 0,user.account_type,user.pin,fd_start,fd_years)
    )

    db.commit()
    cursor.close()
    db.close()

    return {"msg": "Registered successfully"}

# ================= LOGIN =================
@app.post("/login")
def login(user: User):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username=%s", (user.username,))
    u = cursor.fetchone()

    if not u:
        return {"msg": "User not found"}

    if u["is_locked"]:
        return {"msg": "Account is locked."}

    if u["password"] == user.password:
        # reset attempts
        cursor.execute(
            "UPDATE users SET attempts=0 WHERE username=%s",
            (user.username,)
        )
        db.commit()

        return {"msg": "Login successful", "user": u}
    else:
        attempts = u["attempts"] + 1

        if attempts >= 3:
            cursor.execute(
                "UPDATE users SET attempts=%s, is_locked=TRUE WHERE username=%s",
                (attempts, user.username)
            )
            msg = "Account locked after 3 attempts"
        else:
            cursor.execute(
                "UPDATE users SET attempts=%s WHERE username=%s",
                (attempts, user.username)
            )
            msg = f"Wrong password ({attempts}/3)"

        db.commit()
        return {"msg": msg}

# ================= DEPOSIT =================
@app.post("/deposit")
def deposit(data: Amount):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username=%s", (data.username,))
    u = cursor.fetchone()
    if data.amount > 50000:
        return {"msg": "Deposit limit is ₹50000"}

    if not u:
        return {"msg": "User not found"}

    account = get_account(u)

    new_balance = account.deposit(data.amount)

    cursor.execute(
        "UPDATE users SET balance=%s WHERE username=%s",
        (new_balance, data.username)
    )

    cursor.execute(
        "INSERT INTO history (username, type, amount) VALUES (%s, %s, %s)",
        (data.username, "deposit", data.amount)
    )

    db.commit()
    return {"msg": "Deposit successful", "balance": new_balance}

# ================= WITHDRAW =================
@app.post("/withdraw")
def withdraw(data: Amount):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE username=%s", (data.username,))
    u = cursor.fetchone()
    if u["pin"] != data.pin:
        return {"msg": "Wrong PIN"}
    if data.amount > 20000:
        return {"msg": "Withdraw limit is ₹20000"}
    if not u:
        return {"msg": "User not found"}

    account = get_account(u)

    result = account.withdraw(data.amount)

    if isinstance(result, str):
        return {"msg": result}

    cursor.execute(
        "UPDATE users SET balance=%s WHERE username=%s",
        (account.balance, data.username)
    )

    cursor.execute(
        "INSERT INTO history (username, type, amount) VALUES (%s, %s, %s)",
        (data.username, "withdraw", data.amount)
    )

    db.commit()
    return {"msg": "Withdraw successful", "balance": account.balance}


# ================= BALANCE =================
@app.get("/balance/{username}")
def balance(username: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT balance FROM users WHERE username=%s", (username,))
    u = cursor.fetchone()

    cursor.close()
    db.close()

    if u:
        return {"balance": u["balance"]}
    return {"msg": "User not found"}

# ================= HISTORY =================
@app.get("/history/{username}")
def history(username: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT type, amount, date FROM history WHERE username=%s",
        (username,)
    )
    records = cursor.fetchall()

    cursor.close()
    db.close()

    result = []
    for r in records:
        result.append(f"{r['type']} ₹{r['amount']} on {r['date']}")

    return {"history": result}

# ================= TRANSFER =================
@app.post("/transfer")
def transfer(data: Transfer):
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (data.sender,)
        )
        sender = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (data.receiver,)
        )
        receiver = cursor.fetchone()
        if data.sender == data.receiver:
            return {"msg": "Cannot transfer to same account"}
        if not sender or not receiver:
            return {"msg": "User not found"}

        sender_acc = get_account(sender)

        result = sender_acc.withdraw(data.amount)

        if isinstance(result, str):
            return {"msg": result}

        receiver_acc = get_account(receiver)

        receiver_acc.deposit(data.amount)

        cursor.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (sender_acc.balance, data.sender)
        )

        cursor.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (receiver_acc.balance, data.receiver)
        )

        db.commit()

        return {
            "msg": "Transfer successful",
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        cursor.close()
        db.close()