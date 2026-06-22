import os
import db_connect

PORTFOLIO_MODE = os.environ.get('PORTFOLIO_MODE', 'False').lower() in ('true', '1', 't')

def get_db(dictionary=True):
    if PORTFOLIO_MODE:
        return None
    try:
        """
        Returns a fresh cursor for every request to ensure the latest DB data.
        """
        conn = db_connect.connection  # use existing connection
        if dictionary:
            return conn.cursor(dictionary=True)
        return conn.cursor()

    except Exception:
        return None