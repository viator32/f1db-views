/*---------------------------------------------------------------
  SCHEMA to keep derived objects separate
----------------------------------------------------------------*/
CREATE SCHEMA IF NOT EXISTS analysis;
SET search_path = public, analysis;

/*---------------------------------------------------------------
  1.  Track projection  (location + car_data)  [heavy!]
----------------------------------------------------------------*/
DROP MATERIALIZED VIEW IF EXISTS analysis.mv_track_projection;
CREATE MATERIALIZED VIEW analysis.mv_track_projection AS
SELECT
    l.session_id,
    l.driver_id,
    d.full_name,
    tm.team_name,
    t.team_colour,
    l.lap_number,
    date_trunc('second', l.time) AS t,   -- round to second
    l.x, l.y, l.z,
    cd.speed,
    cd.gear,
    cd.throttle,
    cd.brake_is_pressed
FROM location l
JOIN driver d          USING (driver_id)
JOIN team_membership tm USING (driver_id, session_id)
JOIN team t            ON t.team_name = tm.team_name
LEFT JOIN car_data cd  ON cd.time = l.time
                      AND cd.driver_id  = l.driver_id
                      AND cd.session_id = l.session_id
WITH NO DATA;

CREATE UNIQUE INDEX ON analysis.mv_track_projection(session_id, driver_id, t, lap_number);

/*---------------------------------------------------------------
  2.  Stint summary
----------------------------------------------------------------*/
DROP MATERIALIZED VIEW IF EXISTS analysis.mv_stint_summary;
CREATE MATERIALIZED VIEW analysis.mv_stint_summary AS
SELECT
    st.session_id,
    st.driver_id,
    d.full_name,
    tm.team_name,
    t.team_colour,
    st.stint_number,
    st.compound,
    st.lap_start,
    st.lap_end,
    COUNT(*)                               AS num_laps,
    ROUND(AVG(l.duration),2)               AS avg_lap_s,
    ROUND(MIN(l.duration),2)               AS best_lap_s
FROM stint             st
JOIN lap               l  USING (driver_id, session_id)
JOIN driver            d  USING (driver_id)
JOIN team_membership   tm USING (driver_id, session_id)
JOIN team              t  ON t.team_name = tm.team_name
WHERE l.lap_number BETWEEN st.lap_start AND st.lap_end
GROUP BY st.session_id, st.driver_id, d.full_name,
         tm.team_name, t.team_colour,
         st.stint_number, st.compound, st.lap_start, st.lap_end
WITH NO DATA;

CREATE UNIQUE INDEX ON analysis.mv_stint_summary(session_id, driver_id, stint_number);

/*---------------------------------------------------------------
  3.  Pit-stop timeline
----------------------------------------------------------------*/
DROP MATERIALIZED VIEW IF EXISTS analysis.mv_pit_stop_timeline;
CREATE MATERIALIZED VIEW analysis.mv_pit_stop_timeline AS
SELECT
    ps.session_id,
    ps.driver_id,
    d.full_name,
    tm.team_name,
    t.team_colour,
    ps.lap_number,
    ps.time,
    ps.duration
FROM pit_stop          ps
JOIN driver            d  USING (driver_id)
JOIN team_membership   tm USING (driver_id, session_id)
JOIN team              t  ON t.team_name = tm.team_name
WITH NO DATA;

CREATE UNIQUE INDEX ON analysis.mv_pit_stop_timeline(session_id, driver_id, time);

/*---------------------------------------------------------------
  4.  Sector performance  (best per sector)
----------------------------------------------------------------*/
DROP MATERIALIZED VIEW IF EXISTS analysis.mv_sector_performance;
CREATE MATERIALIZED VIEW analysis.mv_sector_performance AS
SELECT
    s.session_id,
    s.driver_id,
    d.full_name,
    tm.team_name,
    t.team_colour,
    sec.sector_number,
    MIN(sec.duration) AS best_sector_s
FROM lap               s
JOIN sector            sec ON sec.lap_id = s.lap_id
JOIN driver            d   ON d.driver_id = s.driver_id
JOIN team_membership   tm  ON tm.driver_id = s.driver_id
                           AND tm.session_id = s.session_id
JOIN team              t   ON t.team_name = tm.team_name
GROUP BY s.session_id, s.driver_id, d.full_name, tm.team_name, t.team_colour,
         sec.sector_number
WITH NO DATA;

CREATE UNIQUE INDEX ON analysis.mv_sector_performance(session_id, driver_id, sector_number);

/*---------------------------------------------------------------
  5.  Season driver summary
----------------------------------------------------------------*/
DROP MATERIALIZED VIEW IF EXISTS analysis.mv_driver_summary_season;
CREATE MATERIALIZED VIEW analysis.mv_driver_summary_season AS
SELECT
    year,
    full_name,
    SUM(points) AS season_points,
    MIN(position) FILTER (WHERE session_type='Race') AS best_finish
FROM v_session_results
GROUP BY year, full_name
WITH NO DATA;
