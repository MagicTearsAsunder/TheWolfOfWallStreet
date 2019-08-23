import sys
import psycopg2
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


"""
  Configure your Database here. Assume you are using defaut port 5432.
"""
# Connect PostgreSQL database.
try:
    conn = psycopg2.connect(dbname="Your_Database_Name", user="Your_Username", password="Your_Password", host="localhost")
except psycopg2.Error as connection_error:
    print(connection_error)
    sys.exit("Database connection failed")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    username = session["user_id"]

    # Get cash and UUID from user's table.
    cur = conn.cursor()
    try:
        cur.execute("SELECT current_cash, user_transactions FROM users WHERE username = %s",
                    (username,))
    except psycopg2.Error as psycopg_error:
        print(psycopg_error)
        cur.close()
        return apology("Something went wrong.", 500)
    else:
        cash_plus_uuid = cur.fetchone()
        cur.close()

    # Current user's cash and his UUID.
    current_cash = float(cash_plus_uuid[0])
    uuid_transaction = cash_plus_uuid[1]

    # Search for all user's transactions in transactions table.
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT symbol, SUM(shares) FROM transactions WHERE trans_uid = %s GROUP BY symbol HAVING SUM(shares) > 0",
                    (uuid_transaction,))
    except psycopg2.Error as psycopg_error:
        print(psycopg_error)
        cur.close()
        return apology("Something went wrong.", 500)
    else:
        symbols_plus_shares = cur.fetchall()
        cur.close()

    # Form a list of all user's Data (Name, Symbol, Shares, Price, Total)
    data_from_lookup = []
    only_stocks_value = 0
    for i in range(len(symbols_plus_shares)):
        data_from_lookup.append(lookup(symbols_plus_shares[i][0]))
        symbols_plus_shares_temporal = symbols_plus_shares[i][1]
        price_of_specific_stocks = symbols_plus_shares_temporal * data_from_lookup[i][2]
        only_stocks_value += price_of_specific_stocks
        data_from_lookup[i].insert(3, round(price_of_specific_stocks, 2))
        data_from_lookup[i].insert(2, symbols_plus_shares_temporal)

    # Pass user's data to HTML form
    total_users_cash = only_stocks_value + current_cash
    return render_template("index.html", data_from_lookup=data_from_lookup, current_cash=current_cash, total_users_cash=round(total_users_cash, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Must provide symbols and shares.", 403)
        if not request.form.get("shares"):
            return apology("Must provide symbols and shares.", 403)

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        shares = int(shares)

        # Check shares
        if shares < 1:
            return apology("Shares should me greater or equals 1.", 403)

        # Take data from API.   lookup_list[0] - company_name.  lookup_list[1] - symbol_api.    lookup_list[2] - latest_price.
        lookup_list = lookup(symbol)
        if lookup_list[0] is None or lookup_list[1] is None or lookup_list[2] is None:
            return apology("Invalid Literels.", 403)

        # Take user's current cash
        cur = conn.cursor()
        username = session["user_id"]
        try:
            cur.execute("SELECT current_cash, user_transactions FROM users WHERE username = %s;",
                        (username,))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            cur.close()
            return apology("Something went wrong.", 500)
        else:
            cash_plus_uuid = cur.fetchone()
            cur.close()
        user_s_cash = float(cash_plus_uuid[0])
        user_s_uuid = cash_plus_uuid[1]

        # Check sufficiency of user's cash
        total_price = shares * lookup_list[2]
        if total_price > user_s_cash:
            return apology("Insufficient funds", 403)

        # Update user's cash
        user_s_cash -= total_price
        cur = conn.cursor()
        try:
            cur.execute("UPDATE users SET current_cash=%s WHERE user_transactions=%s",
                        (user_s_cash, user_s_uuid,))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            conn.rollback()
        else:
            conn.commit()
            cur.close()

        # Update transactions table
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO transactions (username, symbol, shares, price, time, trans_uid) VALUES (%s, %s, %s, %s, LOCALTIMESTAMP(0), %s)",
                        (username, lookup_list[1], shares, lookup_list[2], user_s_uuid, ))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            conn.rollback()
        else:
            conn.commit()
            cur.close()

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Show all the user's transactions history
    username = session["user_id"]

    cur = conn.cursor()
    try:
        cur.execute("SELECT symbol, shares, price, time FROM transactions WHERE username = %s ORDER BY time",
                    (username,))
    except psycopg2.Error as psycopg_error:
        print(psycopg_error)
        cur.close()
        return apology("Something went wrong.", 500)
    else:
        history_data = cur.fetchall()
        cur.close()

    return render_template("history.html", history_data=history_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username.", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Must provide password.", 403)

        # Query database for username
        username = request.form.get("username")
        cur1 = conn.cursor()

        # Search username in Database
        try:
            cur1.execute("SELECT username, hashed_password FROM users WHERE username = %s",
                         (username,))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            cur1.close()
            return apology("Something went wrong.", 500)
        else:
            rows = cur1.fetchone()
            cur1.close()

        # Ensure username exists and password is correct
        if rows is None or not check_password_hash(rows[1], request.form.get("password")):
            return apology("Invalid username and/or password.", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Show the current stocks price"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        text = lookup(symbol)

        if text[0] is None or text[1] is None or text[2] is None:
            return render_template("invalid_literals.html")

        # Form a string to be shown to user
        text = f"A stock of {text[0]} ({text[1]}). Latest price: {text[2]}"

        return render_template("quoted.html", text=text)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Grab user's inputs
    if request.method == "POST":
        username_reg = request.form.get("username_reg")
        password1_reg = request.form.get("password1_reg")
        password2_reg = request.form.get("password2_reg")

        # Check username for correctness
        if username_reg is None:
            return apology("Username's input is empty.", 403)
        if not username_reg.isalnum():
            return apology("Username should be alphanumeric.", 403)

        # Check user's password for correctness
        if password1_reg is None or password2_reg is None:
            return apology("Password's input is empty.", 403)
        if password1_reg != password2_reg:
            return apology("The passwords do not match.", 403)
        if not password1_reg.isalnum():
            return apology("Password should be alphanumeric.", 403)

        # Encrypt password
        hashed_password = generate_password_hash(password1_reg, method='pbkdf2:sha256', salt_length=8)

        # Insert users's data to Database
        cur2 = conn.cursor()
        try:
            cur2.execute("INSERT INTO users (username, hashed_password, current_cash, user_transactions) VALUES (%s, %s, %s, uuid_generate_v4())",
                         (username_reg, hashed_password, 10000.00, ))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            conn.rollback()
            cur2.close()
            return apology("Username already exists.", 403)
        else:
            conn.commit()
            cur2.close()

        return render_template("login.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    username = session["user_id"]
    if request.method == "GET":

        # Search for current user's stocks
        cur = conn.cursor()
        try:
            cur.execute("SELECT DISTINCT symbol FROM transactions WHERE username = %s GROUP BY symbol HAVING SUM(shares) > 0",
                        (username, ))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            cur.close()
            return apology("Something went wrong.", 500)
        else:
            symbols_from_db = cur.fetchall()
            cur.close()

        # Return this stocks to HTML file
        symbols_list = []
        for i in range(len(symbols_from_db)):
            symbols_list.append(symbols_from_db[i][0])

        return render_template("sell.html", symbols_list=symbols_list)

    # If POST method.
    else:
        # Grab the parameters user inputs
        if request.form.get("symbol") is None or request.form.get("shares") is None:
            return apology("Must provide symbols and shares.", 403)
        symbol_user_inputs = request.form.get("symbol")
        shares_user_inputs = int(request.form.get("shares"))

        # Search for current user's stocks
        cur = conn.cursor()
        try:
            cur.execute("SELECT symbol, SUM(shares) FROM transactions WHERE username = %s AND symbol = %s GROUP BY symbol HAVING SUM(shares) > 0",
                (username, symbol_user_inputs, ))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            cur.close()
            return apology("Something went wrong.", 500)
        else:
            symbols_and_shares = cur.fetchone()
            cur.close()

        # Check if stocks are sufficient
        if not symbols_and_shares[0] == symbol_user_inputs or symbols_and_shares[1] < shares_user_inputs:
            return apology("Not enough shares.", 403)

        # Prepare transaction to Database
        shares_inserting_in_database = -shares_user_inputs

        # Get user's UUID from users table
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_transactions FROM users WHERE username = %s",
                        (username,))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            cur.close()
            return apology("Something went wrong.", 500)
        else:
            users_uuid = cur.fetchone()
            cur.close()

        # Get actual stock's price from API function lookup
        price = lookup(symbol_user_inputs)
        price = price[2]

        # Peform negative(sell) transaction to Database
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO transactions (username, symbol, shares, price, time, trans_uid) VALUES (%s, %s, %s, %s, LOCALTIMESTAMP(0), %s)",
                (username, symbol_user_inputs, shares_inserting_in_database, price, users_uuid))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            conn.rollback()
            cur.close()
            return apology("Username already exists.", 403)
        else:
            conn.commit()
            cur.close()

        # Add cash to user
        additional_cash = round((shares_user_inputs * price), 2)
        cur = conn.cursor()
        try:
            cur.execute("UPDATE users SET current_cash = current_cash + %s WHERE user_transactions = %s",
                        (additional_cash, users_uuid, ))
        except psycopg2.Error as psycopg_error:
            print(psycopg_error)
            conn.rollback()
            cur.close()
            return apology("Username already exists.", 403)
        else:
            conn.commit()
            cur.close()

        return redirect("/sell")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


if __name__ == '__main__':
    app.run()


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
