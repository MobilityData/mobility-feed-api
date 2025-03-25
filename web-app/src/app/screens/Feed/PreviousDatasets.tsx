import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
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
import { type paths } from '../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SummarizeIcon from '@mui/icons-material/Summarize';
import CodeIcon from '@mui/icons-material/Code';
import DateRangeIcon from '@mui/icons-material/DateRange';
import { WEB_VALIDATOR_LINK } from '../../constants/Navigation';
import { formatServiceDateRange } from './Feed.functions';
import { useTranslation } from 'react-i18next';

export interface PreviousDatasetsProps {
  datasets:
    | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
    | undefined;
}

export default function PreviousDatasets({
  datasets,
}: PreviousDatasetsProps): React.ReactElement {
  const theme = useTheme();
  const { t } = useTranslation('feeds');
  return (
    <>
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        {t('datasetHistory')}
      </Typography>
      <Typography>{t('datasetHistoryDescription')}</Typography>

      {datasets !== undefined && datasets.length > 0 && (
        <Box sx={{ mt: 2, mb: 2, display: 'flex' }}>
          <Typography sx={{ fontWeight: 'bold' }}>
            {datasets.length} {t('datasets')}
          </Typography>
        </Box>
      )}

      <ContentBox
        width={{ xs: '100%' }}
        title={''}
        outlineColor={theme.palette.primary.dark}
        padding={{ xs: 0, sm: 1 }}
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
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          <Tooltip
                            title={t('datasetHistoryTooltip.serviceDateRange')}
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
                    {(dataset.validation_report === null ||
                      dataset.validation_report === undefined) && (
                      <Typography sx={{ ml: '4px' }}>
                        {t('validationReportNotAvailable')}
                      </Typography>
                    )}
                    {dataset.validation_report !== null &&
                      dataset.validation_report !== undefined && (
                        <>
                          <Chip
                            component='a'
                            clickable
                            href={`${dataset?.validation_report?.url_html}`}
                            target='_blank'
                            rel='noreferrer nofollow'
                            sx={{ m: '4px' }}
                            icon={
                              dataset?.validation_report?.unique_error_count !==
                                undefined &&
                              dataset?.validation_report?.unique_error_count >
                                0 ? (
                                <ReportOutlined />
                              ) : (
                                <CheckCircle />
                              )
                            }
                            label={
                              dataset?.validation_report?.unique_error_count !==
                                undefined &&
                              dataset?.validation_report?.unique_error_count > 0
                                ? `${dataset?.validation_report
                                    ?.unique_error_count} ${t(
                                    'common:feedback.errors',
                                  )}`
                                : t('common:feedback.noErrors')
                            }
                            color={
                              dataset?.validation_report?.unique_error_count !==
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
                                ?.unique_warning_count !== undefined &&
                              dataset?.validation_report?.unique_warning_count >
                                0 ? (
                                <ReportOutlined />
                              ) : (
                                <CheckCircle />
                              )
                            }
                            label={
                              dataset?.validation_report
                                ?.unique_warning_count !== undefined &&
                              dataset?.validation_report?.unique_warning_count >
                                0
                                ? `${dataset?.validation_report
                                    ?.unique_warning_count} ${t(
                                    'common:feedback.warnings',
                                  )}`
                                : t('common:feedback.noWarnings')
                            }
                            color={
                              dataset?.validation_report
                                ?.unique_warning_count !== undefined &&
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
                            } ${t('common:feedback.infoNotices')}`}
                            color='primary'
                            variant='outlined'
                          />
                        </>
                      )}
                  </TableCell>
                  <TableCell sx={{ textAlign: 'center' }}>
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
                            {t('common:download')}
                          </Button>
                        </Tooltip>
                        |
                        <Tooltip
                          title={t('datasetHistoryTooltip.viewReport')}
                          placement='top'
                        >
                          <IconButton
                            color='primary'
                            aria-label={t('datasetHistoryTooltip.viewReport')}
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
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </ContentBox>
    </>
  );
}
