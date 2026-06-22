import db_connect
from backend.connection import get_db
from flask import request, redirect
from datetime import datetime

def add_show():
    cursor = get_db() 
    if not cursor:
        return redirect("/addshow")

    title = request.form["title"]
    releaseYear = request.form.get("releaseYear")

    try:
        title = request.form["title"]
        releaseYear = request.form.get("releaseYear")

        # automatic date sort handles the transformation
        sort_date = None
        if releaseYear:
            try:
                # check for DD-MM-YYYY (e.g., 12-12-2012)
                if "-" in releaseYear and len(releaseYear.split("-")[0].strip()) <= 2:
                    sort_date = datetime.strptime(releaseYear.strip(), "%d-%m-%Y").date()
                else:
                    # extract first 4 digits for series/ranges (e.g., 2017 - 2018)
                    year_part = releaseYear.strip()[:4]
                    if year_part.isdigit():
                        sort_date = f"{year_part}-01-01"
            except Exception:
                sort_date = None
        
        # convert to int only if not empty
        totalSeasons_raw = request.form.get("totalSeasons")
        totalSeasons = int(totalSeasons_raw) if totalSeasons_raw else None

        totalEpisodes_raw = request.form.get("totalEpisodes")
        totalEpisodes = int(totalEpisodes_raw) if totalEpisodes_raw else None

        # watch status: will be None if user picks the first option "-- Select Status --"
        watchStatus = request.form.get("watchStatus") or None
        title_img = request.form.get("title_img", "pics/placeholder.jpg")

        # checkbox: if not checked, returns None
        variety = 1 if request.form.get("variety") else 0

        # insert show
        cursor.execute("""
            INSERT INTO showtitle (title, releaseYear, totalSeasons, totalEpisodes, watchStatus, title_img, variety, webstatus, sort_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'show', %s)
        """, (title, releaseYear, totalSeasons, totalEpisodes, watchStatus, title_img, variety, sort_date))
        new_title_id = cursor.lastrowid

        # insert categories
        categories = request.form.getlist("categories[]")
        for cid in categories:
            cursor.execute(
                "INSERT INTO showtitle_category (title_id, category_id) VALUES (%s, %s)",
                (new_title_id, cid)
            )

        # insert ownerships
        groups = request.form.getlist("groups[]")    # list of group_ids
        members = request.form.getlist("members[]")  # list of member_ids

        if groups:
            for gid in groups:
                valid_member_found = False

                if members:
                    for mid in members:
                        # check if member belongs to this group
                        cursor.execute("""
                            SELECT 1 FROM member_groups
                            WHERE group_id = %s AND member_id = %s
                        """, (gid, mid))
                        
                        if cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO showownership (title_id, group_id, member_id)
                                VALUES (%s, %s, %s)
                            """, (new_title_id, gid, mid))
                            valid_member_found = True

                # if no valid member, insert group-only ownership
                if not valid_member_found:
                    cursor.execute("""
                        INSERT INTO showownership (title_id, group_id, member_id)
                        VALUES (%s, %s, NULL)
                    """, (new_title_id, gid))

        # Commit everything as a single transaction unit
        if db_connect.connection:
            db_connect.connection.commit()
            
        return redirect("/addshow")

    except Exception as e:
        if db_connect.connection:
            db_connect.connection.rollback()
        print(f"!!! Database transaction error adding new entry grid show: {str(e)}")
        return redirect("/addshow")

    finally:
        cursor.close()


def add_video():
    cursor = get_db() 
    if not cursor:
        return redirect("/addvideo")
    
    try:
        # required fields
        video_title = request.form.get("title")
        is_variety = 1 if request.form.get("variety") else 0

        # release date
        day = request.form.get("release_day")
        month = request.form.get("release_month")
        year = request.form.get("release_year")
        
        release_date = None  # default to NULL if incomplete
        if year and month and day:
            release_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        # season, episode, extras, notes
        season = request.form.get("season")
        episode_number = request.form.get("episode")

        # allow '-' or 'SPE' as valid input, or None if empty
        season = season.strip() if season else None
        episode_number = episode_number.strip() if episode_number else None

        title_extras = request.form.get("episode_extras") or None
        notes = request.form.get("notes") or None

        # insert into video table
        cursor.execute("""
            INSERT INTO video 
            (video_title, is_variety, releaseDate, season, episodeNumber, title_extras, video_notes, webstatus)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'show')
        """, (video_title, is_variety, release_date, season, episode_number, title_extras, notes))

        video_id = cursor.lastrowid

        # video ↔ showtitle
        show_ids = request.form.getlist("showtitles[]")

        if not video_id:
            raise ValueError("video_id not set after inserting video!")

        # loop through selected shows
        for sid in show_ids:
            try:
                sid_int = int(sid)
                if sid_int <= 0:
                    continue
            except (ValueError, TypeError):
                continue

            cursor.execute(
                "INSERT INTO video_showtitle (video_id, title_id) VALUES (%s, %s)",
                (video_id, sid_int)
            )

        # ownership (groups & members) -> videoHost
        host_groups = request.form.getlist("ownership_groups[]")
        host_members = request.form.getlist("ownership_members[]")

        if host_groups:
            for g in host_groups:
                valid_member_found = False

                # if both members and groups exist, insert only valid pairs
                if host_members:
                    for m in host_members:
                        cursor.execute("""
                            SELECT 1 FROM member_groups
                            WHERE group_id = %s AND member_id = %s
                        """, (g, m))

                        # check if this member belongs to this group
                        if cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO videohost (video_id, group_id, member_id)
                                VALUES (%s, %s, %s)
                            """, (video_id, g, m))
                            valid_member_found = True

                # if no valid member, insert group with NULL member_id
                if not valid_member_found:
                    cursor.execute("""
                        INSERT INTO videohost (video_id, group_id, member_id)
                        VALUES (%s, %s, NULL)
                    """, (video_id, g))
            
        # guests (groups & members)
        guest_groups = request.form.getlist("guest_groups[]")
        guest_members = request.form.getlist("guest_members[]")

        if guest_groups:
            for g in guest_groups:
                valid_member_found = False

                # if both members and groups exist, insert only valid pairs
                if guest_members:
                    for m in guest_members:
                        cursor.execute("""
                            SELECT 1 FROM member_groups
                            WHERE group_id = %s AND member_id = %s
                        """, (g, m))
                        
                        # check if this member really belongs to this group
                        if cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO videoguest (video_id, group_id, member_id)
                                VALUES (%s, %s, %s)
                            """, (video_id, g, m))
                            valid_member_found = True

                # if no valid member, insert group with NULL member_id
                if not valid_member_found:
                    cursor.execute("""
                        INSERT INTO videoguest (video_id, group_id, member_id)
                        VALUES (%s, %s, NULL)
                    """, (video_id, g))

        # music mc
        mc_ids = request.form.getlist("mcs[]")
        mc_member_values = request.form.getlist("mc_members[]")

        # primary key: (video_id, mc_id, member_id)
        if mc_ids and mc_member_values:
            # take the first selected mc pair
            current_mc_id = int(mc_ids[0])

            for value in mc_member_values:
                try:
                    # value is "memberid_groupid"
                    parts = value.split("_")
                    # member_id is index 0
                    m_id = int(parts[0])

                    # group_id is index 1. 
                    # check if it exists and isn't just an empty string
                    g_id = None
                    if len(parts) > 1 and parts[1].strip():
                        g_id = int(parts[1])

                    cursor.execute("""
                        INSERT IGNORE INTO videomushowmc (video_id, mc_id, member_id, group_id)
                        VALUES (%s, %s, %s, %s)
                    """, (video_id, current_mc_id, m_id, g_id))
                except (ValueError, IndexError) as e:
                    print(f"MC Loop Error: {e}")
                    continue

        # livestream tags
        livestream_tags = request.form.getlist("livestream_tags[]")
        for tag in livestream_tags:
            cursor.execute(
                "INSERT INTO videolivetags (video_id, tag_id) VALUES (%s, %s)",
                (video_id, tag)
            )

        if db_connect.connection:
            db_connect.connection.commit()
            
        return redirect("/addvideo")

    except Exception:
        if db_connect.connection:
            db_connect.connection.rollback()
        return redirect("/addvideo")

    finally:
        cursor.close()

    