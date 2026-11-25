-- Give GTFS Realtime feeds the location groups of the schedule feeds they reference.
INSERT INTO feedosmlocationgroup (feed_id, group_id, stops_count)
SELECT fr.gtfs_rt_feed_id, g.group_id, g.stops_count
FROM feedreference fr
JOIN feedosmlocationgroup g ON g.feed_id = fr.gtfs_feed_id
ON CONFLICT (feed_id, group_id) DO NOTHING;
