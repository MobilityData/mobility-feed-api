# Creating the list of feeds used for validator acceptance tests

- Initially the gtfs-validator acceptance tests (See [acceptance_test.yml](https://github.com/MobilityData/gtfs-validator/blob/master/.github/workflows/acceptance_test.yml)) would use all the feeds from the [mobility-database-catalog](https://github.com/MobilityData/mobility-database-catalogs). Over time this proved to be too time consuming so a curated list of feeds was created to speed up the tests while still providing good coverage.

- The curated list of feeds is obtained using a query on the [Mobility Database](https://mobilitydatabase.org/).

- The query is in create_list.sql. 

- You can use the create_acceptance_list.py script to generate the list. From the mobility-feed-api base directory, you can:
  - `cd scripts/validator-acceptance-feed-list`
  - `cp ../../config/.env.local .env`
  - Edit .env to point to the DB you want to query (usually the prod DB). You will probably have to tunnel to the DB (See [tunnel-create.sh](https://github.com/MobilityData/mobility-feed-api/blob/main/scripts/tunnel-create.sh)).
  - Make sure python is available (Suggestion is the use the same virtual environment as the api)
  - Execute the script: `python create_acceptance_list.py --env-file .env`
  - The list will be created in `acceptance_test_feed_list.csv`

If you have access to the [MobilityData Metabase site](https://metabase.mobilitydatabase.org/), a simpler way to get the list is to create a question using the query.

Once the list is created, it should be committed to the gtfs-validator repository, in the [scripts/mobility-database-harvester](https://github.com/MobilityData/gtfs-validator/tree/master/scripts/mobility-database-harvester) directory where it can be used by the gtfs-validator acceptance tests.
