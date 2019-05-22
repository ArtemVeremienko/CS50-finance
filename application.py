import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Look up the current user
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session['user_id'])
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", 
                        user_id=session['user_id'])
    
    quotes = {}
    all_stocks = 0
    # Iterate all exist stocks
    for stock in stocks:
        quotes[stock['symbol']] = lookup(stock['symbol'])
        all_stocks += quotes[stock['symbol']]['price'] * stock['total_shares']

    cash_remaining = user[0]['cash']
    total = cash_remaining + all_stocks
    return render_template("index.html", quotes=quotes, stocks=stocks, total=total, cash_remaining=cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Check POST from method
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        quote = lookup(symbol);
        # Ensure quote was input
        if not quote:
            return apology("missing or wrong symbol")
        
        # Check if shares positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("missing shares")
        
        # Check if shares request was 0
        if shares <= 0:
            return apology("shares less or equal than 0")
        
        # Query database for username
        rows = rows = db.execute("SELECT cash FROM users WHERE id = :user_id",
                          user_id=session["user_id"])
        
        # How much cash have user in his account
        cash_remaining = rows[0]['cash']
        price_per_share = quote['price']
        
        # Total price order
        total_price = price_per_share * shares
        
        # Check for money to buy
        if total_price > cash_remaining:
            return apology("not enough money")
        
        # Orders keeping
        db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price = total_price, user_id = session['user_id'])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES (:user_id, :symbol, :shares, :price_per_share)", 
                    user_id=session['user_id'], symbol=symbol, shares=shares, price_per_share=price_per_share)

        # Display a flash 'Bought!' message
        flash("Bought!")
        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    input_username = request.args.get("username")
    usernames = db.execute("SELECT username FROM users")
    for username in usernames:
        if username['username'] == input_username:
            return jsonify("true")
    return jsonify("false")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price_per_share, created_at FROM transactions WHERE user_id = :user_id ORDER BY created_at DESC",
                                user_id=session['user_id'])
    return render_template("history.html", transactions=transactions)

@app.route("/add-funds", methods=["GET", "POST"])
@login_required
def add_funds():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount"))
        except:
            return apology("Money must be a real number")
        
        db.execute("UPDATE users SET cash = cash + :amount WHERE id = :user_id", amount=amount, user_id=session['user_id'])
        
        flash(f"Successfully added {usd(amount)}")
        return redirect("/")
    else:
        return render_template("add_funds.html")
        
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    # Check POST from method
    if request.method == "POST":
        # Ensure quote was input
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol")
        # Ensure quoted was right
        quoted = lookup(symbol);
        if not quoted:
            return apology("missing symbol")
        return render_template("quoted.html", quoted=quoted)
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Check POST form method
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        
        # Ensure passwords match    
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)
            
        # Add new user to db
        new_user_id = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", 
                username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")))
        
        # unique username constraint violated?
        if not new_user_id:
            return apology("username taken")
        
        # Remember which user has logged in
        session["user_id"] = new_user_id
        
        # Display a flash message
        flash("Registered!")
        
        # Redirect user to home page
        return redirect("/")
        
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
        
    


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Check POST from method
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol);
        # Ensure quote was input
        if not quote:
            return apology("missing symbol")
        
        # Check if shares positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("missing shares")
        
        # Check if shares request was 0
        if shares <= 0:
            return apology("shares less or equal than 0")
        
        
        # Check if we have enough shares
        stock = db.execute("SELECT SUM(shares) AS total_shares FROM transactions WHERE user_id = :user_id AND symbol = :symbol GROUP BY symbol",
                            user_id=session['user_id'], symbol=symbol)
        # Check for empty name or shares
        if len(stock) != 1 or stock[0]['total_shares'] < 0 or stock[0]['total_shares'] < shares:
            return apology("wrong shares")
        
        # Query database for username
        rows = rows = db.execute("SELECT cash FROM users WHERE id = :user_id",
                          user_id=session["user_id"])
        
        # How much cash have user in his account
        cash_remaining = rows[0]['cash']
        price_per_share = quote['price']
        
        # Total price order
        total_price = price_per_share * shares
        
        # Orders keeping
        db.execute("UPDATE users SET cash = cash + :price  WHERE id = :user_id", price = total_price, user_id = session['user_id'])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES (:user_id, :symbol, :shares, :price_per_share)", 
                    user_id=session['user_id'], symbol=symbol, shares=-shares, price_per_share=price_per_share)
    
        # Display a flash 'Sold!' message
        flash("Sold!")
        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session['user_id'])
        return render_template("sell.html", stocks=stocks)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change password"""
    if request.method == "POST":
        if not request.form.get("current_password"):
            return apology("Need current password")
        
        #Query database for user_id
        rows = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id=session['user_id'])   

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("current_password")):
            return apology("invalid password", 403)
        
        # Ensure new password not empty
        if not request.form.get("new_password"):
            return apology("must provide new password", 403)
        # Ensure new password confirmation not empty
        elif not request.form.get("new_password_confirmation"):
            return apology("must provide new password confirmation", 403)
        # Ensure new password and confirmation match
        elif request.form.get("new_password") != request.form.get("new_password_confirmation"):
            return apology("new password and confirmation must match", 403)
            
        #Update database password
        hash = generate_password_hash(request.form.get("new_password"))
        rows = db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", hash=hash, user_id=session['user_id'])
        
        # Display a flash message
        flash("Password changed!")
        return render_template("change_password.html")
    else:
        return render_template("change_password.html")
    

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
