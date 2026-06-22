import db_connect
from backend.connection import get_db


def add_totimeline(form_data):
    """Handles the database insertion for new undecided videos."""
    v_title = form_data.get('video_title')
    v_date = form_data.get('release_date')
    v_notes = form_data.get('video_notes')
    is_variety = 1 if form_data.get('is_variety') else 0

    cursor = get_db()
    if not cursor:
        return False
    
    query = """
        INSERT INTO video (video_title, releaseDate, video_notes, is_variety, webstatus)
        VALUES (%s, %s, %s, %s, 'undecided')
    """
    
    try:
        cursor.execute(query, (v_title, v_date, v_notes, is_variety))
        db_connect.connection.commit()
        return True
    
    except Exception:
        db_connect.connection.rollback()
        return False

    finally:
        cursor.close()


def save_triage(v_id, status, notes, selected_shows):
    """
    Logic for saving a single video card.
    Returns: (bool, message)
    """
    # validation Rule
    if status == 'show' and not selected_shows:
        return False, "Select at least one show before dispatching."

    cursor = get_db()
    if not cursor:
        return False, "Operation bypassed: System in Portfolio Mode or Database down."
    
    try:
        # update main video table
        cursor.execute("""
            UPDATE video 
            SET webstatus = %s, video_notes = %s 
            WHERE video_id = %s
        """, (status, notes, v_id))

        # sync showtitle associations
        cursor.execute("DELETE FROM video_showtitle WHERE video_id = %s", (v_id,))
        for s_id in selected_shows:
            if str(s_id).isdigit():
                cursor.execute("""
                    INSERT INTO video_showtitle (video_id, title_id) 
                    VALUES (%s, %s)
                """, (v_id, int(s_id)))

        db_connect.connection.commit()
        return True, "Saved successfully"
    
    except Exception as e:
        db_connect.connection.rollback()
        return False, f"Database error: {str(e)}"
    
    finally:
        cursor.close()