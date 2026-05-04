import mysql.connector
class Database:
    def __init__(self):
        self.db = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="atm_oops_db"
        )
        self.cursor = self.db.cursor()

    def execute(self, query, values=None):
        self.cursor.execute(query, values or ())
        return self.cursor

    def commit(self):
        self.db.commit()
class ATM:
    def __init__(self):
        self.db = Database()

    def register(self):
        username = input("Enter new username: ")
        password = input("Enter new password: ")

        if self.db.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        ).fetchone():
            print("Username already exists")
        else:
            self.db.execute(
                "INSERT INTO users (username, password, balance) VALUES (%s,%s,%s)",
                (username, password, 0)
            )
            self.db.commit()
            print("Registration successful")

    def login(self):
        username = input("Enter username: ")
        password = input("Enter password: ")

        user = self.db.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        ).fetchone()

        if user:
            print("Login successful")
            return User(self.db, username)
        else:
            print("Invalid login")
            return None

class User:
    def __init__(self, db, username):
        self.db = db
        self.username = username

    def get_balance(self):
        result = self.db.execute(
            "SELECT balance FROM users WHERE username=%s",
            (self.username,)
        ).fetchone()
        return result[0]

    def update_balance(self, new_balance):
        self.db.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (new_balance, self.username)
        )
        self.db.commit()

    def add_history(self, type, amount):
        self.db.execute(
            "INSERT INTO history (username, type, amount) VALUES (%s,%s,%s)",
            (self.username, type, amount)
        )
        self.db.commit()

    def show_history(self):
        records = self.db.execute(
            "SELECT type, amount, date FROM history WHERE username=%s ORDER BY id DESC",
            (self.username,)
        ).fetchall()

        if not records:
            print("No history found")
            return

        for row in records:
            t, amount, date = row
            print(f"{date} --> {t} ₹{amount}")

    def deposit(self):
        amount = int(input("Enter amount: "))
        balance = self.get_balance()
        new_balance = balance + amount
        self.update_balance(new_balance)
        self.add_history("Deposit", amount)
        print("Credit successful")

    def withdraw(self):
        amount = int(input("Enter amount: "))
        balance = self.get_balance()

        if amount > balance:
            print("Insufficient balance")
        else:
            new_balance = balance - amount
            self.update_balance(new_balance)
            self.add_history("Withdraw", amount)
            print("Debited successfully")

    def transfer(self):
        receiver = input("Enter receiver username: ")
        amount = int(input("Enter amount: "))

        sender_balance = self.get_balance()

        if amount > sender_balance:
            print("Insufficient balance")
            return

        rec = self.db.execute(
            "SELECT balance FROM users WHERE username=%s",
            (receiver,)
        ).fetchone()

        if not rec:
            print("Receiver not found")
            return

        receiver_balance = rec[0]

        # update balances
        new_sender_balance = sender_balance - amount
        new_receiver_balance = receiver_balance + amount

        self.db.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (new_sender_balance, self.username)
        )

        self.db.execute(
            "UPDATE users SET balance=%s WHERE username=%s",
            (new_receiver_balance, receiver)
        )

        self.add_history("Transfer", amount)
        self.db.commit()

        print("Transfer successful")

atm = ATM()

while True:
    print("\n1. Register")
    print("2. Login")
    print("3. Exit")

    option = int(input("Enter option: "))

    if option == 1:
        atm.register()

    elif option == 2:
        user = atm.login()

        if user:
            while True:
                print("\n1. Transfer")
                print("2. Debit")
                print("3. Credit")
                print("4. Balance Check")
                print("5. History")
                print("6. Logout")

                choice = int(input("Enter choice: "))

                if choice == 1:
                    user.transfer()

                elif choice == 2:
                    user.withdraw()

                elif choice == 3:
                    user.deposit()

                elif choice == 4:
                    print("Balance:", user.get_balance())

                elif choice == 5:
                    user.show_history()


                elif choice == 6:
                    print("Logged out")
                    break

    elif option == 3:
        print("Goodbye!")
        break

# class Database:
#     def __init__(self,name):
#         self.name = name
# d1 = Database()
# my_query = "INSERT INTO users (username, password, balance) VALUES (%s,%s,%s)",
                
# value = ("shubhamdon123", 1524, 0)
# d1.execute(my_query,value)
# d1.commit()
