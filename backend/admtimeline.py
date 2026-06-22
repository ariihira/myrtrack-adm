import os, json
from datetime import datetime
from backend.connection import get_db
from collections import OrderedDict


IS_PORTFOLIO = os.environ.get("PORTFOLIO_MODE", "False").strip().title() == "True"

def get_livestream_timeline_data(streams, video_music_map):
    """
    Groups flat stream data into a nested dictionary: { Year: [StreamCards] }
    """
    timeline_data = OrderedDict()
    
    for s in streams:
        # Attach songs from the map to the specific video
        s['songs'] = video_music_map.get(s['video_id'], [])
        
        # Extract year from date
        year = str(s['releaseDate'])[:4] if s['releaseDate'] else "Unknown"
        
        if year not in timeline_data:
            timeline_data[year] = []
            
        timeline_data[year].append(s)
        
    return timeline_data


def alltimeline(excluded_category_ids=None, selected_group_names=None):
    """
    Fetches processed video records matching complex priority rules.
    Seamlessly supports both production MySQL execution and decoupled static Portfolio environments.
    """
    # 1. BOUNCER / GUARD LAYER
    if IS_PORTFOLIO:
        try:
            # Helper to open your static asset mirror
            def get_mock_data(key):
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

            # 1. Pull core table snapshots
            raw_videos = get_mock_data('video')
            junc_show = get_mock_data('video_showtitle')
            all_shows = get_mock_data('showtitle')
            junc_cat = get_mock_data('showtitle_category')
            junc_own = get_mock_data('showownership')
            all_groups = get_mock_data('kgroups')
            
            host_rows = get_mock_data('videohost')
            guest_rows = get_mock_data('videoguest')
            tiny_rows = get_mock_data('tinyguest')
            mc_rows = get_mock_data('videomushowmc')
            all_members = get_mock_data('members')


            # categories that should result in clearing the owning_groups field
            categories_to_clear_owner = [1, 7, 9]

            # ownership is ignored if a video host or MC is present
            categories_conditional_ignore = [1, 4, 5, 7]

            # video is excluded unless a host, guest, or tiny guest is present
            conditional_excluded_ids = [1, 4, 5, 6, 16]

            # ensure excluded_category_ids is a clean list
            if excluded_category_ids is None:
                clean_excluded_ids = [17, 18]
            elif not isinstance(excluded_category_ids, list):
                try: clean_excluded_ids = [int(excluded_category_ids)]
                except Exception: clean_excluded_ids = []
            else:
                try: clean_excluded_ids = [int(x) for x in excluded_category_ids]
                except Exception: clean_excluded_ids = []

            shows_map = {str(s.get('title_id')): s for s in all_shows}
            groups_map = {str(g.get('group_id')): g.get('group_name') for g in all_groups}
            
            video_to_shows = {}
            for j in junc_show:
                vid, tid = str(j.get('video_id')), str(j.get('title_id'))
                video_to_shows.setdefault(vid, []).append(tid)

            show_to_cats = {}
            for j in junc_cat:
                tid, cid = str(j.get('title_id')), int(j.get('category_id') or 0)
                show_to_cats.setdefault(tid, []).append(cid)

            show_to_owners = {}
            for j in junc_own:
                tid, gid = str(j.get('title_id')), str(j.get('group_id'))
                if gid in groups_map:
                    show_to_owners.setdefault(tid, []).append(groups_map[gid])

            # fetch videos 
            processed_videos = []
            for v in raw_videos:
                # Replicate releaseDate checks and filter hidden web statuses safely
                if v.get('webstatus') == 'hide' or not v.get('releaseDate'):
                    continue
                    
                v_id = str(v.get('video_id'))
                target_show_ids = video_to_shows.get(v_id, [])
                
                # We join all showtitle categories, but the crucial filter is in the WHERE clause below.
                associated_cats = []
                associated_show_titles = []
                associated_owners = []
                for tid in target_show_ids:
                    if tid in shows_map:
                        associated_show_titles.append(shows_map[tid].get('title', ''))
                        cats = show_to_cats.get(tid, [])
                        associated_cats.extend(cats)
                        associated_owners.extend(show_to_owners.get(tid, []))

                # AND have at least one associated show title NOT in the excluded categories.
                if clean_excluded_ids and all(c in clean_excluded_ids for c in associated_cats):
                    continue
                if not target_show_ids: 
                    continue

                has_host_rel = any(str(h.get('video_id')) == v_id for h in host_rows)
                has_guest_rel = any(str(g.get('video_id')) == v_id for g in guest_rows)
                has_tiny_rel = any(str(t.get('video_id')) == v_id for t in tiny_rows)
                has_mc_rel = any(str(m.get('video_id')) == v_id for m in mc_rows)

                # AND IF the video is part of conditional excluded ids
                is_cond_excluded = any(c in conditional_excluded_ids for c in associated_cats)
                if is_cond_excluded and not (has_host_rel or has_guest_rel or has_tiny_rel):
                    continue

                # group filter & checks if any of the relational intersections link back to the filtered groups
                if selected_group_names:
                    match_group_found = False
                    # Checked via Show Ownership & Condition A: Show is not in a conditional category
                    if not any(c in categories_conditional_ignore for c in associated_cats):
                        if any(own in selected_group_names for own in associated_owners):
                            match_group_found = True
                    # Checked via Host, Guest, Tiny Guest, or MC Entity Relations
                    if not match_group_found:
                        for row_list, key_lbl in [(host_rows, 'group_id'), (guest_rows, 'group_id'), (tiny_rows, 'group_id'), (mc_rows, 'group_id')]:
                            for r in row_list:
                                if str(r.get('video_id')) == v_id and groups_map.get(str(r.get(key_lbl))) in selected_group_names:
                                    match_group_found = True
                                    break
                    if not match_group_found:
                        continue 

                v_record = {
                    'video_id': v.get('video_id'),
                    'eventDate': v.get('releaseDate'),
                    'season': str(v.get('season') or ''),
                    'episodeNumber': str(v.get('episodeNumber') or ''),
                    'title': v.get('video_title'),
                    'ext': v.get('title_extras'),
                    'var': 1 if any(shows_map[tid].get('variety') for tid in target_show_ids if tid in shows_map) or v.get('is_variety') else 0,
                    'notes': str(v.get('video_notes') or ''),
                    # Only allowed shows (those not in excluded categories)
                    'show_titles': ", ".join(sorted(list(set(associated_show_titles)))),
                    'category_ids': ",".join(str(c) for c in set(associated_cats)),
                    # 1. HOST LOGIC
                    'is_host': 1 if has_host_rel else 0,
                    # 2. MC LOGIC (fetch specific MC group names)
                    'has_mc': 1 if has_mc_rel else 0,
                    'item_type': 'video'
                }

                h_match = next((h for h in host_rows if str(h.get('video_id')) == v_id), None)
                v_record['host_group_name'] = groups_map.get(str(h_match.get('group_id'))) if h_match else None

                mc_matched_gnames = sorted(list({groups_map[str(m.get('group_id'))] for m in mc_rows if str(m.get('video_id')) == v_id and str(m.get('group_id')) in groups_map}))
                v_record['mc_group_names'] = ", ".join(mc_matched_gnames) if mc_matched_gnames else None
                
                # 3. OWNER LOGIC
                v_record['owning_groups'] = ", ".join(sorted(list(set(associated_owners))))

                processed_videos.append(v_record)

            videos = sorted(processed_videos, key=lambda x: (x['eventDate'] or '', x['video_id']))
            video_ids = [v['video_id'] for v in videos]

            # trackers for secondary lookups
            video_guest_map = {}
            video_mc_map = {}
            members_map = {str(m.get('member_id')): m for m in all_members}
            
            # fetch all guests for these videos
            for vg in guest_rows:
                vid = vg.get('video_id')
                if vid in video_ids:
                    video_guest_map.setdefault(vid, {'members': [], 'groups': []})
                    mid = str(vg.get('member_id') or '')
                    gid = str(vg.get('group_id') or '')
                    
                    # attach guests to videos
                    if mid in members_map:
                        m_obj = members_map[mid]
                        m_group = m_obj.get('groups', '').split(',')[0].strip() if m_obj.get('groups') else None
                        video_guest_map[vid]['members'].append({
                            'name': m_obj.get('member_name'),
                            'group': groups_map.get(gid) or m_group
                        })
                    elif gid in groups_map:
                        if groups_map[gid] not in video_guest_map[vid]['groups']:
                            video_guest_map[vid]['groups'].append(groups_map[gid])

            # fetch all individual mc records
            for vmc in mc_rows:
                vid = vmc.get('video_id')
                if vid in video_ids:
                    video_mc_map.setdefault(vid, [])
                    mid = str(vmc.get('member_id') or '')
                    gid = str(vmc.get('group_id') or '')
                    # attach mc to videos
                    if mid in members_map:
                        video_mc_map[vid].append({
                            'name': members_map[mid].get('member_name'),
                            'group': groups_map.get(gid)
                        })

        except Exception as portfolio_err:
            print(f"⚠️ Portfolio simulation error encountered: {str(portfolio_err)}")
            return []

    # -------------------------------------------------------------
    # 🔌 ENGINE PART B: LIVE SQL DATABASE DEPLOYMENT
    # -------------------------------------------------------------
    else:
        cursor = get_db()
        if not cursor:
            return []

        try:
            # categories that should result in clearing the owning_groups field
            categories_to_clear_owner = [1, 7, 9]

            # ownership is ignored if a video host or MC is present
            categories_conditional_ignore = [1, 4, 5, 7]
            conditional_ignore_str = ",".join(str(cid) for cid in categories_conditional_ignore)

            # video is excluded unless a host, guest, or tiny guest is present
            conditional_excluded_ids = [1, 4, 5, 6, 16]
            conditional_ids_str = ",".join(str(cid) for cid in conditional_excluded_ids)

            # ensure excluded_category_ids is a clean list
            if excluded_category_ids is None:
                clean_excluded_ids = [17, 18]
            elif not isinstance(excluded_category_ids, list):
                try: clean_excluded_ids = [int(excluded_category_ids)]
                except (ValueError, TypeError): clean_excluded_ids = []
            else:
                try: clean_excluded_ids = [int(x) for x in excluded_category_ids]
                except (ValueError, TypeError): clean_excluded_ids = []

            # setup list parameters for SQL injection execution
            query_params = list(clean_excluded_ids)
            
            # create the SQL placeholders string based on the clean list
            placeholders = ','.join(['%s'] * len(clean_excluded_ids))

            # group filter
            group_filter_clause = ""
            if selected_group_names:
                group_placeholders = ','.join(['%s'] * len(selected_group_names))
                
                # multiply the parameters across all 5 EXISTS query checks
                for _ in range(5):
                    query_params.extend(selected_group_names)
                
                # checks if any of the relational intersections link back to the filtered groups
                group_filter_clause = f"""
                AND (
                    -- Checked via Show Ownership
                    EXISTS (
                        SELECT 1 FROM video_showtitle v_st
                        JOIN showownership s_o ON v_st.title_id = s_o.title_id
                        JOIN kgroups g_own ON s_o.group_id = g_own.group_id
                        LEFT JOIN showtitle_category st_c ON v_st.title_id = st_c.title_id
                        WHERE v_st.video_id = v.video_id 
                          AND g_own.group_name IN ({group_placeholders})
                          AND (
                              -- Condition A: Show is not in a conditional category
                              NOT EXISTS (
                                   SELECT 1 FROM showtitle_category st_c2 
                                   WHERE st_c2.title_id = v_st.title_id AND st_c2.category_id IN ({conditional_ignore_str})
                               )
                          )
                    )
                    -- Checked via Host Entity Relation
                    OR EXISTS (
                        SELECT 1 FROM videohost v_h
                        JOIN kgroups g_hst ON v_h.group_id = g_hst.group_id
                        WHERE v_h.video_id = v.video_id AND g_hst.group_name IN ({group_placeholders})
                    )
                    -- Checked via Main Guest Entity Relation
                    OR EXISTS (
                        SELECT 1 FROM videoguest v_g
                        JOIN kgroups g_gst ON v_g.group_id = g_gst.group_id
                        WHERE v_g.video_id = v.video_id AND g_gst.group_name IN ({group_placeholders})
                    )
                    -- Checked via Tiny Guest Appearance
                    OR EXISTS (
                        SELECT 1 FROM tinyguest v_tg
                        JOIN kgroups g_tgst ON v_tg.group_id = g_tgst.group_id
                        WHERE v_tg.video_id = v.video_id AND g_tgst.group_name IN ({group_placeholders})
                    )
                    -- Checked via Music Show Master of Ceremonies
                    OR EXISTS (
                        SELECT 1 FROM videomushowmc v_mc
                        JOIN kgroups g_mc ON v_mc.group_id = g_mc.group_id
                        WHERE v_mc.video_id = v.video_id AND g_mc.group_name IN ({group_placeholders})
                    )
                )
                """

            # fetch videos 
            query = f"""
            SELECT 
                v.video_id,
                v.releaseDate AS eventDate,
                IFNULL(v.season, '') AS season,
                IFNULL(v.episodeNumber, '') AS episodeNumber,
                v.video_title AS title,
                v.title_extras AS ext,
                v.is_variety AS var,
                IFNULL(v.video_notes, '') AS notes,

                -- Only allowed shows (those not in excluded categories)
                GROUP_CONCAT(DISTINCT s.title ORDER BY s.title SEPARATOR ', ') AS show_titles,

                GROUP_CONCAT(DISTINCT sc.category_id) AS category_ids,
                
                -- 1. HOST LOGIC
                EXISTS (SELECT 1 FROM videohost vh WHERE vh.video_id = v.video_id) AS is_host,
                (SELECT g2.group_name FROM videohost vh2 
                 JOIN kgroups g2 ON vh2.group_id = g2.group_id 
                 WHERE vh2.video_id = v.video_id LIMIT 1) AS host_group_name,

                -- 2. MC LOGIC (fetch specific MC group names)
                EXISTS (SELECT 1 FROM videomushowmc vmc WHERE vmc.video_id = v.video_id) AS has_mc,
                (SELECT GROUP_CONCAT(DISTINCT g3.group_name SEPARATOR ', ') 
                 FROM videomushowmc vmc2 
                 JOIN kgroups g3 ON vmc2.group_id = g3.group_id 
                 WHERE vmc2.video_id = v.video_id) AS mc_group_names,

                -- 3. OWNER LOGIC
                IFNULL(GROUP_CONCAT(DISTINCT g.group_name ORDER BY g.group_name SEPARATOR ', '), '') AS owning_groups,
                
                'video' AS item_type

            FROM video v
                -- Join only allowed shows (for aggregation purposes)
                LEFT JOIN video_showtitle vs ON v.video_id = vs.video_id
                LEFT JOIN showtitle s ON vs.title_id = s.title_id

                -- We join all showtitle categories, but the crucial filter is in the WHERE clause below.
                LEFT JOIN showtitle_category sc ON s.title_id = sc.title_id
                
                -- This join allows us to find the owners of the associated showtitle
                LEFT JOIN showownership so ON s.title_id = so.title_id
                LEFT JOIN kgroups g ON so.group_id = g.group_id
                
                -- Include only videos that:
                WHERE v.releaseDate IS NOT NULL 
                -- AND have at least one associated show title NOT in the excluded categories.
                AND EXISTS (
                    SELECT 1
                    FROM video_showtitle vs2
                    JOIN showtitle_category sc2 ON vs2.title_id = sc2.title_id
                    WHERE vs2.video_id = v.video_id
                    AND sc2.category_id NOT IN ({placeholders})
                )
                -- AND IF the video is part of conditional excluded ids
                AND (
                    NOT EXISTS (
                        SELECT 1 
                        FROM video_showtitle vs3
                        JOIN showtitle_category sc3 ON vs3.title_id = sc3.title_id
                        WHERE vs3.video_id = v.video_id AND sc3.category_id IN ({conditional_ids_str})
                    )
                    OR EXISTS (SELECT 1 FROM videohost WHERE video_id = v.video_id)
                    OR EXISTS (SELECT 1 FROM videoguest WHERE video_id = v.video_id)
                    OR EXISTS (SELECT 1 FROM tinyguest WHERE video_id = v.video_id)
                )
                {group_filter_clause}

            GROUP BY v.video_id
            ORDER BY v.releaseDate ASC, v.video_id ASC
            """
            
            # execute the query
            cursor.execute(query, tuple(query_params))
            videos = cursor.fetchall()

            video_ids = [v['video_id'] for v in videos]

            # trackers for secondary lookups
            video_guest_map = {}
            video_mc_map = {}

            if video_ids:
                format_strings = ','.join(['%s'] * len(video_ids))

                # fetch all guests for these videos
                cursor.execute(f"""
                    SELECT vg.video_id, m.member_name, g1.group_name AS member_group, g2.group_name AS guest_group
                    FROM videoguest vg
                    LEFT JOIN members m ON vg.member_id = m.member_id
                    LEFT JOIN member_groups mg ON m.member_id = mg.member_id
                    LEFT JOIN kgroups g1 ON mg.group_id = g1.group_id
                    LEFT JOIN kgroups g2 ON vg.group_id = g2.group_id
                    WHERE vg.video_id IN ({format_strings})
                """, tuple(video_ids))

                # attach guests to videos
                for row in cursor.fetchall():
                    vid = row['video_id']
                    video_guest_map.setdefault(vid, {'members': [], 'groups': []})
                    if row['member_name']:
                        if not row['guest_group'] or row['member_group'] == row['guest_group']:
                            video_guest_map[vid]['members'].append({'name': row['member_name'], 'group': row['member_group']})
                    elif row['guest_group'] and row['guest_group'] not in video_guest_map[vid]['groups']:
                        video_guest_map[vid]['groups'].append(row['guest_group'])

                # fetch all individual mc records
                cursor.execute(f"""
                    SELECT vmc.video_id, m.member_name, g.group_name FROM videomushowmc vmc
                    JOIN members m ON vmc.member_id = m.member_id
                    LEFT JOIN kgroups g ON vmc.group_id = g.group_id
                    WHERE vmc.video_id IN ({format_strings}) ORDER BY g.group_name ASC, m.member_name ASC
                """, tuple(video_ids))

                # attach mc to videos
                for row in cursor.fetchall():
                    video_mc_map.setdefault(row['video_id'], []).append({'name': row['member_name'], 'group': row['group_name']})

        except Exception:
            return []
        finally:
            cursor.close()

    # -------------------------------------------------------------
    # 👑 ENGINE PART C: POST-PROCESSING MATRIX (UNIFIED)
    # -------------------------------------------------------------
    # post-processing display configurations
    # runs identically in both modes
    categories_conditional_ignore = [1, 4, 5, 7]
    categories_to_clear_owner = [1, 7, 9]

    for v in videos:
        # clean 'season' field (Non-numeric check)
        season_value = v['season']
        if season_value and not str(season_value).strip().isdigit():
            v['season'] = ''

        # clear 'owning_groups' if categories 1, 7, or 9 are present
        category_ids_str = v.get('category_ids', '')
        has_conditional_category = False
    
        if category_ids_str:
            # convert the comma-separated string back to a list of integers
            fetched_categories = set(int(cid) for cid in str(category_ids_str).split(',') if str(cid).isdigit())
            has_conditional_category = any(cat in fetched_categories for cat in categories_conditional_ignore)
            
            # check for overlap with the categories that require clearing the owner
            if fetched_categories.intersection(categories_to_clear_owner):
                v['owning_groups'] = ''

        # map dynamic guest lists
        v_g_data = video_guest_map.get(v['video_id'], {'members': [], 'groups': []})    
        g_group_map = {}
        for m in v_g_data['members']:
            g_group_map.setdefault(m['group'], []).append(m['name'])

        g_parts = []
        # format group + members: "Group (Member1, Member2)" or "Group Member1"
        for g_name in sorted(g_group_map):
            m_names = g_group_map[g_name]
            if len(m_names) > 1:
                g_parts.append(f"{g_name} ({', '.join(m_names)})")
            else:
                g_parts.append(f"{g_name} {m_names[0]}")
            
        # add standalone groups (those without specific member lists)
        g_parts.extend(v_g_data['groups'])    
        # final string join using the bullet separator
        v['guest_display'] = ' • '.join(g_parts)
        # map individual MC lists
        v['mc_names'] = video_mc_map.get(v['video_id'], [])

        # ---  PRIORITY LOGIC ---
        # If show is category 1, 4, 7 and a Host/MC is present, ignore owner group strings completely
        if has_conditional_category and (v.get('is_host') or v.get('has_mc')):
            if v.get('is_host'):
                v['display_group'] = v.get('host_group_name', '')
            elif v.get('has_mc'):
                v['display_group'] = v.get('mc_group_names', '')
        else:
            # 1. HOST PRIORITY (Rules 1, 2, 3)
            # "owner groups as host + multi -> host", "1 group owner -> group", "host + no owner -> host"
            if v.get('is_host'):
                v['display_group'] = v.get('host_group_name') or v.get('owning_groups', '').split(',')[0]
            # 2. MC PRIORITY (Rule 4)
            # "music show mc -> all group name as mc in that video"
            elif v.get('has_mc'):
                v['display_group'] = v.get('mc_group_names') or v.get('owning_groups')
            # 3. GUEST PRIORITY (Rule 5)
            # "no host + guest -> guest group name"
            elif v.get('guest_display'):
                # Extracting only group names from the new "Group (Member)" format
                unique_groups = set()
                # get all known group names for this specific video
                known_groups = set(v_g_data['groups'])
                for m in v_g_data['members']:
                    known_groups.add(m['group'])

                # split the display string by the bullet
                for segment in v['guest_display'].split(' • '):
                    segment = segment.strip()
                    # check if the segment IS exactly a known group
                    if segment in known_groups:
                        unique_groups.add(segment)
                        continue
                    # check for "Group (Member, Member)" format
                    if "(" in segment:
                        unique_groups.add(segment.split('(')[0].strip())
                    # scenario b: Group Name MemberName -> find last space
                    elif " " in segment:
                        # iterate through known groups to see if the segment STARTS with one
                        # ex: handles "NCT 127 Mark" by finding "NCT 127"
                        found_known = False
                        for group in known_groups:
                            if segment.startswith(group):
                                unique_groups.add(group)
                                found_known = True
                                break
                        # fallback logic if for some reason the group isn't in known_groups
                        if not found_known:
                            parts = segment.rsplit(' ', 1)
                            unique_groups.add(parts[0].strip())
                    else:
                        unique_groups.add(segment)

                # reassemble alphabetically
                v['display_group'] = ', '.join(sorted(list(unique_groups)))            
            # OWNER FALLBACK (Rule 6)
            # no host + no guest + owner (one/multiple) -> all group owner name
            else:
                v['display_group'] = v.get('owning_groups')            

    return videos