-- validCheckSum: 1:any runAlways:true
DO $$
DECLARE
   _tbl text;
BEGIN
   FOR _tbl IN
      (SELECT quote_ident(table_schema) || '.' || quote_ident(table_name)
       FROM   information_schema.tables
       WHERE  table_type = 'BASE TABLE'
       AND    table_schema NOT LIKE 'pg_%'
       AND    table_schema != 'information_schema'
       AND    table_name NOT LIKE 'databasechangelog%' -- exclude Liquibase tables
       AND    table_name NOT LIKE 'spatial_ref_sys')  -- exclude PostGIS table
   LOOP
      EXECUTE 'TRUNCATE TABLE ' || _tbl || ' CASCADE';
   END LOOP;
END $$;