import os, json, math
from backend.connection import get_db


# Local environment evaluation to avoid circular import issues with app.py
raw_env = os.environ.get('PORTFOLIO_MODE', 'NOT_SET')
IS_PORTFOLIO = raw_env.lower() in ('true', '1', 't')

_PORTFOLIO_CACHE = None

def _load_portfolio_data(key=None):
    global _PORTFOLIO_CACHE
    try:
        if _PORTFOLIO_CACHE is None:
            with open('data.json', 'r', encoding='utf-8') as f:
                _PORTFOLIO_CACHE = json.load(f)
        data = _PORTFOLIO_CACHE
        return data.get(key, []) if key else data
    except Exception:
        return []

def fetch_core_videos_portfolio(page=1, search_q='', sort_by='video_id', order='DESC', status_filter='all', limit=50):
    """
    Simulates SQL filtering, GROUP_CONCAT joins, dynamic sorting, 
    and pagination using data.json snapshot for Portfolio Mode.
    """
    raw_videos = _load_portfolio_data('video')
    raw_junction = _load_portfolio_data('video_showtitle')
    raw_shows = _load_portfolio_data('showtitle')

    # Build reference lookup mapping for shows
    shows_by_id = {str(s.get('title_id')): s.get('title', '') for s in raw_shows if s.get('title_id')}
    
    # Map show assignments per video: {video_id: [(title_id, title_name), ...]}
    video_to_shows = {}
    for j in raw_junction:
        v_id = str(j.get('video_id'))
        t_id = str(j.get('title_id'))
        if t_id in shows_by_id:
            video_to_shows.setdefault(v_id, []).append((t_id, shows_by_id[t_id]))

    # Filter videos
    processed_videos = []
    search_q_clean = search_q.lower().strip()

    for v in raw_videos:
        v_id_str = str(v.get('video_id', ''))
        v_title = v.get('video_title') or ''
        v_status = (v.get('webstatus') or 'undecided').lower()

        # Status filter logic
        if status_filter != 'all':
            if status_filter == 'undecided':
                if v_status not in ('undecided', '', None):
                    continue
            elif v_status != status_filter:
                continue

        # Get assigned shows metadata
        assigned_tuples = sorted(video_to_shows.get(v_id_str, []), key=lambda x: x[1])
        show_titles_str = ", ".join([t[1] for t in assigned_tuples]) if assigned_tuples else None
        show_title_ids_str = ",".join([t[0] for t in assigned_tuples]) if assigned_tuples else None

        # Search query filter logic
        if search_q_clean:
            match_id = v_id_str == search_q_clean
            match_title = search_q_clean in v_title.lower()
            match_show = show_titles_str and (search_q_clean in show_titles_str.lower())
            
            if not (match_id or match_title or match_show):
                continue

        # Construct row dict matching MySQL layout
        v_copy = dict(v)
        v_copy['show_titles'] = show_titles_str
        v_copy['show_title_ids'] = show_title_ids_str
        v_copy['webstatus'] = v_status
        processed_videos.append(v_copy)

    # Sorting Logic
    reverse_flag = (order == 'DESC')

    def get_sort_key(item):
        if sort_by == 'releaseDate':
            return item.get('releaseDate') or ''
        elif sort_by == 'video_title':
            return (item.get('video_title') or '').lower()
        elif sort_by == 'showtitle':
            return (item.get('show_titles') or '').lower()
        else: # video_id
            try:
                return int(item.get('video_id', 0))
            except ValueError:
                return 0

    processed_videos.sort(key=get_sort_key, reverse=reverse_flag)

    # Pagination calculations
    total_items = len(processed_videos)
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
    offset = (page - 1) * limit
    paginated_videos = processed_videos[offset:offset + limit]

    # Format all_shows dropdown list
    all_shows = sorted([{'title_id': s.get('title_id'), 'title': s.get('title')} for s in raw_shows], key=lambda x: str(x['title']).lower())

    return {
        'videos': paginated_videos,
        'all_shows': all_shows,
        'total_items': total_items,
        'total_pages': total_pages
    }

def fetch_core_videos(page=1, search_q='', sort_by='video_id', order='DESC', status_filter='all', limit=50):
    """
    Fetches paginated video records with their associated show titles 
    from MySQL, applies dynamic filtering, and returns pagination metadata.
    """
    cursor = get_db()
    if not cursor:
        return {'videos': [], 'all_shows': [], 'total_items': 0, 'total_pages': 1}

    try:
        offset = (page - 1) * limit

        # Validate sorting column map to prevent SQL Injection
        valid_sorts = {
            'video_id': 'v.video_id',
            'releaseDate': 'v.releaseDate',
            'video_title': 'v.video_title',
            'showtitle': 'show_titles'
        }
        sort_column = valid_sorts.get(sort_by, 'v.video_id')
        if order not in ['ASC', 'DESC']:
            order = 'DESC'

        # Build dynamic search parameters
        where_clauses = []
        params = []

        if search_q:
            if search_q.isdigit():
                where_clauses.append("(v.video_id = %s OR v.video_title LIKE %s OR st.title LIKE %s)")
                params.extend([int(search_q), f"%{search_q}%", f"%{search_q}%"])
            else:
                where_clauses.append("(v.video_title LIKE %s OR st.title LIKE %s)")
                params.extend([f"%{search_q}%", f"%{search_q}%"])

        valid_statuses = ['show', 'timeline', 'ghost', 'archived', 'undecided']
        if status_filter in valid_statuses:
            if status_filter == 'undecided':
                where_clauses.append("(v.webstatus = 'undecided' OR v.webstatus IS NULL)")
            else:
                where_clauses.append("v.webstatus = %s")
                params.append(status_filter)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Fetch total count for pagination calculations
        count_query = f"""
            SELECT COUNT(DISTINCT v.video_id) as total
            FROM video v
            LEFT JOIN video_showtitle vst ON v.video_id = vst.video_id
            LEFT JOIN showtitle st ON vst.title_id = st.title_id
            {where_sql}
        """
        cursor.execute(count_query, params)
        count_res = cursor.fetchone()
        total_items = count_res['total'] if count_res else 0
        total_pages = math.ceil(total_items / limit) if total_items > 0 else 1

        # Fetch paginated videos list
        query = f"""
            SELECT 
                v.video_id,
                v.video_title,
                v.releaseDate,
                v.webstatus,
                GROUP_CONCAT(st.title ORDER BY st.title SEPARATOR ', ') AS show_titles,
                GROUP_CONCAT(st.title_id ORDER BY st.title SEPARATOR ',') AS show_title_ids
            FROM video v
            LEFT JOIN video_showtitle vst ON v.video_id = vst.video_id
            LEFT JOIN showtitle st ON vst.title_id = st.title_id
            {where_sql}
            GROUP BY v.video_id, v.video_title, v.releaseDate, v.webstatus
            ORDER BY {sort_column} {order}, v.video_id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        videos = cursor.fetchall()

        # Fetch show titles list for reassignment modal dropdown
        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title ASC")
        all_shows = cursor.fetchall()

        return {
            'videos': videos,
            'all_shows': all_shows,
            'total_items': total_items,
            'total_pages': total_pages
        }
    finally:
        cursor.close()

def process_video_action(action, video_id, data):
    """
    Processes updates and deletions for core video records in live MySQL database.
    """
    cursor = get_db()
    if not cursor:
        return False, "Database connection error."

    try:
        if action == 'update_status':
            new_status = data.get('webstatus')
            cursor.execute("UPDATE video SET webstatus = %s WHERE video_id = %s", (new_status, video_id))

        elif action == 'update_shows':
            title_ids = data.get('title_ids', [])
            cursor.execute("DELETE FROM video_showtitle WHERE video_id = %s", (video_id,))
            for tid in title_ids:
                cursor.execute("INSERT INTO video_showtitle (video_id, title_id) VALUES (%s, %s)", (video_id, tid))

        elif action == 'delete_video':
            # Database CASCADE constraints handle junction cleanup automatically
            cursor.execute("DELETE FROM video WHERE video_id = %s", (video_id,))

        else:
            return False, "Invalid action specified"

        connection.commit()
        return True, None
    except Exception as e:
        connection.rollback()
        return False, str(e)
    finally:
        cursor.close()