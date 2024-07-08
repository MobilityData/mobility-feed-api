import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
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
  ReportOutlined,
  LaunchOutlined,
  CheckCircle,
} from '@mui/icons-material';
import { type paths } from '../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

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
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        Dataset History
      </Typography>
      <Typography>
        The Mobility Database fetches and stores new datasets twice a week, on
        Mondays and Thursdays at midnight EST.{' '}
      </Typography>

      {datasets !== undefined && datasets.length > 0 && (
        <Typography sx={{ fontWeight: 'bold' }}>
          <Box sx={{ mt: 2, mb: 2, display: 'flex' }}>
            1-{datasets.length < 10 ? datasets.length : 10} of {datasets.length}{' '}
            Datasets
          </Box>
        </Typography>
      )}

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
                    <Typography variant='body1'>
                      {index === 0 && <b>Latest: </b>}
                      {new Date(dataset.downloaded_at).toDateString()}
                    </Typography>
                  </TableCell>
                )}
                <TableCell>
                  <Button
                    variant='text'
                    disableElevation
                    endIcon={<DownloadOutlined />}
                    href={dataset.hosted_url}
                  >
                    Download
                  </Button>
                </TableCell>
                <TableCell sx={{ textAlign: { xs: 'left', xl: 'center' } }}>
                  {dataset.validation_report !== null &&
                    dataset.validation_report !== undefined && (
                      <>
                        <Chip
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
                              ? `${dataset?.validation_report?.unique_error_count} errors`
                              : `No errors`
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
                          icon={
                            dataset?.validation_report?.unique_warning_count !==
                              undefined &&
                            dataset?.validation_report?.unique_warning_count >
                              0 ? (
                              <ReportOutlined />
                            ) : (
                              <CheckCircle />
                            )
                          }
                          label={
                            dataset?.validation_report?.unique_warning_count !==
                              undefined &&
                            dataset?.validation_report?.unique_warning_count > 0
                              ? `${dataset?.validation_report?.unique_warning_count} warnings`
                              : `No warnings`
                          }
                          color={
                            dataset?.validation_report?.unique_warning_count !==
                              undefined &&
                            dataset?.validation_report?.unique_warning_count > 0
                              ? 'warning'
                              : 'success'
                          }
                          variant='outlined'
                        />
                        <Chip
                          sx={{ m: '4px' }}
                          icon={<InfoOutlinedIcon />}
                          label={`${
                            dataset?.validation_report?.unique_info_count ?? '0'
                          } info notices`}
                          color='primary'
                          variant='outlined'
                        />
                      </>
                    )}
                </TableCell>
                <TableCell sx={{ textAlign: 'center' }}>
                  {dataset.validation_report != null &&
                    dataset.validation_report !== undefined && (
                      <Button
                        variant='contained'
                        sx={{ mx: 2 }}
                        disableElevation
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
                  {dataset.validation_report != null &&
                    dataset.validation_report !== undefined && (
                      <Button
                        variant='contained'
                        sx={{ mx: 2, my: { xs: 1, xl: 0 } }}
                        endIcon={<LaunchOutlined />}
                        disableElevation
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
