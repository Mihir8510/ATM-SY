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
class Amount(BaseModel):
    username: str
    amount: int

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
    def withdraw(self, amount):
        return "Withdraw not allowed in FD account"
def get_account(account_type, balance):
    account_type = account_type.lower().strip()
    if account_type == "saving":
        return SavingAccount(balance)
    elif account_type == "current":
        return CurrentAccount(balance)
    elif account_type == "fd":
        return FDAccount(balance)
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

    cursor.execute("SELECT * FROM users WHERE username=%s", (user.username,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return {"msg": "Username already exists"}

    cursor.execute(
        "INSERT INTO users (username, password, balance,account_type) VALUES (%s, %s, %s,%s)",
        (user.username, user.password, 0,user.account_type)
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

    if not u:
        return {"msg": "User not found"}

    account = get_account(u["account_type"], u["balance"])

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

    if not u:
        return {"msg": "User not found"}

    account = get_account(u["account_type"], u["balance"])

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

        if not sender or not receiver:
            return {"msg": "User not found"}

        sender_acc = get_account(
            sender["account_type"],
            sender["balance"]
        )

        result = sender_acc.withdraw(data.amount)

        if isinstance(result, str):
            return {"msg": result}

        receiver_acc = get_account(
            receiver["account_type"],
            receiver["balance"]
        )

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