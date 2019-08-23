import requests
from flask import redirect, render_template, session
from functools import wraps


def apology(message, code=400):
    """Renders message as an apology to user."""

    return render_template("apology.html", code_number=code, message=message), code


def login_required(f):
    """ Decorate routes to require login. """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # reject symbol if it contains comma
    if "," in symbol:
        return None

    # token sk_3be9fd78baad48879c2d1e28d4a7ec3d
    # This is a private token, lol. Such disrespect.
    token = "sk_3be9fd78baad48879c2d1e28d4a7ec3d"

    # Get API. Data provided by https://cloud.iexapis.com/
    try:
        api = requests.get(f"https://cloud.iexapis.com/stable/stock/{symbol}/quote?token={token}")
    except ConnectionError as connection_api_server:
        print("Connection API server error.")
        print(connection_api_server)
        return apology("Connection API server error.", 500)
    else:
        if not api.ok:
            return None
        else:
            api_dict = api.json()
            company_name = api_dict.get('companyName')
            symbol_api = api_dict.get('symbol')
            latest_price = api_dict.get('latestPrice')

            if company_name is None or symbol_api is None or latest_price is None:
                return None

            text = [company_name, symbol_api, round(latest_price, 2)]

            return text


def usd(value):
    """Formats value as USD."""

    return f"${value:,.2f}"
