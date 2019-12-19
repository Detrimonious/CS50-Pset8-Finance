import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # grabs current money the logged-in user has
    money = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    thecash = money[0]["cash"]

    # grabs the stocks (symbols) the user has bought, as well as the sum of each stock they have purchased. Excludes stocks where num=0 (all sold)
    rows = db.execute("SELECT Symbol, SUM(Sharesnum) FROM Buy WHERE User=:User GROUP BY Symbol HAVING sum(Sharesnum)>0", User=session["user_id"])

    # empty dictionary to store each stock symbol and their current lookup prices, and variable to store total value so far
    pricedict = {}
    totaldict = {}
    sumprices = 0.0
    for row in rows:
        price = lookup(row["Symbol"])["price"]
        sumprices += (row["SUM(Sharesnum)"]) * price
        pricedict[row["Symbol"]] = usd(price)
        totaldict[row["Symbol"]] = usd(price * row["SUM(Sharesnum)"])

    totalcash = usd(thecash + sumprices)
    currentcash = usd(thecash)

    # sends the symbols, sum of shares, dictionary of symbols-to-lookup-price, and current amount of money remaining
    return render_template("index.html", rows=rows, pricedict=pricedict, totaldict=totaldict, currentcash=currentcash, totalcash=totalcash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # if we are already on buy.html and then we submit the symbol
    if request.method == "POST":

        # if no symbol is entered, error
        if not request.form.get("symbol"):
            return apology("No symbol entered", 400)

        # use function in helpers 'lookup' for the symbol, if the symbol doesn't exist, error
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote == None:
            return apology("This symbol does not exist", 400)

        # if no shares entered, error
        if not request.form.get("shares"):
            return apology("Enter # shares", 400)

        # if shares less than 1 and not integer, error
        try:
            numshares = int(request.form.get("shares"))
        except ValueError:
            return apology("Shares must be integer", 400)

        if numshares < 1:
            return apology("Shares is not a positive integer", 400)

        cost = numshares * int(quote['price'])

        # select the user id, see if they have enough money to afford the shares
        user = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        if user[0]["cash"] < int(cost):
            return apology("Not enough cash left.", 400)

        # add purchases to table 'buy', and deduct money from the user
        else:
            result = db.execute("INSERT INTO Buy('User', 'Time', 'Symbol', 'Sharesnum', 'Price') VALUES (?,?,?,?,?)", (session["user_id"], datetime.now(), symbol, numshares, cost))
            result = db.execute("UPDATE users SET cash=? WHERE id=?", (user[0]["cash"]-cost, session["user_id"]))

        return redirect("/")

    return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""

    # gets the username entered in the register form
    name = request.args.get("username")
    users = db.execute("SELECT username FROM users")

    # if the length is <1 or already used in the database, return False. else True.
    if len(name) < 1:
        return jsonify(False)

    if len(name) >= 1:
        for user in users:
            if user["username"] == name:
                return jsonify(False)

    return jsonify(True)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # only selects the rows (transactions) made by the logged-in user
    rows = db.execute("SELECT * FROM Buy WHERE User=:User", User=session["user_id"])

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
    """Get stock quote."""

    # if we are already on quote.html and then we submit the symbol
    if request.method == "POST":

        # if no symbol is entered, error
        if not request.form.get("symbol"):
            return apology("No symbol entered.", 400)

        # use function in helpers 'lookup' for the symbol, and make the price into usd, then display all in html
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote:
            for keyitem, valueitem in quote.items():
                if keyitem == "price":
                    quote[keyitem] = usd(valueitem)
            return render_template("quoted.html", quote=quote)
        else:
            return apology("Not a valid quote.", 400)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # if we are on register.html and things are inputted and submitted
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # ensure confirmation password was submitted
        elif not request.form.get("confirmation"):
            return apology("please confirm your password", 400)

        # ensure password and confirmation are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation does not match", 400)

        # hash the password
        hashword = generate_password_hash(request.form.get("password"))

        # add the username and hashed password into the database. if username is already in the database, error.
        result = db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", (request.form.get("username"), hashword))
        if not result:
            return apology("User already exists", 400)

        # retain the user logged in
        session["user_id"]=result

        return redirect("/")

    # if we have not yet logged in or submitted information, display a register page
    else:
       return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # regardless of GET or POST, generate list of stock symbols user has had
    stocks = db.execute("SELECT Symbol, SUM(Sharesnum) FROM Buy GROUP BY Symbol HAVING User=:User", User=session["user_id"])

    # if POST and items were submitted
    if request.method == "POST":

        symbol = request.form.get("symbol")

        # if no symbol selected somehow
        if not request.form.get("symbol"):
            return apology("No stock selected", 400)

        # if no shares were entered
        if not request.form.get("shares"):
            return apology("Enter num shares", 400)

        # if shares less than 1 and not integer, error
        try:
            numshares = int(request.form.get("shares"))
        except ValueError:
            return apology("Shares must be integer", 400)

        if numshares < 1:
            return apology("Shares must be a positive integer", 400)

        # get the number of shares they have in the selected stock. if attempting to sell more than owned, error
        for x in stocks:
            if x["Symbol"] == symbol:
                shares = x["SUM(Sharesnum)"]
        if numshares > shares:
            return apology("Selling more than owned", 400)

        # should look up the current price, check the total, and add a Sale to the Buy table by using negative numshares. Also update the cash the user has
        quote = lookup(symbol)
        cost = numshares * quote['price']
        user = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        result = db.execute("INSERT INTO Buy('User', 'Time', 'Symbol', 'Sharesnum', 'Price') VALUES (?,?,?,?,?)", (session["user_id"], datetime.now(), symbol, -numshares, cost))
        result = db.execute("UPDATE users SET cash=? WHERE id=?", (user[0]["cash"]+cost, session["user_id"]))

        return redirect("/")

    return render_template("sell.html", stocks=stocks)


@app.route("/passchange", methods=["GET", "POST"])
@login_required
def passchange():
    """Change user password"""

    # if we are on register.html and things are inputted and submitted
    if request.method == "POST":

        # gets current password hash from database
        hashresult = db.execute("SELECT hash FROM users WHERE id=:id", id=session["user_id"])

        # hash the new password
        hashword = generate_password_hash(request.form.get("password"))

        # Ensure all password blanks were filled
        if not request.form.get("currentpassword") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("fill all blanks", 400)

        # Ensure the correct current password is entered
        elif not check_password_hash(hashresult[0]["hash"], request.form.get("currentpassword")):
            return apology("not correct current password", 400)

        # ensure password and confirmation are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password confirmation does not match", 400)

        # update into new hashed password
        result = db.execute("UPDATE users SET hash=? WHERE id=?", (hashword, session["user_id"]))

        return redirect("/")

    # if we have not yet submitted information, display a 'change password' page
    else:
       return render_template("passchange.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
