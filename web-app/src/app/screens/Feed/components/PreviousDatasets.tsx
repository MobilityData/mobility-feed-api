'use client';

import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import {
  DownloadOutlined,
  ReportOutlined,
  LaunchOutlined,
  CheckCircle,
} from '@mui/icons-material';
import { type paths } from '../../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SummarizeIcon from '@mui/icons-material/Summarize';
import CodeIcon from '@mui/icons-material/Code';
import DateRangeIcon from '@mui/icons-material/DateRange';
import { WEB_VALIDATOR_LINK } from '../../../constants/Navigation';
import { formatServiceDateRange } from '../Feed.functions';
import { useTranslations } from 'next-intl';
import { getGtfsFeedDatasets } from '../../../services/feeds';
import { getUserAccessToken } from '../../../services/profile-service';

export interface PreviousDatasetsProps {
  initialDatasets?: paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json'];
  feedId: string;
}

export default function PreviousDatasets({
  initialDatasets,
  feedId,
}: PreviousDatasetsProps): React.ReactElement {
  const theme = useTheme();
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
  const [datasets, setDatasets] = React.useState(initialDatasets ?? []);
  const [isLoadingDatasets, setIsLoadingDatasets] = React.useState(false);
  const [hasloadedAllDatasets, setHasLoadedAllDatasets] = React.useState(
    (initialDatasets?.length ?? 0) < 10,
  );
  const [scrollPosition, setScrollPosition] = React.useState(0);
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);

  const loadMoreDatasets = React.useCallback(
    async (offset: number) => {
      if (isLoadingDatasets || hasloadedAllDatasets) return;

      setIsLoadingDatasets(true);
      try {
        const accessToken = await getUserAccessToken();
        const newDatasets = await getGtfsFeedDatasets(feedId, accessToken, {
          limit: 10,
          offset,
        });

        if (
          newDatasets != null &&
          newDatasets.length > 0
        ) {
          if (newDatasets.length < 10) {
            setHasLoadedAllDatasets(true);
          }
          setDatasets((prev) => [...prev, ...newDatasets]);
        } else {
          setHasLoadedAllDatasets(true);
        }
      } catch (error) {
        console.error('Error loading more datasets:', error);
        setHasLoadedAllDatasets(true);
      } finally {
        setIsLoadingDatasets(false);
      }
    },
    [feedId, isLoadingDatasets, hasloadedAllDatasets],
  );

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (
          entry.isIntersecting &&
          !hasloadedAllDatasets &&
          !isLoadingDatasets &&
          datasets.length > 0
        ) {
          const currentNumberOfDatasets = datasets.length;
          const currentScrollPosition = listRef.current?.scrollTop ?? 0;
          void loadMoreDatasets(currentNumberOfDatasets);
          setScrollPosition(currentScrollPosition);
        }
      },
      {
        root: listRef.current,
        threshold: 1.0,
        rootMargin: '20px',
      },
    );

    const bottomElement = bottomRef.current;
    if (bottomElement != null) {
      observer.observe(bottomElement);
    }

    return () => {
      if (bottomElement != null) {
        observer.unobserve(bottomElement);
      }
    };
  }, [datasets, hasloadedAllDatasets, isLoadingDatasets, loadMoreDatasets]);

  /**
   * When datasets loads, the default behavior is to bring the user to the bottom
   * This retriggers the loading of datasets infinitely
   * This effect manually controls the scroll position when data loads
   */
  React.useEffect(() => {
    const list = listRef.current;
    if (list != null && list.scrollTop != 0) {
      if (list.scrollTop >= scrollPosition) {
        list.scrollTop = scrollPosition + 150;
      }
    }
  }, [datasets, scrollPosition]);

  return (
    <>
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        {t('datasetHistory')}
      </Typography>
      <Typography sx={{ mb: 2 }}>{t('datasetHistoryDescription')}</Typography>
      <ContentBox
        width={{ xs: '100%' }}
        title={''}
        outlineColor={theme.palette.primary.dark}
        padding={{ xs: 0 }}
      >
        <Box
          sx={{
            height: '100%',
            maxHeight: 'min(600px, 60vh)',
            overflowY: 'auto',
            pb: '5px', // for the bottomRef trigger spacing
          }}
          ref={listRef}
        >
          <TableContainer>
            <Table>
              <TableBody sx={{ width: '100%' }}>
                {datasets?.map((dataset, index) => (
                  <TableRow data-testid='dataset-item' key={dataset.id}>
                    {dataset.downloaded_at != null && (
                      <TableCell>
                        <Typography variant='body1'>
                          {index === 0 && <b>Latest: </b>}
                          {new Date(dataset.downloaded_at).toDateString()}
                        </Typography>
                      </TableCell>
                    )}
                    <TableCell>
                      {dataset?.service_date_range_start != undefined &&
                        dataset?.service_date_range_end != undefined && (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                            }}
                          >
                            <Tooltip
                              title={t(
                                'datasetHistoryTooltip.serviceDateRange',
                              )}
                              placement='top'
                            >
                              <DateRangeIcon></DateRangeIcon>
                            </Tooltip>

                            {formatServiceDateRange(
                              dataset?.service_date_range_start,
                              dataset?.service_date_range_end,
                              dataset.agency_timezone,
                            )}
                          </Box>
                        )}
                    </TableCell>
                    <TableCell sx={{ textAlign: { xs: 'left', xl: 'center' } }}>
                      {dataset.validation_report == null && (
                        <Typography sx={{ ml: '4px' }}>
                          {t('validationReportNotAvailable')}
                        </Typography>
                      )}
                      {dataset.validation_report != null && (
                        <>
                          <Chip
                            component='a'
                            clickable
                            href={`${dataset?.validation_report?.url_html}`}
                            target='_blank'
                            rel='noreferrer nofollow'
                            sx={{ m: '4px' }}
                            icon={
                              dataset?.validation_report?.unique_error_count !=
                                undefined &&
                              dataset?.validation_report?.unique_error_count >
                                0 ? (
                                <ReportOutlined />
                              ) : (
                                <CheckCircle />
                              )
                            }
                            label={
                              dataset?.validation_report?.unique_error_count !=
                                undefined &&
                              dataset?.validation_report?.unique_error_count > 0
                                ? `${dataset?.validation_report
                                    ?.unique_error_count} ${tCommon(
                                    'feedback.errors',
                                  )}`
                                : tCommon('feedback.noErrors')
                            }
                            color={
                              dataset?.validation_report?.unique_error_count !=
                                undefined &&
                              dataset?.validation_report?.unique_error_count > 0
                                ? 'error'
                                : 'success'
                            }
                            variant='outlined'
                          />
                          <Chip
                            sx={{ m: '4px' }}
                            component='a'
                            clickable
                            href={`${dataset?.validation_report?.url_html}`}
                            target='_blank'
                            rel='noreferrer nofollow'
                            icon={
                              dataset?.validation_report
                                ?.unique_warning_count != undefined &&
                              dataset?.validation_report?.unique_warning_count >
                                0 ? (
                                <ReportOutlined />
                              ) : (
                                <CheckCircle />
                              )
                            }
                            label={
                              dataset?.validation_report
                                ?.unique_warning_count != undefined &&
                              dataset?.validation_report?.unique_warning_count >
                                0
                                ? `${dataset?.validation_report
                                    ?.unique_warning_count} ${tCommon(
                                    'feedback.warnings',
                                  )}`
                                : tCommon('feedback.noWarnings')
                            }
                            color={
                              dataset?.validation_report
                                ?.unique_warning_count != undefined &&
                              dataset?.validation_report?.unique_warning_count >
                                0
                                ? 'warning'
                                : 'success'
                            }
                            variant='outlined'
                          />
                          <Chip
                            sx={{ m: '4px' }}
                            component='a'
                            clickable
                            href={`${dataset?.validation_report?.url_html}`}
                            target='_blank'
                            rel='noreferrer nofollow'
                            icon={<InfoOutlinedIcon />}
                            label={`${
                              dataset?.validation_report?.unique_info_count ??
                              '0'
                            } ${tCommon('feedback.infoNotices')}`}
                            color='primary'
                            variant='outlined'
                          />
                        </>
                      )}
                    </TableCell>
                    <TableCell>
                      <Box
                        sx={{
                          display: 'flex',
                          gap: 1,
                          justifyContent: 'center',
                          alignItems: 'center',
                        }}
                      >
                        {dataset.hosted_url != null && (
                          <Tooltip
                            title={t('datasetHistoryTooltip.downloadReport')}
                            placement='top'
                          >
                            <Button
                              variant='text'
                              aria-label={t(
                                'datasetHistoryTooltip.downloadReport',
                              )}
                              startIcon={<DownloadOutlined />}
                              size='medium'
                              href={dataset.hosted_url}
                              rel='noreferrer nofollow'
                            >
                              {tCommon('download')}
                            </Button>
                          </Tooltip>
                        )}
                        {dataset.validation_report == undefined && (
                          <Button
                            variant='contained'
                            sx={{ mx: 2 }}
                            disableElevation
                            endIcon={<LaunchOutlined />}
                            href={WEB_VALIDATOR_LINK}
                            target='_blank'
                            rel='noreferrer'
                          >
                            {t('runValidationReportYourself')}
                          </Button>
                        )}

                        {dataset.validation_report != null && (
                          <>
                            {dataset.hosted_url != null && <>|</>}
                            <Tooltip
                              title={t('datasetHistoryTooltip.viewReport')}
                              placement='top'
                            >
                              <IconButton
                                color='primary'
                                aria-label={t(
                                  'datasetHistoryTooltip.viewReport',
                                )}
                                size='medium'
                                href={`${dataset?.validation_report?.url_html}`}
                                target='_blank'
                                rel='noreferrer nofollow'
                                data-testid='validation-report-html'
                              >
                                <SummarizeIcon />
                              </IconButton>
                            </Tooltip>
                            |
                            <Tooltip
                              title={t('datasetHistoryTooltip.viewJsonReport')}
                              placement='top'
                            >
                              <IconButton
                                color='primary'
                                aria-label={t(
                                  'datasetHistoryTooltip.viewJsonReport',
                                )}
                                size='medium'
                                href={`${dataset?.validation_report?.url_json}`}
                                target='_blank'
                                rel='noreferrer nofollow'
                                data-testid='validation-report-json'
                              >
                                <CodeIcon />
                              </IconButton>
                            </Tooltip>
                          </>
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Box
            ref={bottomRef}
            style={{ height: '5px', background: 'transparent' }}
          />
        </Box>
      </ContentBox>
      {hasloadedAllDatasets && (
        <Typography
          variant='caption'
          component={Box}
          sx={{ width: '100%', textAlign: 'center', mt: 1 }}
        >
          {t('allDatasetsLoaded')}
        </Typography>
      )}

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          height: '48px',
          pt: 1,
        }}
      >
        {isLoadingDatasets && <CircularProgress />}
      </Box>
    </>
  );
}
