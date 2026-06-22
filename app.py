from flask import Flask, render_template, url_for, request, redirect, jsonify, flash
import os, json
from typing import Any
from collections import OrderedDict
from datetime import datetime


# ====================================================================
# DATABASE CONNECTION GUARD & SETUP
# ====================================================================

raw_env_value = os.environ.get('PORTFOLIO_MODE', 'NOT_SET')

# Cleanly parse the variable. If it's missing or set to False, this evaluates to False (Local Mode)
IS_PORTFOLIO = raw_env_value.lower() in ('true', '1', 't')

try:
    import db_connect as db
    import backend.connection as con
    import backend.adminputforms as forms
    import backend.admchrono as chrono
    import backend.admtimeline as time
    import backend.admentities as entity

except ImportError as e:
    print("\n" + "!"*60)
    print(f"CRITICAL IMPORT FAILURE: {str(e)}")
    print("!"*60 + "\n")
    # keeps deployment alive online when running completely stateless
    db = con = forms = chrono = time = entity = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key_123")

# Inject mode into all templates automatically
@app.context_processor
def inject_portfolio_status():
    return dict(is_portfolio=IS_PORTFOLIO)

@app.template_filter('format_date')
def format_date_filter(value, format_string='%Y-%m-%d'):
    """Safely formats both SQL date objects and Portfolio string dates in HTML."""
    if not value:
        return ""
    
    # if it's already a string (portfolio mode), convert it to a date first
    if isinstance(value, str):
        try:
            # adjust '%Y-%m-%d' if JSON strings use a different pattern
            return datetime.strptime(value.split()[0], '%Y-%m-%d').strftime(format_string)
        except ValueError:
            return value # fallback to raw text if parsing fails
            
    # if it's a real datetime/date object (local mode)
    try:
        return value.strftime(format_string)
    except AttributeError:
        return str(value)


@app.before_request
def handle_portfolio_intercepts():
    """
    Global interceptor for Portfolio Staging Mode.
    Ensures active local database pings, or safely mocks POST endpoints to keep UI alive.
    """
    # if live online, intercept write routes to act as a secure Admin Sandbox
    if IS_PORTFOLIO:
        if request.method == "POST":
            if request.is_json:
                return jsonify({"success": True, "message": "Demo Mode: Changes simulated successfully."})
            flash("Sandbox Mode: Structural edits are simulated without modifications.", "success")
            return redirect(request.path)
        return  # allow standard GET requests to fallback to reading template assets

    # local mode: keep database connection alive across background lifecycles
    if db and getattr(db, 'connection', None):
        try:
            db.connection.ping(reconnect=True)
        except Exception:
            try:
                db.connection = db.create_connection()
            except Exception:
                pass

def load_portfolio_data(key=None):
    """
    Helper to read data from the frozen data.json snapshot file during Portfolio Mode.
    """

    try:
        # assumes data.json lives in root workspace folder
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            raw_list = data.get(key, []) if key else data
            
            # If the rows come back as raw lists instead of dicts, map them to explicit dict profiles
            if raw_list and isinstance(raw_list, list) and isinstance(raw_list[0], list):
                if key == 'songs':
                    return [{'song_id': r[0], 'songtitle': r[1], 'artist': r[2], 'album': r[3]} for r in raw_list]
                if key == 'showtitle':
                    return [{'title_id': r[0], 'title': r[1], 'releaseYear': r[2]} for r in raw_list]
            return raw_list
    except Exception:
        return []


# ====================================================================
# CORE ROUTES
# ====================================================================

@app.route('/')
def home():
    return render_template('admdashboard.html')

@app.route('/addshow', methods=['GET', 'POST'])
def addshow():
    if request.method == "POST":
        return forms.add_show()
    
    if IS_PORTFOLIO:
        return render_template('admaddshow.html', 
                               categories=load_portfolio_data('category'), 
                               groups=load_portfolio_data('kgroups'), 
                               members=load_portfolio_data('members'))

    cursor = con.get_db()
    if not cursor:
        return render_template('admaddshow.html', categories=[], groups=[], members=[])

    try:
        cursor.execute("SELECT category_id, category_name FROM category ORDER BY category_id")
        categories = cursor.fetchall()

        cursor.execute("SELECT group_id, group_name FROM kgroups")
        groups = cursor.fetchall()

        cursor.execute("""
            SELECT m.member_id, m.member_name, GROUP_CONCAT(g.group_name SEPARATOR ', ') AS `groups`
            FROM members m
            LEFT JOIN member_groups mg ON m.member_id = mg.member_id
            LEFT JOIN kgroups g ON mg.group_id = g.group_id
            GROUP BY m.member_id, m.member_name
            ORDER BY member_name           
        """)
        members = cursor.fetchall()
        
        return render_template('admaddshow.html',
                               categories=categories, groups=groups, members=members)

    except Exception:
        return render_template('admaddshow.html', categories=[], groups=[], members=[])
        
    finally:
        cursor.close()

@app.route('/addvideo', methods=['GET', 'POST'])
def addvideo():
    if request.method == "POST":
        return forms.add_video()

    if IS_PORTFOLIO:
        return render_template('admaddvideo.html', 
                               shows=load_portfolio_data('showtitle'), 
                               groups=load_portfolio_data('kgroups'), 
                               members=load_portfolio_data('members'), 
                               mc_members_list=load_portfolio_data('mc_members_list'), 
                               mcs=load_portfolio_data('musicshowmc'), 
                               tags=load_portfolio_data('livestreamtags'))

    cursor = con.get_db()
    if not cursor:
        return render_template('admaddvideo.html', shows=[], groups=[], members=[], mc_members_list=[], mcs=[], tags=[])

    try:
        # shows dropdown
        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title")
        shows = cursor.fetchall()

        # groups dropdown
        cursor.execute("SELECT group_id, group_name FROM kgroups ORDER BY group_name")
        groups = cursor.fetchall()

        # members dropdown
        cursor.execute("""
            SELECT m.member_id, m.member_name, GROUP_CONCAT(g.group_name SEPARATOR ', ') AS `groups`
            FROM members m
            LEFT JOIN member_groups mg ON m.member_id = mg.member_id
            LEFT JOIN kgroups g ON mg.group_id = g.group_id
            GROUP BY m.member_id, m.member_name
            ORDER BY m.member_name
        """)
        members = cursor.fetchall()

        # members dropdown (flattened for mc)
        cursor.execute("""
            SELECT m.member_id, m.member_name, g.group_name, g.group_id
            FROM members m
            JOIN member_groups mg ON m.member_id = mg.member_id
            JOIN kgroups g ON mg.group_id = g.group_id
            ORDER BY g.group_name, m.member_name
        """)
        mc_members_list = cursor.fetchall()

        # mushow mc dropdown
        cursor.execute("SELECT mc_id, mc_pairname FROM musicshowmc ORDER BY mc_pairname")
        mcs = cursor.fetchall()

        # livestream tags dropdown
        cursor.execute("SELECT tag_id, tag_name FROM livestreamtags ORDER BY tag_name")
        tags = cursor.fetchall()

        return render_template('admaddvideo.html', 
                               shows=shows, groups=groups, members=members,
                               mc_members_list=mc_members_list, mcs=mcs, tags=tags)

    except Exception:
        return render_template('admaddvideo.html', shows=[], groups=[], members=[], mc_members_list=[], mcs=[], tags=[])

    finally:
        cursor.close()

@app.route('/addwatchtimeline', methods=['GET', 'POST'])
def addtimeline():
    if request.method == 'POST':
        if not IS_PORTFOLIO:
            chrono.add_totimeline(request.form)
        return redirect(url_for('addtimeline'))

    return render_template('admaddtimeline.html')


# ====================================================================
# ENTITY MANAGEMENT
# ====================================================================

@app.route('/entityHGT', methods=['GET', 'POST'])
def entityhgt():
    if request.method == 'POST':
        action = request.form.get('action')
        
        # group actions
        if action == 'insert_group':
            entity.insert_group(request.form)
        elif action == 'update_group':
            group_id = request.form.get('group_id')
            entity.update_group(group_id, request.form)

        # member actions
        elif action == 'insert_member':
            entity.insert_member(request.form)
        elif action == 'update_member':
            member_id = request.form.get('member_id')
            entity.update_member_groups(member_id, request.form)

        return redirect(url_for('entityhgt'))

    if IS_PORTFOLIO:
        portfolio_groups = load_portfolio_data('kgroups')
        portfolio_members = load_portfolio_data('members')
        
        # 1. Build an ID-to-Name lookup dictionary map to resolve parent details instantly
        group_id_to_name = {str(g.get('group_id')): g.get('group_name') for g in portfolio_groups if g.get('group_id')}
        
        # 2. Inject parent_name into the groups dataset explicitly
        processed_groups = []
        for g in portfolio_groups:
            g_copy = dict(g)
            p_id = str(g.get('parent_id') or '')
            if p_id and p_id != 'None' and p_id in group_id_to_name:
                g_copy['parent_name'] = group_id_to_name[p_id]
            else:
                g_copy['parent_name'] = None
            processed_groups.append(g_copy)
            
        # 3. Build a reverse group map to resolve names to unique IDs instantly
        group_name_to_id = {str(g.get('group_name')): str(g.get('group_id')) for g in portfolio_groups if g.get('group_name')}
        
        processed_members = []
        for m in portfolio_members:
            m_copy = dict(m)
            
            # Extract group name string from data.json profile snapshot
            g_string = m.get('groups') or ''
            m_copy['current_groups'] = g_string
            
            # Resolve active names back to raw string IDs for checkbox evaluations
            active_ids = []
            if g_string:
                for name in [name.strip() for name in g_string.split(',')]:
                    if name in group_name_to_id:
                        active_ids.append(group_name_to_id[name])
                        
            m_copy['current_group_ids'] = ",".join(active_ids)
            processed_members.append(m_copy)

        return render_template('admentityhgt.html', 
                               groups=processed_groups, 
                               members=processed_members)
    
    try:
        groups, members = entity.fetch_group_member_data()
        return render_template('admentityhgt.html', groups=groups, members=members)
    
    except Exception:
        return render_template('admentityhgt.html', groups=[], members=[])

@app.route('/entityMC', methods=['GET', 'POST'])
def entitymc():
    if request.method == 'POST':
        action = request.form.get('action')
        mc_id = request.form.get('mc_id')
        
        if action == 'insert':
            entity.insert_mc_pair(request.form)
        elif action == 'update':
            entity.update_mc_full(mc_id, request.form)
            
        return redirect(url_for('entitymc'))
    
    if IS_PORTFOLIO:
        return render_template('admentitymc.html', 
                               pairings=load_portfolio_data('mc_pairings'), 
                               shows=load_portfolio_data('showtitle'), 
                               members=load_portfolio_data('members'))
    
    cursor = con.get_db()
    if not cursor:
        return render_template('admentitymc.html', pairings=[], shows=[], members=[])

    try:
        # main display table
        cursor.execute("""
            SELECT mc.mc_id, mc.mc_pairname, st.title, st.title_id,
                   GROUP_CONCAT(m.member_name SEPARATOR ', ') AS member_names,
                   GROUP_CONCAT(m.member_id SEPARATOR ',') AS member_ids
            FROM musicshowmc mc
            LEFT JOIN mushow_mcs mm ON mc.mc_id = mm.mc_id
            LEFT JOIN showtitle st ON mm.mushow_id = st.title_id
            LEFT JOIN mc_members mcm ON mc.mc_id = mcm.mc_id
            LEFT JOIN members m ON mcm.member_id = m.member_id
            GROUP BY mc.mc_id, mc.mc_pairname, st.title, st.title_id
            ORDER BY mc.mc_pairname ASC
        """)
        pairings = cursor.fetchall()

        # music shows dropdown
        cursor.execute("SELECT title_id, title FROM showtitle WHERE title_id IN (1,2,3,4,5,6) ORDER BY title")
        shows = cursor.fetchall()

        # flattened members dropdown
        cursor.execute("""
            SELECT m.member_id, m.member_name, g.group_name
            FROM members m
            JOIN member_groups mg ON m.member_id = mg.member_id
            JOIN kgroups g ON mg.group_id = g.group_id
            ORDER BY m.member_name ASC, g.group_name ASC
        """)
        members = cursor.fetchall()

        return render_template('admentitymc.html', pairings=pairings, shows=shows, members=members)

    except Exception:
        return render_template('admentitymc.html', pairings=[], shows=[], members=[])

    finally:
        cursor.close()

@app.route('/entityL', methods=['GET', 'POST'])
def entityl():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'insert_tag':
            entity.insert_tag(request.form)
        elif action == 'update_tag':
            entity.update_tag(request.form.get('tag_id'), request.form)
        elif action == 'insert_season':
            entity.insert_season(request.form)
        elif action == 'update_season':
            entity.update_season(request.form.get('title_id'), request.form.get('s_num'), request.form)
            
        return redirect(url_for('entityl', q=request.args.get('q')))

    search_q = request.args.get('q')

    if IS_PORTFOLIO:
        raw_tags = load_portfolio_data('livestreamtags')
        raw_seasons = load_portfolio_data('season_names')
        portfolio_groups = load_portfolio_data('kgroups')
        portfolio_shows = load_portfolio_data('showtitle')
        
        # 1. Build rapid reference mapping lookups
        groups_lookup = {str(g.get('group_id')): g.get('group_name') for g in portfolio_groups if g.get('group_id')}
        shows_lookup = {str(s.get('title_id')): s.get('title') for s in portfolio_shows if s.get('title_id')}
        
        # 2. Simulate relational JOIN queries for the Livestream Tags grid
        processed_tags = []
        for tag in raw_tags:
            tag_copy = dict(tag)
            g_id = str(tag.get('group_id') or '')
            
            # Attaches group_name to the dictionary layout dynamically
            tag_copy['group_name'] = groups_lookup.get(g_id) if g_id and g_id != 'None' else None
            processed_tags.append(tag_copy)
            
        # 3. Simulate relational JOIN queries for the Season Labels grid
        processed_seasons = []
        for season in raw_seasons:
            season_copy = dict(season)
            t_id = str(season.get('title_id') or '')
            
            # Attaches the string parent title value natively
            season_copy['title'] = shows_lookup.get(t_id) if t_id and t_id != 'None' else "Unknown Show"
            processed_seasons.append(season_copy)

        # 4. Handle context filter query adjustments safely
        if search_q:
            q_clean = search_q.strip().lower()
            processed_tags = [t for t in processed_tags if q_clean in str(t.get('tag_name', '')).lower() or q_clean in str(t.get('group_name', '')).lower()]
            processed_seasons = [s for s in processed_seasons if q_clean in str(s.get('season_name', '')).lower() or q_clean in str(s.get('title', '')).lower()]
            
        return render_template('admentityl.html', 
                               tags=processed_tags, 
                               seasons=processed_seasons, 
                               groups=portfolio_groups, 
                               shows=portfolio_shows, 
                               search_q=search_q)

    try:
        tags, seasons, groups, shows = entity.fetch_entity_l_data(search_q)
        return render_template('admentityl.html', 
                               tags=tags, seasons=seasons, 
                               groups=groups, shows=shows, search_q=search_q)
    
    except Exception as e:
        print(f"!!! Database error fetching entity_l data list: {str(e)}")
        return render_template('admentityl.html', tags=[], seasons=[], groups=[], shows=[], search_q=search_q)

@app.route('/entityS', methods=['GET', 'POST'])
def entitys():
    if request.method == 'POST':
        action = request.form.get('action')
        form_data = {
            'title': request.form.get('title'),
            'artist': request.form.get('artist'),
            'album': request.form.get('album'),
            'track_number': request.form.get('track_number') or 1,
            'spotify': request.form.get('spotify') or None,
            'youtube': request.form.get('youtube') or None
        }

        if action == 'insert':
            entity.insert_song(form_data)
        elif action == 'update':
            entity.update_song(request.form.get('song_id'), form_data)
            
        return redirect(url_for('entitys', q=request.args.get('q')))

    search_q = request.args.get('q')

    if IS_PORTFOLIO:
        songs = load_portfolio_data('songs')
        if search_q:
            songs = [s for s in songs if search_q in s.get('songtitle', '').lower() or search_q in s.get('artist', '').lower()]
        return render_template('admentitys.html', songs=songs, search_q=search_q)

    try:
        songs = entity.fetch_songs(search_q)
        return render_template('admentitys.html', 
                            songs=songs, search_q=search_q)
    
    except Exception:
        return render_template('admentitys.html', 
                            songs=[], search_q=search_q)


# ====================================================================
# BATCH GRID WORKFLOWS
# ====================================================================

@app.route('/manage/batch-edit')
def batchedit():
    if IS_PORTFOLIO:
        return render_template('admbatchedit.html', 
                               all_shows=load_portfolio_data('showtitle'), 
                               categories=load_portfolio_data('category'), 
                               groups=load_portfolio_data('kgroups'), 
                               members=load_portfolio_data('members'), 
                               mc_members_list=load_portfolio_data('mc_members_list'), 
                               mcs=load_portfolio_data('musicshowmc'), 
                               tags=load_portfolio_data('livestreamtags'), 
                               songs=load_portfolio_data('songs'))
    
    cursor = con.get_db() 
    if not cursor:
        return render_template('admbatchedit.html', all_shows=[], categories=[], groups=[], members=[], mc_members_list=[], mcs=[], tags=[], songs=[])
    
    try:
        # left sidebar navigation
        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title ASC")
        all_shows = cursor.fetchall()
        
        # metadata & ownership section
        cursor.execute("SELECT category_id, category_name FROM category ORDER BY category_id")
        categories = cursor.fetchall()
        cursor.execute("SELECT group_id, group_name FROM kgroups ORDER BY group_name")
        groups = cursor.fetchall()
        cursor.execute("""
            SELECT m.member_id, m.member_name, GROUP_CONCAT(g.group_name SEPARATOR ', ') as group_names
            FROM members m
            LEFT JOIN member_groups mg ON m.member_id = mg.member_id
            LEFT JOIN kgroups g ON mg.group_id = g.group_id
            GROUP BY m.member_id ORDER BY m.member_name ASC
        """)
        members = cursor.fetchall()

        # relational brush tabs
        cursor.execute("""
            SELECT m.member_id, m.member_name, g.group_id, g.group_name
            FROM members m
            JOIN member_groups mg ON m.member_id = mg.member_id
            JOIN kgroups g ON mg.group_id = g.group_id
            ORDER BY m.member_name ASC
        """)
        mc_members_list = cursor.fetchall()
        cursor.execute("SELECT mc_id, mc_pairname FROM musicshowmc ORDER BY mc_pairname")
        mcs = cursor.fetchall()
        cursor.execute("SELECT tag_id, tag_name FROM livestreamtags ORDER BY tag_name")
        tags = cursor.fetchall()
        cursor.execute("SELECT song_id, songtitle, artist FROM songs ORDER BY artist, songtitle")
        songs = cursor.fetchall()
        
        return render_template('admbatchedit.html', 
                               all_shows=all_shows, categories=categories, 
                               groups=groups, members=members, mc_members_list=mc_members_list,
                               mcs=mcs, tags=tags, songs=songs)
                               
    except Exception:
        return render_template('admbatchedit.html', all_shows=[], categories=[], groups=[], 
                               members=[], mc_members_list=[], mcs=[], tags=[], songs=[])
        
    finally:
        cursor.close()

@app.route('/manage/batch/get-show-data/<int:show_id>')
def get_batch_data(show_id):
    if IS_PORTFOLIO:
        all_shows = load_portfolio_data('showtitle')
        selected_show = next((s for s in all_shows if s.get('title_id') == show_id), {})
        
        # 1. Pull the associated category IDs and ownership records
        show_cats_data = load_portfolio_data('showtitle_category')
        cats = [c.get('category_id') for c in show_cats_data if c.get('title_id') == show_id]
        
        show_owns_data = load_portfolio_data('showownership')
        owns = [
            {'group_id': o.get('group_id'), 'member_id': o.get('member_id')} 
            for o in show_owns_data if o.get('title_id') == show_id
        ]
        
        # 2. Map video IDs belonging to this show_id from your junction blueprint
        junction_data = load_portfolio_data('video_showtitle')
        allowed_video_ids = {j.get('video_id') for j in junction_data if j.get('title_id') == show_id}
        
        # 3. Pull relation lookup footprints to replicate MySQL EXISTS() subqueries
        host_vids = {h.get('video_id') for h in load_portfolio_data('videohost')}
        guest_vids = {g.get('video_id') for g in load_portfolio_data('videoguest')}
        tiny_vids = {t.get('video_id') for t in load_portfolio_data('tinyguest')}
        mc_vids = {m.get('video_id') for m in load_portfolio_data('videomushowmc')}
        live_vids = {l.get('video_id') for l in load_portfolio_data('videolivetags')}
        music_vids = {s.get('video_id') for s in load_portfolio_data('video_music_recs')}
        
        # 4. Filter down and inject active relationship tracking flags onto the rows
        all_videos = load_portfolio_data('video')
        videos = []
        for v in all_videos:
            v_id = v.get('video_id')
            if v.get('webstatus') == 'show' and v_id in allowed_video_ids:
                # Append live binary state checks so JavaScript updates your panel templates
                v_copy = dict(v)
                v_copy['has_h'] = 1 if v_id in host_vids else 0
                v_copy['has_g'] = 1 if v_id in guest_vids else 0
                v_copy['has_t'] = 1 if v_id in tiny_vids else 0
                v_copy['has_m'] = 1 if v_id in mc_vids else 0
                v_copy['has_l'] = 1 if v_id in live_vids else 0
                v_copy['has_s'] = 1 if v_id in music_vids else 0
                videos.append(v_copy)
                
        return jsonify({'show': selected_show, 'cats': cats, 'owns': owns, 'videos': videos})
    
    cursor = con.get_db() 
    if not cursor:
        return jsonify({'show': {}, 'cats': [], 'owns': [], 'videos': []})
    
    try:
        cursor.execute("SELECT * FROM showtitle WHERE title_id = %s", (show_id,))
        show = cursor.fetchone()
        cursor.execute("SELECT category_id FROM showtitle_category WHERE title_id = %s", (show_id,))
        cats = [r['category_id'] for r in cursor.fetchall()]
        cursor.execute("SELECT group_id, member_id FROM showownership WHERE title_id = %s", (show_id,))
        owns = cursor.fetchall()
        
        # checks if a record exists in the relation tables
        cursor.execute("""
            SELECT v.*, 
                   EXISTS(SELECT 1 FROM videohost WHERE video_id = v.video_id) as has_h,
                   EXISTS(SELECT 1 FROM videoguest WHERE video_id = v.video_id) as has_g,
                   EXISTS(SELECT 1 FROM tinyguest WHERE video_id = v.video_id) as has_t,
                   EXISTS(SELECT 1 FROM videomushowmc WHERE video_id = v.video_id) as has_m,
                   EXISTS(SELECT 1 FROM videolivetags WHERE video_id = v.video_id) as has_l,
                   EXISTS(SELECT 1 FROM video_music_recs WHERE video_id = v.video_id) as has_s
            FROM video v
            JOIN video_showtitle vs ON v.video_id = vs.video_id
            WHERE vs.title_id = %s AND v.webstatus = 'show'
            ORDER BY 
                v.season IS NULL, CAST(NULLIF(v.season, '') AS UNSIGNED), v.season, 
                v.releaseDate IS NULL, v.releaseDate,
                v.episodeNumber IS NULL, CAST(NULLIF(v.episodeNumber, '') AS UNSIGNED), v.episodeNumber,
                v.title_extras IS NOT NULL, v.title_extras ASC,
                v.video_id ASC
        """, (show_id,))
        videos = cursor.fetchall()

        return jsonify({'show': show, 'cats': cats, 'owns': owns, 'videos': videos})
    
    finally:
        cursor.close()

@app.route('/manage/batch/save-show', methods=['POST'])
def save_batch_show():
    data = request.json
    s_id = data.get('title_id')
    
    def clean_int(val):
        if val is None or str(val).strip() == "": return None
        try: return int(val)
        except: return None

    cursor = con.get_db()
    if not cursor:
        return jsonify(success=True)

    try:
        watch_status = data.get('watchStatus')
        if watch_status == 'None' or not watch_status:
            watch_status = None # This sends a true NULL to the database

        # update show metadata
        cursor.execute("""
            UPDATE showtitle SET title=%s, watchStatus=%s, releaseYear=%s, 
            totalSeasons=%s, totalEpisodes=%s, variety=%s, title_img=%s, season_order=%s 
            WHERE title_id=%s
        """, (data.get('title'), watch_status, data.get('releaseYear'),
              clean_int(data.get('totalSeasons')), clean_int(data.get('totalEpisodes')), 
              1 if data.get('variety') else 0, data.get('title_img'), data.get('season_order'), s_id))
        
        # sync categories & ownership
        cursor.execute("DELETE FROM showtitle_category WHERE title_id = %s", (s_id,))
        for cid in data.get('categories', []):
            cursor.execute("INSERT INTO showtitle_category (title_id, category_id) VALUES (%s, %s)", (s_id, cid))

        cursor.execute("DELETE FROM showownership WHERE title_id = %s", (s_id,))
        grps, mems = data.get('groups', []), data.get('members', [])
        if grps:
            for gid in grps:
                found = False
                for mid in mems:
                    cursor.execute("SELECT 1 FROM member_groups WHERE group_id = %s AND member_id = %s", (gid, mid))
                    if cursor.fetchone():
                        cursor.execute("INSERT INTO showownership (title_id, group_id, member_id) VALUES (%s, %s, %s)", (s_id, gid, mid))
                        found = True
                if not found: 
                    cursor.execute("INSERT INTO showownership (title_id, group_id, member_id) VALUES (%s, %s, NULL)", (s_id, gid))
        else:
            for mid in mems: 
                cursor.execute("INSERT INTO showownership (title_id, group_id, member_id) VALUES (%s, %s, %s)", (s_id, None, mid))
        
        if db.connection:
            db.connection.commit()
        return jsonify(success=True)

    except Exception as e:
        if db.connection:
            db.connection.rollback()
        return jsonify(success=False, error=str(e)), 500
    
    finally:
        cursor.close()

# stamp episode metadata
@app.route('/manage/batch/save-single-video', methods=['POST'])
def save_batch_single():
    v = request.json
    
    cursor = con.get_db()
    if not cursor:
        return jsonify(success=True)
    
    try:
        cursor.execute("""
            UPDATE video SET video_title=%s, releaseDate=%s, season=%s, episodeNumber=%s, 
            title_extras=%s, video_notes=%s, is_variety=%s WHERE video_id=%s
        """, (v['title'], v['date'] if v['date'] else None, v['season'], v['ep'], 
              v['extras'] or None, v['notes'] or None, 1 if v['is_var'] else 0, v['id']))
        db.connection.commit()
        return jsonify({"success": True})
    
    finally:
        cursor.close()

# stamp HGTMLS relation
@app.route('/manage/batch/stamp-relation', methods=['POST'])
def stamp_batch_relation():
    data = request.json
    v_id, letter, ids = data.get('video_id'), data.get('table'), data.get('ids')
    table_map = {'H':'videohost', 'G':'videoguest', 'T':'tinyguest', 'M':'videomushowmc', 'L':'videolivetags', 'S':'video_music_recs'}
    
    cursor = con.get_db()
    if not cursor:
        return jsonify(success=True)
    
    try:
        cursor.execute(f"DELETE FROM {table_map[letter]} WHERE video_id = %s", (v_id,))
        bg = [i[1:] for i in ids if i.startswith('g')]
        bm = [i[1:] for i in ids if i.startswith('m')]
        bmc = [i[2:] for i in ids if i.startswith('mc')]
        bt = [i[1:] for i in ids if i.startswith('t')]
        bs = [i[1:] for i in ids if i.startswith('s')]
        
        if letter in ['H', 'G', 'T']:
            for gid in bg:
                found = False
                for mid in bm:
                    cursor.execute("SELECT 1 FROM member_groups WHERE group_id = %s AND member_id = %s", (gid, mid))
                    if cursor.fetchone():
                        cursor.execute(f"INSERT INTO {table_map[letter]} (video_id, group_id, member_id) VALUES (%s, %s, %s)", (v_id, gid, mid))
                        found = True
                if not found:
                    cursor.execute(f"INSERT INTO {table_map[letter]} (video_id, group_id, member_id) VALUES (%s, %s, NULL)", (v_id, gid))
            for mid in bm:
                cursor.execute(f"SELECT 1 FROM {table_map[letter]} WHERE video_id = %s AND member_id = %s", (v_id, mid))
                if not cursor.fetchone():
                    cursor.execute(f"INSERT INTO {table_map[letter]} (video_id, group_id, member_id) VALUES (%s, %s, %s)", (v_id, None, mid))
        
        elif letter == 'M':
            mparts = [i[1:].split('_') for i in ids if i.startswith('m')]
            for mc_id in bmc:
                for pts in mparts:
                    mid, gid = pts[0], (pts[1] if len(pts)>1 else None)
                    cursor.execute("INSERT IGNORE INTO videomushowmc (video_id, mc_id, member_id, group_id) VALUES (%s, %s, %s, %s)", (v_id, mc_id, mid, gid))
        
        elif letter == 'L':
            for tid in bt: 
                cursor.execute("INSERT INTO videolivetags (video_id, tag_id) VALUES (%s, %s)", (v_id, tid))
        
        elif letter == 'S':
            for idx, sid in enumerate(bs): 
                cursor.execute("INSERT INTO video_music_recs (video_id, song_id, sort_order) VALUES (%s, %s, %s)", (v_id, sid, idx))
        
        if db.connection:
            db.connection.commit()
        return jsonify({"success": True})
    
    finally:
        cursor.close()

@app.route('/manage/batch/get-relations/<letter>/<int:video_id>')
def get_batch_relations(letter, video_id):
    if IS_PORTFOLIO:
        table_map = {
            'H': 'videohost', 
            'G': 'videoguest', 
            'T': 'tinyguest', 
            'M': 'videomushowmc', 
            'L': 'videolivetags', 
            'S': 'video_music_recs'
        }
        
        target_key = table_map.get(letter)
        if not target_key:
            return jsonify({"current_relations": []})
            
        junction_rows = load_portfolio_data(target_key)
        matched_ids = []

        # Coerce target to string to defeat potential string/integer JSON key mismatch trap
        search_vid = str(video_id)
        
        # Filter down rows that match this specific video clip instance
        for row in junction_rows:
            if not row:
                continue
                
            # --- SCENARIO A: Row is an array/tuple ---
            if isinstance(row, (list, tuple)):
                row_vid = str(row[0]) # In all your junction tables, video_id is column index 0
                if row_vid == search_vid:
                    if letter in ['H', 'G', 'T']:
                        # Primary Key structure layout check: video_id, group_id, member_id
                        if len(row) > 1 and row[1]: matched_ids.append(f"g{row[1]}")
                        if len(row) > 2 and row[2]: matched_ids.append(f"m{row[2]}")
                    elif letter == 'M':
                        # videomushowmc column sequence order: video_id, mc_id, member_id, group_id
                        if len(row) > 1 and row[1]: matched_ids.append(f"mc{row[1]}")
                        mid = row[2] if len(row) > 2 else None
                        gid = row[3] if len(row) > 3 else ''
                        if mid: matched_ids.append(f"m{mid}_{gid}")
                    elif letter == 'L':
                        # videolivetags layout: video_id, tag_id
                        if len(row) > 1 and row[1]: matched_ids.append(f"t{row[1]}")
                    elif letter == 'S':
                        # video_music_recs table: video_id, song_id, created_at, sort_order
                        if len(row) > 1 and row[1]: matched_ids.append(f"s{row[1]}")

            # --- SCENARIO B: Row is a standard dictionary object ---
            elif isinstance(row, dict):
                clean_row = {str(k).lower(): v for k, v in row.items()}
                row_vid = str(clean_row.get('video_id', ''))
                
                if row_vid == search_vid:
                    if letter in ['H', 'G', 'T']:
                        gid = clean_row.get('group_id')
                        mid = clean_row.get('member_id')
                        if gid: matched_ids.append(f"g{gid}")
                        if mid: matched_ids.append(f"m{mid}")
                    elif letter == 'M':
                        mcid = clean_row.get('mc_id')
                        mid = clean_row.get('member_id')
                        gid = clean_row.get('group_id') or ''
                        if mcid: matched_ids.append(f"mc{mcid}")
                        if mid: matched_ids.append(f"m{mid}_{gid}")
                    elif letter == 'L':
                        tid = clean_row.get('tag_id')
                        if tid: matched_ids.append(f"t{tid}")
                    elif letter == 'S':
                        sid = clean_row.get('song_id')
                        if sid: matched_ids.append(f"s{sid}")
                        
        return jsonify({"current_relations": matched_ids})
    
    cursor = con.get_db() 
    if not cursor:
        return jsonify({"current_relations": [], "error": "Database cursor unavailable."}), 500
    
    res = []

    try:
        if letter in ['H', 'G', 'T']:
            tbl = {'H': 'videohost', 'G': 'videoguest', 'T': 'tinyguest'}[letter]
            cursor.execute(f"""
                SELECT CONCAT('g', group_id) as id FROM {tbl} WHERE video_id = %s AND group_id IS NOT NULL
                UNION 
                SELECT CONCAT('m', member_id) as id FROM {tbl} WHERE video_id = %s AND member_id IS NOT NULL
            """, (video_id, video_id))
            res = cursor.fetchall()
        elif letter == 'M':
            cursor.execute("""
                SELECT CONCAT('mc', mc_id) as id FROM videomushowmc WHERE video_id = %s 
                UNION 
                SELECT CONCAT('m', member_id, '_', IFNULL(group_id, '')) as id FROM videomushowmc WHERE video_id = %s
            """, (video_id, video_id))
            res = cursor.fetchall()
        elif letter == 'L':
            cursor.execute("SELECT CONCAT('t', tag_id) as id FROM videolivetags WHERE video_id = %s", (video_id,))
            res = cursor.fetchall()
        elif letter == 'S':
            cursor.execute("SELECT CONCAT('s', song_id) as id FROM video_music_recs WHERE video_id = %s ORDER BY sort_order ASC", (video_id,))
            res = cursor.fetchall()

        return jsonify({"current_relations": [i['id'] for i in res]})    
    
    except Exception as e:
        return jsonify({"current_relations": [], "error": str(e)}), 500
        
    finally:
        cursor.close()


# ====================================================================
# DATA VIEW TIMELINES
# ====================================================================

@app.route('/sorttimeline')
def sorttimeline():
    selected_year = request.args.get('year', 'all')
    selected_month = request.args.get('month', 'all')

    if IS_PORTFOLIO:
        videos = load_portfolio_data('video')
        # emulate the WHERE constraint
        filtered = [v for v in videos if v.get('webstatus') == 'undecided']

        # emulate distinct database configuration loops for unique sidebar tabs
        years = sorted(list(set(v['releaseDate'][:4] for v in videos if v.get('releaseDate'))), reverse=True)
        
        if selected_year != 'all':
            filtered = [v for v in filtered if v.get('releaseDate', '').startswith(selected_year)]
        if selected_month != 'all' and selected_year != 'all':
            # check string index match for format 'YYYY-MM-DD'
            filtered = [v for v in filtered if v.get('releaseDate', '')[5:7] == selected_month.zfill(2)]
            
        return render_template('admsorttimeline.html', videos=filtered[:100], shows=load_portfolio_data('showtitle'), 
                               years=years, selected_year=selected_year, selected_month=selected_month)

    cursor = con.get_db()
    if not cursor:
        return render_template('admsorttimeline.html', videos=[], shows=[], years=[], selected_year='all', selected_month='all')

    try:
        query = "SELECT video_id, video_title, releaseDate, video_notes, webstatus FROM video WHERE webstatus = 'undecided'"
        params = []

        if selected_year != 'all':
            query += " AND (YEAR(releaseDate) = %s OR releaseDate LIKE %s)"
            params.append(int(selected_year))
            params.append(f"{selected_year}%")
        
        if selected_month != 'all' and selected_year != 'all':
            query += " AND MONTH(releaseDate) = %s"
            params.append(int(selected_month))

        query += " ORDER BY releaseDate ASC LIMIT 100"
        
        cursor.execute(query, params)
        filtered_videos = cursor.fetchall()

        cursor.execute("SELECT DISTINCT YEAR(releaseDate) as year FROM video WHERE webstatus = 'undecided' AND releaseDate IS NOT NULL ORDER BY year DESC")
        all_years = [str(row['year']) for row in cursor.fetchall() if row['year']]

        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title ASC")
        all_shows = cursor.fetchall()

        return render_template('admsorttimeline.html', 
                               videos=filtered_videos, shows=all_shows, years=all_years,
                               selected_year=selected_year, selected_month=selected_month)

    except Exception as e:
        return render_template('admsorttimeline.html', videos=[], shows=[], years=[], 
                               selected_year=selected_year, selected_month=selected_month)

    finally:
        cursor.close()

@app.route('/sortarchtimeline')
def sortarch():
    selected_year = request.args.get('year', 'all')
    selected_month = request.args.get('month', 'all')

    if IS_PORTFOLIO:
        videos = load_portfolio_data('video')
        filtered = [v for v in videos if v.get('webstatus') == 'archived']
        years = sorted(list(set(v['releaseDate'][:4] for v in videos if v.get('releaseDate'))), reverse=True)
        
        if selected_year != 'all':
            filtered = [v for v in filtered if v.get('releaseDate', '').startswith(selected_year)]
        if selected_month != 'all' and selected_year != 'all':
            filtered = [v for v in filtered if v.get('releaseDate', '')[5:7] == selected_month.zfill(2)]
            
        return render_template('admsortarch.html', videos=filtered[:100], shows=load_portfolio_data('showtitle'), 
                               years=years, selected_year=selected_year, selected_month=selected_month)
    
    cursor = con.get_db()
    if not cursor:
        return render_template('admsortarch.html', videos=[], shows=[], years=[], selected_year='all', selected_month='all')

    try:
        query = "SELECT video_id, video_title, releaseDate, video_notes, webstatus FROM video WHERE webstatus = 'archived'"
        params = []

        if selected_year != 'all':
            query += " AND (YEAR(releaseDate) = %s OR releaseDate LIKE %s)"
            params.append(int(selected_year))
            params.append(f"{selected_year}%")

        if selected_month != 'all' and selected_year != 'all':
            query += " AND MONTH(releaseDate) = %s"
            params.append(int(selected_month))

        query += " ORDER BY releaseDate DESC LIMIT 100"
        
        cursor.execute(query, params)
        archived_videos = cursor.fetchall()

        cursor.execute("SELECT DISTINCT YEAR(releaseDate) as year FROM video WHERE webstatus = 'archived' AND releaseDate IS NOT NULL ORDER BY year DESC")
        all_years = [str(row['year']) for row in cursor.fetchall() if row['year']]

        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title ASC")
        all_shows = cursor.fetchall()

        return render_template('admsortarch.html',
                               videos=archived_videos, shows=all_shows, years=all_years,
                               selected_year=selected_year, selected_month=selected_month)

    except Exception as e:
        return render_template('admsortarch.html', videos=[], shows=[], years=[], 
                               selected_year=selected_year, selected_month=selected_month)

    finally:
        cursor.close()

@app.route('/triage/save', methods=['POST'])
def savetriage():
    if IS_PORTFOLIO:
        return jsonify({"message": "Demo Mode: Triaging logic simulated successfully."}), 200
    
    try:
        # extract data parameters from incoming JSON request payload
        data = request.get_json()
        v_id = data.get('video_id')
        status = data.get('status')
        notes = data.get('notes')
        selected_shows = data.get('shows', [])

        success, message = chrono.save_triage(v_id, status, notes, selected_shows)

        if success:
            return jsonify({"message": message}), 200
        else:
            return jsonify({"message": message}), 400
        
    except Exception as e:
        return jsonify({"message": "Internal Database Error processing triage selection.", "error": str(e)}), 500


# ====================================================================
# LIBRARY
# ====================================================================

@app.route('/ktimeline')
def ktimeline():
    selected_groups = request.args.getlist('groups')

    all_videos = time.alltimeline(selected_group_names=selected_groups)

    if IS_PORTFOLIO:   
        return render_template('admktimeline.html', 
                               videos=all_videos, 
                               all_groups=load_portfolio_data('kgroups'), 
                               selected_groups=selected_groups)
    
    cursor = con.get_db()
    if not cursor:
        return render_template('admktimeline.html', 
                               videos=all_videos, 
                               all_groups=[], 
                               selected_groups=selected_groups)
    
    try:
        cursor.execute("SELECT group_name FROM kgroups ORDER BY group_name")
        all_groups = cursor.fetchall()

        return render_template('admktimeline.html',
                               videos=all_videos, 
                               all_groups=all_groups,
                               selected_groups=selected_groups)
                               
    except Exception as e:
        return render_template('admktimeline.html', 
                               videos=all_videos, 
                               all_groups=[], 
                               selected_groups=selected_groups)
                               
    finally:
        cursor.close()

@app.route('/livetimeline')
def livetimeline():
    if IS_PORTFOLIO:
        try:
            # 1. Pull decoupled snapshot data assets
            raw_videos = load_portfolio_data('video')
            junc_show = load_portfolio_data('video_showtitle')
            all_shows = load_portfolio_data('showtitle')
            junc_cat = load_portfolio_data('showtitle_category')
            junc_own = load_portfolio_data('showownership')
            all_groups = load_portfolio_data('kgroups')
            
            vmr_rows = load_portfolio_data('video_music_recs')
            all_songs = load_portfolio_data('songs')

            # 2. Build map structures for O(1) in-memory data joining
            shows_map = {str(s.get('title_id')): s for s in all_shows}
            groups_map = {str(g.get('group_id')): g for g in all_groups}
            songs_map = {str(sg.get('song_id')): sg for sg in all_songs}

            video_to_shows = {}
            for j in junc_show:
                video_to_shows.setdefault(str(j.get('video_id')), []).append(str(j.get('title_id')))

            show_to_cats = {}
            for j in junc_cat:
                show_to_cats.setdefault(str(j.get('title_id')), []).append(int(j.get('category_id') or 0))

            show_to_owners = {}
            for j in junc_own:
                show_to_owners.setdefault(str(j.get('title_id')), []).append(str(j.get('group_id')))

            # 3. Simulate core SQL WHERE filtering matrix clauses
            streams = []
            for v in raw_videos:
                # WHERE v.webstatus = 'show' AND v.releaseDate IS NOT NULL
                if v.get('webstatus') != 'show' or not v.get('releaseDate'):
                    continue

                v_id = str(v.get('video_id'))
                target_show_ids = video_to_shows.get(v_id, [])

                for tid in target_show_ids:
                    # JOIN showtitle_category sc ON s.title_id = sc.title_id WHERE sc.category_id = 12
                    cats = show_to_cats.get(tid, [])
                    if 12 not in cats:
                        continue

                    # JOIN showownership so AND kgroups g
                    g_ids = show_to_owners.get(tid, [])
                    for gid in g_ids:
                        gid_int = int(gid or 0)
                        # WHERE (g.group_id BETWEEN 1 AND 6 OR g.group_id BETWEEN 120 AND 124)
                        if (1 <= gid_int <= 6) or (120 <= gid_int <= 124):
                            g_data = groups_map.get(gid, {})
                            show_data = shows_map.get(tid, {})

                            # Shape row records exactly like a MySQL cursor dictionary row layout
                            streams.append({
                                'video_id': v.get('video_id'),
                                'video_title': v.get('video_title'),
                                'releaseDate': v.get('releaseDate'),
                                'video_notes': v.get('video_notes'),
                                'origin_show': show_data.get('title'),
                                'owner_name': g_data.get('group_name'),
                                'group_id': gid_int
                            })

            # ORDER BY v.releaseDate ASC, g.group_id ASC
            streams = sorted(streams, key=lambda x: (str(x['releaseDate']), x['group_id']))
            
            unique_groups = sorted(list(set(s['owner_name'] for s in streams if s.get('owner_name'))))
            video_ids = [s['video_id'] for s in streams]

            # 4. Secondary Query Simulation: Attach full song metadata profiles
            video_music_map = {}
            for vmr in vmr_rows:
                vid = vmr.get('video_id')
                if vid in video_ids:
                    sid = str(vmr.get('song_id'))
                    if sid in songs_map:
                        s_data = songs_map[sid]
                        video_music_map.setdefault(vid, []).append({
                            'video_id': vid,
                            'songtitle': s_data.get('songtitle'),
                            'artist': s_data.get('artist')
                        })

            # Use your native structuring logic function block safely
            timeline_data = time.get_livestream_timeline_data(streams, video_music_map)

            return render_template('admlivetimeline.html', 
                                   timeline_data=timeline_data, 
                                   groups=unique_groups)

        except Exception as portfolio_err:
            print(f"⚠️ Live timeline portfolio extraction failure: {str(portfolio_err)}")
            return render_template('admlivetimeline.html', timeline_data={}, groups=[])
    
    cursor = con.get_db()
    if not cursor:
        return render_template('admlivetimeline.html', timeline_data={}, groups=[])

    try:
        cursor.execute("""
            SELECT 
                v.video_id, v.video_title, v.releaseDate, v.video_notes, 
                s.title AS origin_show, 
                g.group_name AS owner_name,
                g.group_id
            FROM video v
            JOIN video_showtitle vs ON v.video_id = vs.video_id
            JOIN showtitle s ON vs.title_id = s.title_id
            JOIN showtitle_category sc ON s.title_id = sc.title_id
            JOIN showownership so ON s.title_id = so.title_id
            JOIN kgroups g ON so.group_id = g.group_id
            WHERE sc.category_id = 12 
              AND (g.group_id BETWEEN 1 AND 6 OR g.group_id BETWEEN 120 AND 124)
              AND v.webstatus = 'show'
            ORDER BY v.releaseDate ASC, g.group_id ASC
        """)
        streams = cursor.fetchall()
        
        unique_groups = sorted(list(set(s['owner_name'] for s in streams)))
        video_ids = [s['video_id'] for s in streams]
        video_music_map = {}

        if video_ids:
            format_strings = ','.join(['%s'] * len(video_ids))
            cursor.execute(f"""
                SELECT vmr.video_id, s.songtitle, s.artist
                FROM video_music_recs vmr
                JOIN songs s ON vmr.song_id = s.song_id
                WHERE vmr.video_id IN ({format_strings})
                ORDER BY vmr.sort_order ASC
            """, tuple(video_ids))
            for row in cursor.fetchall():
                video_music_map.setdefault(row['video_id'], []).append(row)

        timeline_data = time.get_livestream_timeline_data(streams, video_music_map)
        
        return render_template('admlivetimeline.html', 
                               timeline_data=timeline_data, 
                               groups=unique_groups)

    except Exception as e:
        return render_template('admlivetimeline.html', timeline_data={}, groups=[])
        
    finally:
        cursor.close()

@app.route('/memberlist')
def memblist():
    if IS_PORTFOLIO:
        raw_members = load_portfolio_data('members')
        raw_groups = load_portfolio_data('kgroups')
        
        grouped = {}
        alphabet = set()
        unassigned = []
        
        # 1. Initialize all known groups from your portfolio data
        groups_map = {}
        for g in raw_groups:
            gn = g.get('group_name')
            if gn:
                groups_map[gn] = g
                char = gn[0].upper()
                alphabet.add(char if char.isalpha() else '#')
                
                # Setup structural dict layout exactly as the template expects
                grouped[gn] = {
                    'id': g.get('group_id'),
                    'type': g.get('grouptype'),
                    'members': []
                }

        # 2. Process members and cross-reference their group strings
        for m in raw_members:
            g_string = m.get('groups') or ''
            member_row = {'member_id': m.get('member_id'), 'member_name': m.get('member_name')}
            
            if not g_string or g_string.strip() == '':
                # Replicate: WHERE mg.group_id IS NULL
                unassigned.append(member_row)
            else:
                # Replicate the LEFT JOIN multiplication (member shows up under each group they are assigned to)
                member_assigned_groups = [name.strip() for name in g_string.split(',')]
                for gn in member_assigned_groups:
                    if gn in grouped:
                        grouped[gn]['members'].append({
                            'id': m.get('member_id'),
                            'name': m.get('member_name')
                        })
                        
        # Sort members alphabetically by ID or Name within their respective groups to match production order
        for gn in grouped:
            grouped[gn]['members'] = sorted(grouped[gn]['members'], key=lambda x: x['id'])
        unassigned = sorted(unassigned, key=lambda x: x['member_id'])

        return render_template('admmemblist.html', 
                               grouped=grouped, 
                               unassigned=unassigned, 
                               alphabet=sorted(list(alphabet)))

    cursor = con.get_db()
    if not cursor:
        return render_template('admmemblist.html', grouped={}, unassigned=[], alphabet=[])
    
    try:
        cursor.execute("""
            SELECT 
                g.group_id, g.group_name, g.grouptype,
                m.member_id, m.member_name
            FROM kgroups g
            LEFT JOIN member_groups mg ON g.group_id = mg.group_id
            LEFT JOIN members m ON mg.member_id = m.member_id
            ORDER BY g.group_name ASC, m.member_id ASC;
        """)
        raw_data = cursor.fetchall()
        
        cursor.execute("""
            SELECT m.member_id, m.member_name
            FROM members m
            LEFT JOIN member_groups mg ON m.member_id = mg.member_id
            WHERE mg.group_id IS NULL
            ORDER BY m.member_id ASC;
        """)
        unassigned = cursor.fetchall()

        grouped = {}
        alphabet = set()
        
        # 3. Process structural layouts for Jinja presentation mapping
        for row in raw_data:
            gn = row['group_name']
            char = gn[0].upper() if gn else '#'
            alphabet.add(char if char.isalpha() else '#')
            
            if gn not in grouped:
                grouped[gn] = {
                    'id': row['group_id'],
                    'type': row['grouptype'],
                    'members': []
                }
            
            if row['member_id']:
                grouped[gn]['members'].append({
                    'id': row['member_id'],
                    'name': row['member_name']
                }
            )
                
        return render_template('admmemblist.html', 
                               grouped=grouped, 
                               unassigned=unassigned,
                               alphabet=sorted(list(alphabet)))

    except Exception as e:
        return render_template('admmemblist.html', grouped={}, unassigned=[], alphabet=[])

    finally:
        cursor.close()

@app.route('/songlibrary')
def songlib():
    if IS_PORTFOLIO:
        all_songs = load_portfolio_data('songs')
        library = {}
        alphabet = set()
        
        for s in all_songs:
            art = s.get('artist', 'Unknown Artist')
            alb = s.get('album') or "Unknown Album"
            char = art[0].upper() if art else '#'
            alphabet.add(char if char.isalpha() else '#')
            
            if art not in library: library[art] = {}
            if alb not in library[art]: library[art][alb] = []
            library[art][alb].append(s)
            
        return render_template('admsonglib.html', library=library, alphabet=sorted(list(alphabet)))
    
    cursor = con.get_db()
    if not cursor:
        return render_template('admsonglib.html', library={}, alphabet=[])

    try:
        cursor.execute("""
            SELECT * FROM songs 
            ORDER BY artist ASC, album ASC, track_number ASC
        """)
        all_songs = cursor.fetchall()
        
        library = {}
        alphabet = set()
        
        for s in all_songs:
            art = s['artist']
            alb = s['album'] or "Unknown Album"
            
            # alphabet index
            char = art[0].upper()
            letter = char if char.isalpha() else '#'
            alphabet.add(letter)
            
            # nested grouping
            if art not in library:
                library[art] = {}
            if alb not in library[art]:
                library[art][alb] = []
                
            library[art][alb].append(s)
        
        return render_template('admsonglib.html',
                               library=library, 
                               alphabet=sorted(list(alphabet)))

    except Exception as e:
        return render_template('admsonglib.html', library={}, alphabet=[])

    finally:
        cursor.close()





if __name__ == '__main__':
    app.run(debug=True)
