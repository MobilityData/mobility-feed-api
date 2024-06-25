import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Button,
  Chip,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Typography,
  colors,
} from '@mui/material';
import {
  DownloadOutlined,
  ErrorOutlineOutlined,
  ReportOutlined,
  LaunchOutlined,
  CheckCircle,
} from '@mui/icons-material';
import { type paths } from '../../services/feeds/types';

export interface PreviousDatasetsProps {
  datasets:
    | paths['/v1/gtfs_feeds/{id}/datasets']['get']['responses'][200]['content']['application/json']
    | undefined;
}

export default function PreviousDatasets({
  datasets,
}: PreviousDatasetsProps): React.ReactElement {
  return (
    <>
      <Typography sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold' }}>
        Dataset History
      </Typography>
      <Typography>
        The Mobility Database fetches and stores new datasets once a week, at
        11:59 EST on Sundays.{' '}
      </Typography>
      <Typography>
        {datasets !== undefined && datasets.length > 0 && (
          <div>
            1-{datasets.length < 10 ? datasets.length : 10} of {datasets.length}{' '}
            {'Datasets >'}
          </div>
        )}
      </Typography>
      <ContentBox
        width={{ xs: '100%' }}
        title={''}
        outlineColor={colors.indigo[500]}
      >
        <TableContainer>
          <TableBody sx={{ display: 'inline-table', width: '100%' }}>
            {datasets?.map((dataset, index) => (
              <TableRow key={dataset.id}>
                {dataset.downloaded_at != null && (
                  <TableCell>
                    {index === 0 && <b>Latest: </b>}
                    {new Date(dataset.downloaded_at).toDateString()}
                  </TableCell>
                )}
                <TableCell>
                  <span style={{ display: 'flex' }}>
                    <a href={dataset.hosted_url}>Download Dataset</a>
                    <DownloadOutlined />
                  </span>
                </TableCell>
                <TableCell>
                  {dataset.validation_report !== null &&
                    dataset.validation_report !== undefined && (
                      <>
                        <Chip
                          icon={
                            dataset?.validation_report?.total_error !==
                              undefined &&
                            dataset?.validation_report?.total_error > 0 ? (
                              <ReportOutlined />
                            ) : (
                              <CheckCircle />
                            )
                          }
                          label={
                            dataset?.validation_report?.total_error !==
                              undefined &&
                            dataset?.validation_report?.total_error > 0
                              ? `${dataset?.validation_report?.total_error} errors`
                              : `No errors`
                          }
                          color={
                            dataset?.validation_report?.total_error !==
                              undefined &&
                            dataset?.validation_report?.total_error > 0
                              ? 'error'
                              : 'success'
                          }
                          variant='outlined'
                        />
                        <Chip
                          icon={
                            dataset?.validation_report?.total_warning !==
                              undefined &&
                            dataset?.validation_report?.total_warning > 0 ? (
                              <ReportOutlined />
                            ) : (
                              <CheckCircle />
                            )
                          }
                          label={
                            dataset?.validation_report?.total_warning !==
                              undefined &&
                            dataset?.validation_report?.total_warning > 0
                              ? `${dataset?.validation_report?.total_warning} warnings`
                              : `No warnings`
                          }
                          color={
                            dataset?.validation_report?.total_warning !==
                              undefined &&
                            dataset?.validation_report?.total_warning > 0
                              ? 'warning'
                              : 'success'
                          }
                          variant='outlined'
                        />
                        <Chip
                          icon={<ErrorOutlineOutlined />}
                          label={`${
                            dataset?.validation_report?.total_info ?? '0'
                          } Info Notices`}
                          color='primary'
                          variant='outlined'
                        />
                      </>
                    )}
                </TableCell>
                <TableCell>
                  {dataset.validation_report != null &&
                    dataset.validation_report !== undefined && (
                      <Button
                        variant='contained'
                        sx={{ m: 2 }}
                        endIcon={<LaunchOutlined />}
                      >
                        <a
                          href={`${dataset?.validation_report?.url_html}`}
                          target='_blank'
                          className='btn-link'
                          rel='noreferrer'
                        >
                          View Report
                        </a>
                      </Button>
                    )}
                </TableCell>
                <TableCell>
                  {dataset.validation_report != null &&
                    dataset.validation_report !== undefined && (
                      <Button
                        variant='contained'
                        sx={{ m: 2 }}
                        endIcon={<LaunchOutlined />}
                      >
                        <a
                          href={`${dataset?.validation_report?.url_json}`}
                          target='_blank'
                          className='btn-link'
                          rel='noreferrer'
                        >
                          JSON Version
                        </a>
                      </Button>
                    )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </TableContainer>
      </ContentBox>
    </>
  );
}
