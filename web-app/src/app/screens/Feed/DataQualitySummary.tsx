import * as React from 'react';
import { Button, Chip, Grid, Typography } from '@mui/material';

import { CheckCircle, ReportOutlined } from '@mui/icons-material';
import { type components } from '../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export interface DataQualitySummaryProps {
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default function DataQualitySummary({
  latestDataset,
}: DataQualitySummaryProps): React.ReactElement {
  if (
    latestDataset?.validation_report === undefined ||
    latestDataset.validation_report === null
  )
    return <></>;
  return (
    <>
      <Typography variant='h6' gutterBottom>
        Data Quality Summary
      </Typography>
      <Grid container direction={'column'} spacing={2}>
        <Grid item container direction={'row'} spacing={2}>
          <Grid
            item
            sx={{
              alignContent: 'center',
            }}
          >
            <Chip
              icon={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0 ? (
                  <ReportOutlined />
                ) : (
                  <CheckCircle />
                )
              }
              label={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0
                  ? `${latestDataset?.validation_report?.unique_error_count} errors`
                  : `No errors`
              }
              color={
                latestDataset?.validation_report?.unique_error_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_error_count > 0
                  ? 'error'
                  : 'success'
              }
              variant='outlined'
            />
          </Grid>
          <Grid
            item
            sx={{
              alignContent: 'center',
            }}
          >
            <Chip
              icon={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0 ? (
                  <ReportOutlined />
                ) : (
                  <CheckCircle />
                )
              }
              label={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0
                  ? `${latestDataset?.validation_report?.unique_warning_count} warnings`
                  : `No warnings`
              }
              color={
                latestDataset?.validation_report?.unique_warning_count !==
                  undefined &&
                latestDataset?.validation_report?.unique_warning_count > 0
                  ? 'warning'
                  : 'success'
              }
              variant='outlined'
            />
          </Grid>
          <Grid
            item
            sx={{
              alignContent: 'center',
            }}
          >
            <Chip
              icon={<InfoOutlinedIcon />}
              label={`${
                latestDataset?.validation_report?.unique_info_count ?? '0'
              } info notices`}
              color='primary'
              variant='outlined'
            />
          </Grid>
        </Grid>
        <Grid item container direction={'row'} spacing={2}>
          <Grid item>
            {latestDataset?.validation_report?.url_html !== undefined && (
              <Button variant='contained' disableElevation>
                <a
                  href={`${latestDataset?.validation_report?.url_html}`}
                  target='_blank'
                  className='btn-link'
                  rel='noreferrer'
                >
                  Open Full Report
                </a>
              </Button>
            )}
          </Grid>
        </Grid>
      </Grid>
    </>
  );
}
