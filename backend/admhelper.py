import os, json
from datetime import datetime
from flask import request, jsonify, flash, redirect

# In-memory cache store for data.json snapshot
_PORTFOLIO_CACHE = None

# Evaluate mode locally to avoid circular dependencies
raw_env_value = os.environ.get('PORTFOLIO_MODE', 'NOT_SET')
IS_PORTFOLIO = raw_env_value.lower() in ('true', '1', 't')


def load_portfolio_data(key=None):
    """
    Helper to read data from the frozen data.json snapshot file during Portfolio Mode.
    Uses in-memory caching to optimize query performance across modules.
    """
    global _PORTFOLIO_CACHE

    try:
        if _PORTFOLIO_CACHE is None:
            with open('data.json', 'r', encoding='utf-8') as f:
                _PORTFOLIO_CACHE = json.load(f)

        data = _PORTFOLIO_CACHE
        raw_list = data.get(key, []) if key else data

        # If rows come back as raw lists instead of dicts, map them to explicit dict profiles
        if raw_list and isinstance(raw_list, list) and isinstance(raw_list[0], list):
            if key == 'songs':
                return [{'song_id': r[0], 'songtitle': r[1], 'artist': r[2], 'album': r[3]} for r in raw_list]
            if key == 'showtitle':
                return [{'title_id': r[0], 'title': r[1], 'releaseYear': r[2]} for r in raw_list]
        return raw_list
    except Exception as e:
        print(f"⚠️ Portfolio Data Loading Error [{key}]: {str(e)}")
        return []


def format_date_filter(value, format_string='%Y-%m-%d'):
    """Safely formats both SQL date objects and Portfolio string dates in HTML."""
    if not value:
        return ""
    
    if isinstance(value, str):
        try:
            clean_str = value.split('T')[0].split()[0]
            return datetime.strptime(clean_str, '%Y-%m-%d').strftime(format_string)
        except ValueError:
            return value
            
    try:
        return value.strftime(format_string)
    except AttributeError:
        return str(value)


def init_portfolio_middleware(app, db_ref=None):
    """
    Registers Flask hooks, context processors, and template filters on the app instance.
    """
    @app.context_processor
    def inject_portfolio_status():
        return dict(is_portfolio=IS_PORTFOLIO)

    @app.template_filter('format_date')
    def _format_date_filter(value, format_string='%Y-%m-%d'):
        return format_date_filter(value, format_string)

    @app.before_request
    def handle_portfolio_intercepts():
        if IS_PORTFOLIO:
            if request.method == "POST":
                if request.is_json:
                    return jsonify({"success": True, "message": "Demo Mode: Changes simulated successfully."})
                flash("Sandbox Mode: Structural edits are simulated without modifications.", "success")
                return redirect(request.path)
            return

        # Local mode database keep-alive check
        if db_ref and getattr(db_ref, 'connection', None):
            try:
                db_ref.connection.ping(reconnect=True)
            except Exception:
                try:
                    db_ref.connection = db_ref.create_connection()
                except Exception:
                    pass