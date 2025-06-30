/* ----------  V1: final race / session results  ---------- */
CREATE OR REPLACE VIEW v_session_results AS
SELECT
    s.session_id,
    s.session_name,
    m.meeting_name,
    m.year,
    d.acronym,
    d.full_name,
    r.position,
    r.points,
    t.team_name,
    t.team_colour
FROM result r
JOIN driver d ON d.driver_id = r.driver_id
JOIN session s ON s.session_id = r.session_id
JOIN meeting m ON m.meeting_id = s.meeting_id
JOIN team_membership tm ON tm.driver_id = d.driver_id
                       AND tm.session_id = s.session_id
JOIN team t ON t.team_name = tm.team_name;

/* ----------  V2: lap times + sector split  ---------- */
CREATE OR REPLACE VIEW v_lap_detail AS
SELECT
    l.lap_id,
    l.session_id,
    l.driver_id,
    l.lap_number,
    l.duration            AS lap_time_s,
    s1.duration           AS sector1_s,
    s2.duration           AS sector2_s,
    s3.duration           AS sector3_s
FROM lap l
LEFT JOIN sector s1 ON s1.lap_id = l.lap_id AND s1.sector_number = 1
LEFT JOIN sector s2 ON s2.lap_id = l.lap_id AND s2.sector_number = 2
LEFT JOIN sector s3 ON s3.lap_id = l.lap_id AND s3.sector_number = 3;

/* ----------  V3: cumulative points per driver per season  ---------- */
CREATE OR REPLACE VIEW v_driver_points AS
SELECT
    full_name,
    year,
    SUM(points) AS season_points
FROM v_session_results
GROUP BY full_name, year;
