-- ====================================================================
-- DATABASE & USER SETUP
-- ====================================================================

CREATE DATABASE myraaflix CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE myraaflix;



-- ====================================================================
-- PRIMARY INDEPENDENT TABLES
-- ====================================================================

-- Members table
CREATE TABLE members (
    member_id INT AUTO_INCREMENT PRIMARY KEY,
    member_name VARCHAR(100) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Category table
CREATE TABLE category (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Music show MC
CREATE TABLE musicshowmc (
    mc_id INT AUTO_INCREMENT PRIMARY KEY,
    mc_pairname VARCHAR(100) NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Music
CREATE TABLE songs (
    song_id INT AUTO_INCREMENT PRIMARY KEY,
    songtitle VARCHAR(255) NOT NULL,
    artist VARCHAR(255),
    album VARCHAR(255) DEFAULT NULL,
    track_number INT DEFAULT 1,
    spotify_link VARCHAR(255) DEFAULT NULL,
    youtube_link VARCHAR(255) DEFAULT NULL,
    CONSTRAINT unique_song_album UNIQUE (songtitle, artist, album)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;



-- ====================================================================
-- SELF-REFERENCING & DEPENDENT MAIN TABLES
-- ====================================================================

-- Groups table
CREATE TABLE kgroups (
    group_id INT AUTO_INCREMENT PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    group_desc TEXT,
    grouptype ENUM ('bg', 'gg', 'solo', 'band', 'coed', 'subunit') DEFAULT NULL,
    parent_id INT DEFAULT NULL,
    debutdate DATE,
    CONSTRAINT fk_group_parent FOREIGN KEY (parent_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Showtitle table
CREATE TABLE showtitle (
    title_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    releaseYear VARCHAR(50),
    totalSeasons INT DEFAULT NULL,
    totalEpisodes INT DEFAULT NULL,
    watchStatus ENUM('Not Started', 'Watching', 'Finished') DEFAULT NULL,
    title_img VARCHAR(255) DEFAULT 'pics/placeholder.jpg',
    variety BOOLEAN DEFAULT FALSE,
    sort_date DATE DEFAULT NULL,
    season_order TEXT DEFAULT NULL,
    webstatus ENUM('show','ghost','archived','undecided'),
    INDEX idx_title_status (webstatus, watchStatus)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video table
CREATE TABLE video (
    video_id INT AUTO_INCREMENT PRIMARY KEY,
    season VARCHAR(25) NULL,
    episodeNumber VARCHAR(10) NULL,
    video_title VARCHAR(255),
    releaseDate DATE,
    title_extras ENUM('Teaser','Behind','Extra','DVD'),
    video_notes TEXT,
    is_variety BOOLEAN DEFAULT FALSE,
    webstatus ENUM('show','timeline','ghost','archived','undecided')
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Livestream tags
CREATE TABLE livestreamtags (
    tag_id INT AUTO_INCREMENT PRIMARY KEY,
    tag_name VARCHAR(100),
    member_id INT,
    group_id INT,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Specific season name table
CREATE TABLE season_names (
    title_id INT NOT NULL,
    season_number VARCHAR(25) NOT NULL,
    season_name VARCHAR(255) NOT NULL,
    PRIMARY KEY (title_id, season_number),
    FOREIGN KEY (title_id) REFERENCES showtitle(title_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;




-- ====================================================================
-- RELATIONSHIP / JUNCTION TABLES (MANY-TO-MANY)
-- ====================================================================

-- Member ↔ Group
CREATE TABLE member_groups (
    member_id INT NOT NULL,
    group_id INT NOT NULL,
    PRIMARY KEY (member_id, group_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Showtitle ↔ Group ↔ Member
CREATE TABLE showownership (
    title_id INT NOT NULL,
    group_id INT NULL,
    member_id INT NULL,
    FOREIGN KEY (title_id) REFERENCES showtitle(title_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    INDEX idx_so_ids (title_id, group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Group ↔ Member (Video guest listing)
CREATE TABLE videoguest (
    video_id INT NOT NULL,
    member_id INT NULL,
    group_id INT NULL,
    FOREIGN KEY (video_id) REFERENCES video(video_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Group ↔ Member (Cameos / special appearances / non full guest)
CREATE TABLE tinyguest (
    video_id INT NOT NULL,
    member_id INT NULL,
    group_id INT NULL,
    FOREIGN KEY (video_id) REFERENCES video(video_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Group ↔ Member (Video host/owner listing)
CREATE TABLE videohost (
    host_id INT AUTO_INCREMENT PRIMARY KEY,
    video_id INT NOT NULL,
    member_id INT NULL,
    group_id INT NULL,
    FOREIGN KEY (video_id) REFERENCES video(video_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id),
    UNIQUE (video_id, member_id, group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Showtitle
CREATE TABLE video_showtitle (
    video_id INT NOT NULL,
    title_id INT NOT NULL,
    PRIMARY KEY (video_id, title_id),
    FOREIGN KEY (video_id) REFERENCES video(video_id) ON DELETE CASCADE,
    FOREIGN KEY (title_id) REFERENCES showtitle(title_id) ON DELETE CASCADE,
    INDEX idx_vs_ids (video_id, title_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Showtitle ↔ Category
CREATE TABLE showtitle_category (
    title_id INT NOT NULL,
    category_id INT NOT NULL,
    PRIMARY KEY (title_id, category_id),
    FOREIGN KEY (title_id) REFERENCES showtitle(title_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(category_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Showtitle ↔ Group (Showtitle ownership)
CREATE TABLE titleguest (
    title_id INT NOT NULL,
    group_id INT NOT NULL,
    PRIMARY KEY (title_id, group_id),
    FOREIGN KEY (title_id) REFERENCES showtitle(title_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Livestream tags
CREATE TABLE videolivetags (
    video_id INT NOT NULL,
    tag_id INT NOT NULL,
    PRIMARY KEY (video_id, tag_id),
    FOREIGN KEY (video_id) REFERENCES video(video_id),
    FOREIGN KEY (tag_id) REFERENCES livestreamtags(tag_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- MC ↔ Members
CREATE TABLE mc_members (
    mc_id INT NOT NULL,
    member_id INT NOT NULL,
    PRIMARY KEY (mc_id, member_id),
    FOREIGN KEY (mc_id) REFERENCES musicshowmc(mc_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Music show ↔ MCs
CREATE TABLE mushow_mcs (
    mushow_id INT NOT NULL,
    mc_id INT NOT NULL,
    PRIMARY KEY (mushow_id, mc_id),
    FOREIGN KEY (mushow_id) REFERENCES showtitle(title_id),
    FOREIGN KEY (mc_id) REFERENCES musicshowmc(mc_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- Video ↔ Music show MC
CREATE TABLE videomushowmc (
    video_id INT NOT NULL,
    mc_id INT NOT NULL,
    member_id INT NOT NULL,
    group_id INT NULL,
    PRIMARY KEY (video_id, mc_id, member_id),
    FOREIGN KEY (video_id) REFERENCES video(video_id),
    FOREIGN KEY (mc_id) REFERENCES musicshowmc(mc_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id),
    CONSTRAINT fk_vmc_group FOREIGN KEY (group_id) REFERENCES kgroups(group_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- (livestream) Video ↔ Songs
CREATE TABLE video_music_recs (
    video_id INT NOT NULL,
    song_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sort_order INT DEFAULT 0,
    PRIMARY KEY (video_id, song_id),
    FOREIGN KEY (video_id) REFERENCES video(video_id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(song_id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;



-- ====================================================================
-- DATABASE TRIGGERS
-- ====================================================================

-- Drop all tinyguest triggers completely so they NEVER back-fill titleguest
DROP TRIGGER IF EXISTS trg_tinyguest_after_insert;
DROP TRIGGER IF EXISTS trg_tinyguest_after_update;
DROP TRIGGER IF EXISTS trg_tinyguest_after_delete;

-- Reset videoguest triggers to protect titleguest cleanly
DROP TRIGGER IF EXISTS trg_videoguest_after_insert;
DROP TRIGGER IF EXISTS trg_videoguest_after_update;
DROP TRIGGER IF EXISTS trg_videoguest_after_delete;

DELIMITER $$

-- Trigger: Automatically back-fill titleguest when a group is added to a video clip
CREATE TRIGGER trg_videoguest_after_insert
AFTER INSERT ON videoguest
FOR EACH ROW
BEGIN
    IF NEW.group_id IS NOT NULL THEN
        INSERT IGNORE INTO titleguest (title_id, group_id)
        SELECT vs.title_id, NEW.group_id
        FROM video_showtitle vs
        WHERE vs.video_id = NEW.video_id;
    END IF;
END$$

-- Trigger: Update titleguest mapping if a video guest group assignment changes
CREATE TRIGGER trg_videoguest_after_update
AFTER UPDATE ON videoguest
FOR EACH ROW
BEGIN
    IF OLD.group_id IS NOT NULL AND OLD.group_id != IFNULL(NEW.group_id, 0) THEN
        DELETE tg FROM titleguest tg
        JOIN video_showtitle vs_old ON tg.title_id = vs_old.title_id
        WHERE tg.group_id = OLD.group_id
          AND vs_old.video_id = OLD.video_id
          AND NOT EXISTS (
              SELECT 1 FROM video_showtitle vs
              JOIN videoguest vg ON vs.video_id = vg.video_id
              WHERE vs.title_id = vs_old.title_id AND vg.group_id = OLD.group_id
          );
    END IF;

    IF NEW.group_id IS NOT NULL THEN
        INSERT IGNORE INTO titleguest (title_id, group_id)
        SELECT vs.title_id, NEW.group_id
        FROM video_showtitle vs
        WHERE vs.video_id = NEW.video_id;
    END IF;
END$$

-- Trigger: Clean up titleguest if a video guest is removed and no other clips feature them
CREATE TRIGGER trg_videoguest_after_delete
AFTER DELETE ON videoguest
FOR EACH ROW
BEGIN
    DELETE tg FROM titleguest tg
    JOIN video_showtitle vs_del ON tg.title_id = vs_del.title_id
    WHERE tg.group_id = OLD.group_id
      AND vs_del.video_id = OLD.video_id
      AND NOT EXISTS (
          SELECT 1 FROM video_showtitle vs
          JOIN videoguest vg ON vs.video_id = vg.video_id
          WHERE vs.title_id = vs_del.title_id AND vg.group_id = OLD.group_id
      );
END$$

DELIMITER ;