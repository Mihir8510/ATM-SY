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

class Amount(BaseModel):
    username: str
    amount: int

class Transfer(BaseModel):
    sender: str
    receiver: str
    amount: int

# ================= HOME =================
@app.get("/")
def home():
    return {"msg": "API is running"}

# ================= REGISTER =================
@app.post("/register")
def register(user: User):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE username=%s", (user.username,))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return {"msg": "Username already exists"}

    cursor.execute(
        "INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)",
        (user.username, user.password, 0)
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

    cursor.execute(
        "SELECT * FROM users WHERE username=%s AND password=%s",
        (user.username, user.password)
    )
    u = cursor.fetchone()

    cursor.close()
    db.close()

    if u:
        return {"msg": "Login successful", "user": u}
    return {"msg": "Invalid login"}

# ================= DEPOSIT =================
@app.post("/deposit")
def deposit(data: Amount):
    try:
        if data.amount <= 0:
            return {"msg": "Amount must be greater than 0"}
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username=%s", (data.username,))
        u = cursor.fetchone()

        if not u:
            cursor.close()
            db.close()
            return {"msg": "User not found"}

        new_balance = u["balance"] + data.amount

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
    except Exception as e:
        return {"msg": f"Error: {str(e)}"}
    finally:
        cursor.close()
        db.close()

    

# ================= WITHDRAW =================
@app.post("/withdraw")
def withdraw(data: Amount):
    try:
        if data.amount <= 0:
            return {"msg": "Amount must be greater than 0"}
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username=%s", (data.username,))
        u = cursor.fetchone()

        if not u:
            cursor.close()
            db.close()
            return {"msg": "User not found"}

        if data.amount > u["balance"]:
            cursor.close()
            db.close()
            return {"msg": "Insufficient balance"}

        new_balance = u["balance"] - data.amount

        cursor.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (new_balance, data.username)
        )

        cursor.execute(
            "INSERT INTO history (username, type, amount) VALUES (%s, %s, %s)",
            (data.username, "withdraw", data.amount)
        )

        db.commit()
        return {"msg": "Withdraw successful", "balance": new_balance}
    except Exception as e:
        return {"msg": f"Error: {str(e)}"}
    finally:
        cursor.close()
        db.close()


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
        if data.amount <= 0:
            return {"msg": "Amount must be greater than 0"}
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username=%s", (data.sender,))
        sender = cursor.fetchone()

        cursor.execute("SELECT * FROM users WHERE username=%s", (data.receiver,))
        receiver = cursor.fetchone()

        if not sender or not receiver:
            cursor.close()
            db.close()
            return {"msg": "User not found"}

        if data.amount > sender["balance"]:
            cursor.close()
            db.close()
            return {"msg": "Insufficient balance"}

        cursor.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (sender["balance"] - data.amount, data.sender)
        )

        cursor.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (receiver["balance"] + data.amount, data.receiver)
        )

        cursor.execute(
            "INSERT INTO history (username, type, amount) VALUES (%s, %s, %s)",
            (data.sender, f"transfer to {data.receiver}", data.amount)
        )

        cursor.execute(
            "INSERT INTO history (username, type, amount) VALUES (%s, %s, %s)",
            (data.receiver, f"received from {data.sender}", data.amount)
        )

        db.commit()
        return {"msg": "Transfer successful"}
    finally:
        cursor.close()
        db.close()

    