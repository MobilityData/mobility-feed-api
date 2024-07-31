/**
 * This file was auto-generated by openapi-typescript.
 * Do not make direct changes to the file.
 */

export interface paths {
  '/v1/feeds': {
    /** @description Get some (or all) feeds from the Mobility Database. The items are sorted by provider in alphabetical ascending order. */
    get: operations['getFeeds'];
  };
  '/v1/feeds/{id}': {
    /** @description Get the specified feed from the Mobility Database. */
    get: operations['getFeed'];
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
  };
  '/v1/gtfs_feeds': {
    /** @description Get some (or all) GTFS feeds from the Mobility Database. */
    get: operations['getGtfsFeeds'];
  };
  '/v1/gtfs_rt_feeds': {
    /** @description Get some (or all) GTFS Realtime feeds from the Mobility Database. */
    get: operations['getGtfsRtFeeds'];
  };
  '/v1/gtfs_feeds/{id}': {
    /** @description Get the specified GTFS feed from the Mobility Database. Once a week, we check if the latest dataset has been updated and, if so, we update it in our system accordingly. */
    get: operations['getGtfsFeed'];
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
  };
  '/v1/gtfs_rt_feeds/{id}': {
    /** @description Get the specified GTFS Realtime feed from the Mobility Database. */
    get: operations['getGtfsRtFeed'];
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
  };
  '/v1/gtfs_feeds/{id}/datasets': {
    /** @description Get a list of datasets related to a GTFS feed. Once a week, we check if the latest dataset has been updated and, if so, we update it in our system accordingly. */
    get: operations['getGtfsFeedDatasets'];
    parameters: {
      path: {
        id: components['parameters']['feed_id_of_datasets_path_param'];
      };
    };
  };
  '/v1/gtfs_feeds/{id}/gtfs_rt_feeds': {
    /** @description Get a list of GTFS Realtime related to a GTFS feed. */
    get: operations['getGtfsFeedGtfsRtFeeds'];
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
  };
  '/v1/datasets/gtfs/{id}': {
    /** @description Get the specified dataset from the Mobility Database. */
    get: operations['getDatasetGtfs'];
  };
  '/v1/metadata': {
    /** @description Get metadata about this API. */
    get: operations['getMetadata'];
  };
  '/v1/search': {
    /**
     * @description Search feeds on feed name, location and provider's information.
     * <br>
     * The current implementation leverages the text search functionalities from [PostgreSQL](https://www.postgresql.org/docs/current/textsearch-controls.html), in particulary `plainto_tsquery`.
     * <br><br>
     * Points to consider while using search endpoint:
     * <br>
     * - Operators are not currently supported. Operators are ignored as stop-words.
     * - Search is based on lexemes(English) and case insensitive. The search_text_query_param is parsed and normalized much as for to_tsvector, then the & (AND) tsquery operator is inserted between surviving words.
     * - The search will match all the lexemes with an AND operator. So, all lexemes must be present in the document.
     * - Our current implementation only creates English lexemes. We are currently considering adding support to more languages.
     * - The order of the words is not relevant for matching. The query __New York__ should give you the same results as __York New__.
     * <br><br>
     * Example:
     * <br>
     * Query: New York Transit
     * <br>
     * Search Executed: 'new' & york & 'transit'
     * <br>
     */
    get: operations['searchFeeds'];
  };
}

export type webhooks = Record<string, never>;

export interface components {
  schemas: {
    Redirect: {
      /**
       * @description The feed ID that should be used in replacement of the current one.
       * @example mdb-10
       */
      target_id?: string;
      /**
       * @description A comment explaining the redirect.
       * @example Redirected because of a change of URL.
       */
      comment?: string;
    };
    BasicFeed: {
      /**
       * @description Unique identifier used as a key for the feeds table.
       * @example mdb-1210
       */
      id?: string;
      /**
       * @example gtfs
       * @enum {string}
       */
      data_type?: 'gtfs' | 'gtfs_rt';
      /**
       * @description Describes status of the Feed. Should be one of
       *   * `active` Feed should be used in public trip planners.
       *   * `deprecated` Feed is explicitly deprecated and should not be used in public trip planners.
       *   * `inactive` Feed hasn't been recently updated and should be used at risk of providing outdated information.
       *   * `development` Feed is being used for development purposes and should not be used in public trip planners.
       *
       * @example deprecated
       * @enum {string}
       */
      status?: 'active' | 'deprecated' | 'inactive' | 'development';
      /**
       * Format: date-time
       * @description The date and time the feed was added to the database, in ISO 8601 date-time format.
       * @example "2023-07-10T22:06:00.000Z"
       */
      created_at?: string;
      external_ids?: components['schemas']['ExternalIds'];
      /**
       * @description A commonly used name for the transit provider included in the feed.
       * @example Los Angeles Department of Transportation (LADOT, DASH, Commuter Express)
       */
      provider?: string;
      /**
       * @description An optional description of the data feed, e.g to specify if the data feed is an aggregate of  multiple providers, or which network is represented by the feed.
       *
       * @example Bus
       */
      feed_name?: string;
      /** @description A note to clarify complex use cases for consumers. */
      note?: string;
      /**
       * @description Use to contact the feed producer.
       * @example someEmail@ladotbus.com
       */
      feed_contact_email?: string;
      source_info?: components['schemas']['SourceInfo'];
      redirects?: Array<components['schemas']['Redirect']>;
    };
    GtfsFeed: {
      data_type: 'gtfs';
    } & Omit<components['schemas']['BasicFeed'], 'data_type'> & {
        locations?: components['schemas']['Locations'];
        latest_dataset?: components['schemas']['LatestDataset'];
      };
    GtfsRTFeed: {
      data_type: 'gtfs_rt';
    } & Omit<components['schemas']['BasicFeed'], 'data_type'> & {
        entity_types?: Array<'vp' | 'tu' | 'sa'>;
        /** @description A list of the GTFS feeds that the real time source is associated with, represented by their MDB source IDs. */
        feed_references?: string[];
        locations?: components['schemas']['Locations'];
      };
    SearchFeedItemResult: {
      /**
       * @description Unique identifier used as a key for the feeds table.
       * @example mdb-1210
       */
      id: string;
      /**
       * @example gtfs
       * @enum {string}
       */
      data_type: 'gtfs' | 'gtfs_rt';
      /**
       * @description Describes status of the Feed. Should be one of
       *   * `active` Feed should be used in public trip planners.
       *   * `deprecated` Feed is explicitly deprecated and should not be used in public trip planners.
       *   * `inactive` Feed hasn't been recently updated and should be used at risk of providing outdated information.
       *   * `development` Feed is being used for development purposes and should not be used in public trip planners.
       *
       * @example deprecated
       * @enum {string}
       */
      status: 'active' | 'deprecated' | 'inactive' | 'development';
      /**
       * Format: date-time
       * @description The date and time the feed was added to the database, in ISO 8601 date-time format.
       * @example "2023-07-10T22:06:00.000Z"
       */
      created_at?: string;
      external_ids?: components['schemas']['ExternalIds'];
      /**
       * @description A commonly used name for the transit provider included in the feed.
       * @example Los Angeles Department of Transportation (LADOT, DASH, Commuter Express)
       */
      provider?: string;
      /**
       * @description An optional description of the data feed, e.g to specify if the data feed is an aggregate of  multiple providers, or which network is represented by the feed.
       *
       * @example Bus
       */
      feed_name?: string;
      /** @description A note to clarify complex use cases for consumers. */
      note?: string;
      /**
       * @description Use to contact the feed producer.
       * @example someEmail@ladotbus.com
       */
      feed_contact_email?: string;
      source_info?: components['schemas']['SourceInfo'];
      redirects?: Array<components['schemas']['Redirect']>;
      locations?: components['schemas']['Locations'];
      latest_dataset?: components['schemas']['LatestDataset'];
      entity_types?: Array<'vp' | 'tu' | 'sa'>;
      /** @description A list of the GTFS feeds that the real time source is associated with, represented by their MDB source IDs. */
      feed_references?: string[];
    };
    BasicFeeds: Array<components['schemas']['BasicFeed']>;
    GtfsFeeds: Array<components['schemas']['GtfsFeed']>;
    GtfsRTFeeds: Array<components['schemas']['GtfsRTFeed']>;
    LatestDataset: {
      /**
       * @description Identifier of the latest dataset for this feed.
       * @example mdb-1210-202402121801
       */
      id?: string;
      /**
       * Format: url
       * @description As a convenience, the URL of the latest uploaded dataset hosted by MobilityData.  It should be the same URL as the one found in the latest dataset id dataset. An alternative way to find this is to use the latest dataset id to obtain the dataset and then use its hosted_url.
       *
       * @example https://storage.googleapis.com/mobilitydata-datasets-prod/mdb-1210/mdb-1210-202402121801/mdb-1210-202402121801.zip
       */
      hosted_url?: string;
      bounding_box?: components['schemas']['BoundingBox'];
      /**
       * Format: date-time
       * @description The date and time the dataset was downloaded from the producer, in ISO 8601 date-time format.
       * @example "2023-07-10T22:06:00.000Z"
       */
      downloaded_at?: string;
      /**
       * @description A hash of the dataset.
       * @example ad3805c4941cd37881ff40c342e831b5f5224f3d8a9a2ec3ac197d3652c78e42
       */
      hash?: string;
      validation_report?: {
        /** @example 10 */
        total_error?: number;
        /** @example 20 */
        total_warning?: number;
        /** @example 30 */
        total_info?: number;
        /** @example 1 */
        unique_error_count?: number;
        /** @example 2 */
        unique_warning_count?: number;
        /** @example 3 */
        unique_info_count?: number;
      };
    };
    ExternalIds: Array<components['schemas']['ExternalId']>;
    ExternalId: {
      /**
       * @description The ID that can be use to find the feed data in an external or legacy database.
       * @example 1210
       */
      external_id?: string;
      /**
       * @description The source of the external ID, e.g. the name of the database where the external ID can be used.
       * @example mdb
       */
      source?: string;
    };
    SourceInfo: {
      /**
       * Format: url
       * @description URL where the producer is providing the dataset.  Refer to the authentication information to know how to access this URL.
       *
       * @example https://ladotbus.com/gtfs
       */
      producer_url?: string;
      /**
       * @description Defines the type of authentication required to access the `producer_url`. Valid values for this field are:
       *   * 0 or (empty) - No authentication required.
       *   * 1 - The authentication requires an API key, which should be passed as value of the parameter api_key_parameter_name in the URL. Please visit URL in authentication_info_url for more information.
       *   * 2 - The authentication requires an HTTP header, which should be passed as the value of the header api_key_parameter_name in the HTTP request.
       * When not provided, the authentication type is assumed to be 0.
       *
       * @example 2
       * @enum {integer}
       */
      authentication_type?: 0 | 1 | 2;
      /**
       * Format: url
       * @description Contains a URL to a human-readable page describing how the authentication should be performed and how credentials can be created.  This field is required for `authentication_type=1` and `authentication_type=2`.
       *
       * @example https://apidevelopers.ladottransit.com
       */
      authentication_info_url?: string;
      /**
       * @description Defines the name of the parameter to pass in the URL to provide the API key. This field is required for `authentication_type=1` and `authentication_type=2`.
       *
       * @example Ocp-Apim-Subscription-Key
       */
      api_key_parameter_name?: string;
      /**
       * Format: url
       * @description A URL where to find the license for the feed.
       * @example https://www.ladottransit.com/dla.html
       */
      license_url?: string;
    };
    Locations: Array<components['schemas']['Location']>;
    Location: {
      /**
       * @description ISO 3166-1 alpha-2 code designating the country where the system is located.  For a list of valid codes [see here](https://unece.org/trade/uncefact/unlocode-country-subdivisions-iso-3166-2).
       *
       * @example US
       */
      country_code?: string;
      /**
       * @description ISO 3166-2 subdivision name designating the subdivision (e.g province, state, region) where the system is located.  For a list of valid names [see here](https://unece.org/trade/uncefact/unlocode-country-subdivisions-iso-3166-2).
       *
       * @example California
       */
      subdivision_name?: string;
      /**
       * @description Primary municipality in which the transit system is located.
       * @example Los Angeles
       */
      municipality?: string;
    };
    BasicDataset: {
      /**
       * @description Unique identifier used as a key for the datasets table.
       * @example mdb-10-202402080058
       */
      id?: string;
      /**
       * @description ID of the feed related to this dataset.
       * @example mdb-10
       */
      feed_id?: string;
    };
    GtfsDataset: components['schemas']['BasicDataset'] & {
      /**
       * @description The URL of the dataset data as hosted by MobilityData. No authentication required.
       * @example https://storage.googleapis.com/storage/v1/b/mdb-latest/o/us-maine-casco-bay-lines-gtfs-1.zip?alt=media
       */
      hosted_url?: string;
      /** @description A note to clarify complex use cases for consumers. */
      note?: string;
      /**
       * Format: date-time
       * @description The date and time the dataset was downloaded from the producer, in ISO 8601 date-time format.
       * @example "2023-07-10T22:06:00.000Z"
       */
      downloaded_at?: string;
      /**
       * @description A hash of the dataset.
       * @example 6497e85e34390b8b377130881f2f10ec29c18a80dd6005d504a2038cdd00aa71
       */
      hash?: string;
      bounding_box?: components['schemas']['BoundingBox'];
      validation_report?: components['schemas']['ValidationReport'];
    };
    /** @description Bounding box of the dataset when it was first added to the catalog. */
    BoundingBox: {
      /**
       * @description The minimum latitude for the dataset bounding box.
       * @example 33.721601
       */
      minimum_latitude?: number;
      /**
       * @description The maximum latitude for the dataset bounding box.
       * @example 34.323077
       */
      maximum_latitude?: number;
      /**
       * @description The minimum longitude for the dataset bounding box.
       * @example -118.882829
       */
      minimum_longitude?: number;
      /**
       * @description The maximum longitude for the dataset bounding box.
       * @example -118.131748
       */
      maximum_longitude?: number;
    };
    GtfsDatasets: Array<components['schemas']['GtfsDataset']>;
    Metadata: {
      /** @example 1.0.0 */
      version?: string;
      /** @example 8635fdac4fbff025b4eaca6972fcc9504bc1552d */
      commit_hash?: string;
    };
    /** @description Validation report */
    ValidationReport: {
      /**
       * Format: date-time
       * @description The date and time the report was generated, in ISO 8601 date-time format.
       * @example "2023-07-10T22:06:00.000Z"
       */
      validated_at?: string;
      /** @description An array of features for this dataset. */
      features?: string[];
      /** @example 4.2.0 */
      validator_version?: string;
      /** @example 10 */
      total_error?: number;
      /** @example 20 */
      total_warning?: number;
      /** @example 30 */
      total_info?: number;
      /** @example 1 */
      unique_error_count?: number;
      /** @example 2 */
      unique_warning_count?: number;
      /** @example 3 */
      unique_info_count?: number;
      /**
       * Format: url
       * @description JSON validation report URL
       * @example https://storage.googleapis.com/mobilitydata-datasets-dev/mdb-10/mdb-10-202312181718/mdb-10-202312181718-report-4_2_0.json
       */
      url_json?: string;
      /**
       * Format: url
       * @description HTML validation report URL
       * @example https://storage.googleapis.com/mobilitydata-datasets-dev/mdb-10/mdb-10-202312181718/mdb-10-202312181718-report-4_2_0.html
       */
      url_html?: string;
    };
  };
  responses: never;
  parameters: {
    /** @description Filter feeds by their status. [Status definitions defined here](https://github.com/MobilityData/mobility-database-catalogs?tab=readme-ov-file#gtfs-schedule-schema) */
    status?: 'active' | 'deprecated' | 'inactive' | 'development';
    /** @description Filter feeds by their status. [Status definitions defined here](https://github.com/MobilityData/mobility-database-catalogs?tab=readme-ov-file#gtfs-schedule-schema) */
    statuses?: Array<'active' | 'deprecated' | 'inactive' | 'development'>;
    /** @description List only feeds with the specified value. Can be a partial match. Case insensitive. */
    provider?: string;
    /** @description List only feeds with the specified value. Can be a partial match. Case insensitive. */
    producer_url?: string;
    /** @description Filter feeds by their entity type. Expects a comma separated list of all types to fetch. */
    entity_types?: string;
    /** @description Filter feeds by their exact country code. */
    country_code?: string;
    /** @description List only feeds with the specified value. Can be a partial match. Case insensitive. */
    subdivision_name?: string;
    /** @description List only feeds with the specified value. Can be a partial match. Case insensitive. */
    municipality?: string;
    /** @description Filter feed datasets with downloaded date greater or equal to given date. Date should be in ISO 8601 date-time format. */
    downloaded_after?: string;
    /** @description Filter feed datasets with downloaded date less or equal to given date. Date should be in ISO 8601 date-time format. */
    downloaded_before?: string;
    /**
     * @description Specify the minimum and maximum latitudes of the bounding box to use for filtering.
     *  <br>Filters by the bounding box of the `LatestDataset` for a feed.
     *  <br>Must be specified alongside `dataset_longitudes`.
     */
    dataset_latitudes?: string;
    /** @description Specify the minimum and maximum longitudes of the bounding box to use for filtering. <br>Filters by the bounding box of the `LatestDataset` for a feed. <br>Must be specified alongside `dataset_latitudes`. */
    dataset_longitudes?: string;
    /**
     * @description Specify the filtering method to use with the dataset_latitudes and dataset_longitudes parameters.
     *  * `completely_enclosed` - Get resources that are completely enclosed in the specified bounding box.
     *  * `partially_enclosed` - Get resources that are partially enclosed in the specified bounding box.
     *  * `disjoint` - Get resources that are completely outside the specified bounding box.
     *
     * @example completely_enclosed
     */
    bounding_filter_method?:
      | 'completely_enclosed'
      | 'partially_enclosed'
      | 'disjoint';
    /** @description If true, only return the latest dataset. */
    latest_query_param?: boolean;
    /** @description The number of items to be returned. */
    limit_query_param?: number;
    /** @description Offset of the first item to return. */
    offset?: number;
    /** @description General search query to match against transit provider, location, and feed name. */
    search_text_query_param?: string;
    /** @description Unique identifier used as a key for the feeds table. */
    data_type_query_param?: 'gtfs' | 'gtfs_rt';
    /** @description The feed ID of the requested feed. */
    feed_id_query_param?: string;
    /** @description The feed ID of the requested feed. */
    feed_id_path_param: string;
    /** @description The ID of the feed for which to obtain datasets. */
    feed_id_of_datasets_path_param: string;
    /** @description The ID of the requested dataset. */
    dataset_id_path_param: string;
  };
  requestBodies: never;
  headers: never;
  pathItems: never;
}

export type $defs = Record<string, never>;

export interface external {
  'BearerTokenSchema.yaml': {
    paths: Record<string, never>;
    webhooks: Record<string, never>;
    components: {
      schemas: never;
      responses: never;
      parameters: never;
      requestBodies: never;
      headers: never;
      pathItems: never;
    };
    $defs: Record<string, never>;
  };
}

export interface operations {
  /** @description Get some (or all) feeds from the Mobility Database. The items are sorted by provider in alphabetical ascending order. */
  getFeeds: {
    parameters: {
      query?: {
        limit?: components['parameters']['limit_query_param'];
        offset?: components['parameters']['offset'];
        status?: components['parameters']['status'];
        provider?: components['parameters']['provider'];
        producer_url?: components['parameters']['producer_url'];
      };
    };
    responses: {
      /** @description Successful pull of the feeds common info.  This info has a reduced set of fields that are common to all types of feeds. */
      200: {
        content: {
          'application/json': components['schemas']['BasicFeeds'];
        };
      };
    };
  };
  /** @description Get the specified feed from the Mobility Database. */
  getFeed: {
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the feeds common info for the provided ID. This info has a reduced set of fields that are common to all types of feeds. */
      200: {
        content: {
          'application/json': components['schemas']['BasicFeed'];
        };
      };
    };
  };
  /** @description Get some (or all) GTFS feeds from the Mobility Database. */
  getGtfsFeeds: {
    parameters: {
      query?: {
        limit?: components['parameters']['limit_query_param'];
        offset?: components['parameters']['offset'];
        provider?: components['parameters']['provider'];
        producer_url?: components['parameters']['producer_url'];
        country_code?: components['parameters']['country_code'];
        subdivision_name?: components['parameters']['subdivision_name'];
        municipality?: components['parameters']['municipality'];
        dataset_latitudes?: components['parameters']['dataset_latitudes'];
        dataset_longitudes?: components['parameters']['dataset_longitudes'];
        bounding_filter_method?: components['parameters']['bounding_filter_method'];
      };
    };
    responses: {
      /** @description Successful pull of the GTFS feeds info. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsFeeds'];
        };
      };
    };
  };
  /** @description Get some (or all) GTFS Realtime feeds from the Mobility Database. */
  getGtfsRtFeeds: {
    parameters: {
      query?: {
        limit?: components['parameters']['limit_query_param'];
        offset?: components['parameters']['offset'];
        provider?: components['parameters']['provider'];
        producer_url?: components['parameters']['producer_url'];
        entity_types?: components['parameters']['entity_types'];
        country_code?: components['parameters']['country_code'];
        subdivision_name?: components['parameters']['subdivision_name'];
        municipality?: components['parameters']['municipality'];
      };
    };
    responses: {
      /** @description Successful pull of the GTFS Realtime feeds info. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsRTFeeds'];
        };
      };
    };
  };
  /** @description Get the specified GTFS feed from the Mobility Database. Once a week, we check if the latest dataset has been updated and, if so, we update it in our system accordingly. */
  getGtfsFeed: {
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the requested feed. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsFeed'];
        };
      };
    };
  };
  /** @description Get the specified GTFS Realtime feed from the Mobility Database. */
  getGtfsRtFeed: {
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the requested feed. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsRTFeed'];
        };
      };
    };
  };
  /** @description Get a list of datasets related to a GTFS feed. Once a week, we check if the latest dataset has been updated and, if so, we update it in our system accordingly. */
  getGtfsFeedDatasets: {
    parameters: {
      query?: {
        latest?: components['parameters']['latest_query_param'];
        limit?: components['parameters']['limit_query_param'];
        offset?: components['parameters']['offset'];
        downloaded_after?: components['parameters']['downloaded_after'];
        downloaded_before?: components['parameters']['downloaded_before'];
      };
      path: {
        id: components['parameters']['feed_id_of_datasets_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the requested datasets. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsDatasets'];
        };
      };
    };
  };
  /** @description Get a list of GTFS Realtime related to a GTFS feed. */
  getGtfsFeedGtfsRtFeeds: {
    parameters: {
      path: {
        id: components['parameters']['feed_id_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the GTFS Realtime feeds info related to a GTFS feed. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsRTFeeds'];
        };
      };
    };
  };
  /** @description Get the specified dataset from the Mobility Database. */
  getDatasetGtfs: {
    parameters: {
      path: {
        id: components['parameters']['dataset_id_path_param'];
      };
    };
    responses: {
      /** @description Successful pull of the requested dataset. */
      200: {
        content: {
          'application/json': components['schemas']['GtfsDataset'];
        };
      };
    };
  };
  /** @description Get metadata about this API. */
  getMetadata: {
    responses: {
      /** @description Successful pull of the metadata. */
      200: {
        content: {
          'application/json': components['schemas']['Metadata'];
        };
      };
    };
  };
  /**
   * @description Search feeds on feed name, location and provider's information.
   * <br>
   * The current implementation leverages the text search functionalities from [PostgreSQL](https://www.postgresql.org/docs/current/textsearch-controls.html), in particulary `plainto_tsquery`.
   * <br><br>
   * Points to consider while using search endpoint:
   * <br>
   * - Operators are not currently supported. Operators are ignored as stop-words.
   * - Search is based on lexemes(English) and case insensitive. The search_text_query_param is parsed and normalized much as for to_tsvector, then the & (AND) tsquery operator is inserted between surviving words.
   * - The search will match all the lexemes with an AND operator. So, all lexemes must be present in the document.
   * - Our current implementation only creates English lexemes. We are currently considering adding support to more languages.
   * - The order of the words is not relevant for matching. The query __New York__ should give you the same results as __York New__.
   * <br><br>
   * Example:
   * <br>
   * Query: New York Transit
   * <br>
   * Search Executed: 'new' & york & 'transit'
   * <br>
   */
  searchFeeds: {
    parameters: {
      query?: {
        limit?: components['parameters']['limit_query_param'];
        offset?: components['parameters']['offset'];
        status?: components['parameters']['statuses'];
        feed_id?: components['parameters']['feed_id_query_param'];
        data_type?: components['parameters']['data_type_query_param'];
        search_query?: components['parameters']['search_text_query_param'];
      };
    };
    responses: {
      /** @description Successful search feeds using full-text search on feed, location and provider's information, potentially returning a mixed array of different entity types. */
      200: {
        content: {
          'application/json': {
            /** @description The total number of matching entities found regardless the limit and offset parameters. */
            total?: number;
            results?: Array<components['schemas']['SearchFeedItemResult']>;
          };
        };
      };
    };
  };
}
