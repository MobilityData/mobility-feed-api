WITH
  validation_report AS (
    SELECT
      *,
      summary.validatorVersion
    FROM
      `${project_id}.data_analytics.gtfs_validation_reports_*`
  ),
  most_recent_reports AS (
    SELECT
      t1.*
    FROM (
      SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY feedId ORDER BY validatedAt DESC) AS row_num
      FROM
        validation_report
      WHERE
        summary.validatorVersion = current_version
    ) AS t1
    WHERE row_num = 1
  ),
  old_version_reports AS (
    SELECT
      t1.*
    FROM (
      SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY feedId ORDER BY validatedAt DESC) AS row_num
      FROM
        validation_report
      WHERE
        summary.validatorVersion = previous_version
    ) AS t1
    WHERE row_num = 1
  ),
  most_recent_notices AS (
    SELECT
      feedId,
      datasetId,
      notice.code,
      notice.severity,
      notice.totalNotices
    FROM
      most_recent_reports,
      UNNEST(notices) AS notice
  ),
  old_version_notices AS (
    SELECT
      feedId,
      datasetId,
      notice.code,
      notice.severity,
      notice.totalNotices
    FROM
      old_version_reports,
      UNNEST(notices) AS notice
  ),
  merged_reports AS (
    SELECT
      COALESCE(most_recent_notices.feedId, old_version_notices.feedId) AS feedId,
      COALESCE(most_recent_notices.code, old_version_notices.code) AS code,
      old_version_notices.severity AS severity_previous,
      most_recent_notices.severity AS severity_current,
      IFNULL(old_version_notices.totalNotices, 0) AS totalNotices_previous,
      IFNULL(most_recent_notices.totalNotices, 0) AS totalNotices_current
    FROM
      old_version_notices
    FULL OUTER JOIN
      most_recent_notices
    ON
      old_version_notices.feedId = most_recent_notices.feedId
      AND old_version_notices.code = most_recent_notices.code
  )

SELECT
  feedId AS `Feed ID`,
  code AS `Code`,
  COALESCE(severity_previous, severity_current) AS `Severity`,
  totalNotices_previous AS `Total Previous`,
  totalNotices_current AS `Total Current`,
  GREATEST(totalNotices_current - totalNotices_previous, 0) AS `New Notices`,
  GREATEST(totalNotices_previous - totalNotices_current, 0) AS `Dropped Notices`
FROM
  merged_reports
ORDER BY
  `New Notices` DESC,
  `Dropped Notices` DESC
