import db_connect
from backend.connection import get_db


# entity HGT

def fetch_group_member_data():
    """
    Fetches raw group definitions and nested member assignment states.
    """
    cursor = get_db()
    if not cursor:
        return [], []
    
    try:
        # fetch groups (including parent group names for subunits)
        cursor.execute("""
            SELECT g.*, p.group_name AS parent_name 
            FROM kgroups g
            LEFT JOIN kgroups p ON g.parent_id = p.group_id
            ORDER BY g.group_name ASC
        """)
        groups = cursor.fetchall()

        # fetch Members with their current group assignments
        cursor.execute("""
            SELECT m.member_id, m.member_name, 
                   GROUP_CONCAT(g.group_name SEPARATOR ', ') AS current_groups,
                   GROUP_CONCAT(g.group_id SEPARATOR ',') AS current_group_ids
            FROM members m
            LEFT JOIN member_groups mg ON m.member_id = mg.member_id
            LEFT JOIN kgroups g ON mg.group_id = g.group_id
            GROUP BY m.member_id, m.member_name
            ORDER BY m.member_name ASC
        """)
        members = cursor.fetchall()

        return groups, members

    except Exception:
        return [], []

    finally:
        cursor.close()

def insert_group(data):
    """
    Handles database insertion for a new group/subunit record.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    sql = """INSERT INTO kgroups (group_name, group_desc, grouptype, parent_id, debutdate) 
             VALUES (%s, %s, %s, %s, %s)"""
    
    params = (
        data['group_name'], 
        data.get('group_desc'), 
        data.get('grouptype') or None,
        data.get('parent_id') or None,
        data.get('debutdate') or None
    )
    
    try:
        cursor.execute(sql, params)
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
        
    finally:
        cursor.close()

def update_group(group_id, data):
    """
    Updates all fields for a specific group including hierarchy.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    sql = """
        UPDATE kgroups 
        SET group_name = %s, 
            group_desc = %s, 
            grouptype = %s, 
            parent_id = %s, 
            debutdate = %s 
        WHERE group_id = %s
    """
    # using .get() and 'or None' ensures empty strings from the form 
    # are stored as NULL in the database, preventing FK errors.
    params = (
        data['group_name'],
        data.get('group_desc') or None,
        data.get('grouptype') or None,
        data.get('parent_id') or None,
        data.get('debutdate') or None,
        group_id
    )
    cursor.execute(sql, params)
    db_connect.connection.commit()

def update_member_groups(member_id, data):
    """
    Updates member profile details and atomic group associations.
    """
    cursor = get_db()
    if not cursor:
        return False

    try:
        # update name
        cursor.execute("UPDATE members SET member_name = %s WHERE member_id = %s", 
                       (data['member_name'], member_id))
        
        # update group links (clear and re-insert)
        cursor.execute("DELETE FROM member_groups WHERE member_id = %s", (member_id,))
        
        group_ids = data.getlist('group_ids')
        for g_id in group_ids:
            cursor.execute("INSERT INTO member_groups (member_id, group_id) VALUES (%s, %s)", 
                           (member_id, g_id))
            
        db_connect.connection.commit()
        return True
        
    except Exception:
        db_connect.connection.rollback()
        return False
        
    finally:
        cursor.close()


#entity MC

def insert_mc_pair(data):
    """
    Creates a new MC pair profile and maps show and relational member records.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    try:
        # insert pair name
        cursor.execute("INSERT INTO musicshowmc (mc_pairname) VALUES (%s)", (data['pairname'],))
        mc_id = cursor.lastrowid
        
        # link to mushow
        if data.get('title_id'):
            cursor.execute("INSERT INTO mushow_mcs (mushow_id, mc_id) VALUES (%s, %s)", 
                           (data['title_id'], mc_id))
        
        # link members (multiple)
        member_ids = data.getlist('member_ids')
        for m_id in member_ids:
            cursor.execute("INSERT INTO mc_members (mc_id, member_id) VALUES (%s, %s)", (mc_id, m_id))
        
        db_connect.connection.commit()
        return True
        
    except Exception:
        db_connect.connection.rollback()
        return False
        
    finally:
        cursor.close()

def update_mc_full(mc_id, data):
    """
    Updates MC group naming and completely rebuilds show and member links.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    try:
        # update name
        cursor.execute("UPDATE musicshowmc SET mc_pairname = %s WHERE mc_id = %s", 
                       (data['pairname'], mc_id))
        
        # update mushow link (clear and re-insert)
        cursor.execute("DELETE FROM mushow_mcs WHERE mc_id = %s", (mc_id,))
        if data.get('title_id'):
            cursor.execute("INSERT INTO mushow_mcs (mushow_id, mc_id) VALUES (%s, %s)", 
                           (data['title_id'], mc_id))
        
        # update member links (clear and re-insert)
        cursor.execute("DELETE FROM mc_members WHERE mc_id = %s", (mc_id,))
        member_ids = data.getlist('member_ids')
        for m_id in member_ids:
            cursor.execute("INSERT INTO mc_members (mc_id, member_id) VALUES (%s, %s)", (mc_id, m_id))
        
        db_connect.connection.commit()
        return True
        
    except Exception:
        db_connect.connection.rollback()
        return False
        
    finally:
        cursor.close()


#entity l

def fetch_entity_l_data(search_query=None):
    """
    Fetches all data for Entity L, including dropdown context.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    try:
        # tags
        if search_query:
            sql = """
                SELECT t.*, g.group_name, m.member_name FROM livestreamtags t
                LEFT JOIN kgroups g ON t.group_id = g.group_id
                LEFT JOIN members m ON t.member_id = m.member_id
                WHERE t.tag_name LIKE %s OR g.group_name LIKE %s
                ORDER BY t.tag_name ASC
            """
            val = f"%{search_query}%"
            cursor.execute(sql, (val, val))
        else:
            cursor.execute("""
                SELECT t.*, g.group_name, m.member_name FROM livestreamtags t
                LEFT JOIN kgroups g ON t.group_id = g.group_id
                LEFT JOIN members m ON t.member_id = m.member_id
                ORDER BY t.tag_id DESC LIMIT 200
            """)
        tags = cursor.fetchall()

        # season names
        cursor.execute("""
            SELECT s.*, st.title FROM season_names s
            JOIN showtitle st ON s.title_id = st.title_id
            ORDER BY st.title ASC, s.season_number ASC
        """)
        seasons = cursor.fetchall()

        cursor.execute("SELECT group_id, group_name FROM kgroups ORDER BY group_name")
        groups = cursor.fetchall()
        
        cursor.execute("SELECT title_id, title FROM showtitle ORDER BY title")
        shows = cursor.fetchall()

        return tags, seasons, groups, shows

    except Exception:
        return [], [], [], []

    finally:
        cursor.close()

def insert_tag(data):
    """Inserts a new livestream tag mapping with optional group relationship."""
    cursor = get_db()
    if not cursor:
        return False
    
    sql = "INSERT INTO livestreamtags (tag_name, group_id) VALUES (%s, %s)"
    
    try:
        cursor.execute(sql, (data['name'], data.get('group_id') or None))
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()

def update_tag(tag_id, data):
    """Modifies tag text or changes its linked group relationship."""
    cursor = get_db()
    if not cursor:
        return False
    
    sql = "UPDATE livestreamtags SET tag_name=%s, group_id=%s WHERE tag_id=%s"

    try:
        cursor.execute(sql, (data['name'], data.get('group_id') or None, tag_id))
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()

def insert_season(data):
    """Creates a custom named override for a specific show's season index."""
    cursor = get_db()
    if not cursor:
        return False
    
    sql = "INSERT INTO season_names (title_id, season_number, season_name) VALUES (%s, %s, %s)"
    
    try:
        cursor.execute(sql, (data['title_id'], data['s_num'], data['s_name']))
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()

def update_season(title_id, s_num, data):
    """Updates a custom season display title string based on composite keys."""
    cursor = get_db()
    if not cursor:
        return False
    
    sql = "UPDATE season_names SET season_name=%s WHERE title_id=%s AND season_number=%s"
    
    try:
        cursor.execute(sql, (data['s_name'], title_id, s_num))
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()

#entity s

def fetch_songs(search_query=None):
    """Fetches songs. Limits to 200 for speed unless searching."""
    cursor = get_db()
    if not cursor:
        return False
    
    try:
        if search_query:
            query = """
                SELECT * FROM songs 
                WHERE songtitle LIKE %s OR artist LIKE %s OR album LIKE %s
                ORDER BY artist ASC, album ASC, track_number ASC
            """
            val = f"%{search_query}%"
            cursor.execute(query, (val, val, val))
        else:
            cursor.execute("SELECT * FROM songs ORDER BY song_id DESC LIMIT 200")
            
        return cursor.fetchall()

    except Exception:
        return []

    finally:
        cursor.close()

def insert_song(data):
    """ Handles raw database insertion for a new cataloged track. """
    cursor = get_db()
    if not cursor:
        return False
    
    sql = """
        INSERT INTO songs (songtitle, artist, album, track_number, spotify_link, youtube_link)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (data['title'], data['artist'], data['album'], 
              data['track_number'], data['spotify'], data['youtube'])
    
    try:
        cursor.execute(sql, params)
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()

def update_song(song_id, data):
    """
    Updates all metadata properties for an existing cataloged track.
    """
    cursor = get_db()
    if not cursor:
        return False
    
    sql = """
        UPDATE songs 
        SET songtitle=%s, artist=%s, album=%s, track_number=%s, spotify_link=%s, youtube_link=%s 
        WHERE song_id=%s
    """
    params = (data['title'], data['artist'], 
              data['album'], data['track_number'], 
              data['spotify'], data['youtube'], song_id)
    
    try:
        cursor.execute(sql, params)
        db_connect.connection.commit()
        return True
    except Exception:
        db_connect.connection.rollback()
        return False
    finally:
        cursor.close()