import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Chip,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';

import {
  ErrorOutlineOutlined,
  OpenInNewOutlined,
  ReportOutlined,
  ReportProblemOutlined,
} from '@mui/icons-material';
import { type components } from '../../services/feeds/types';

export interface DataQualitySummaryProps {
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default function DataQualitySummary({
  latestDataset,
}: DataQualitySummaryProps): React.ReactElement {
  return (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Data Quality Summary'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableRow>
          <TableCell>
            <Chip
              icon={<ReportOutlined />}
              label={`${
                latestDataset?.validation_report?.total_error ?? '0'
              } Error`}
              color='error'
              variant='outlined'
            />
            <Chip
              icon={<ReportProblemOutlined />}
              label={`${
                latestDataset?.validation_report?.total_warning ?? '0'
              } Warning`}
              color='warning'
              variant='outlined'
            />
            <Chip
              icon={<ErrorOutlineOutlined />}
              label={`${
                latestDataset?.validation_report?.total_info ?? '0'
              } Info Notices`}
              color='primary'
              variant='outlined'
            />
          </TableCell>
        </TableRow>
        <TableRow>
          {latestDataset?.validation_report?.url_html !== undefined && (
            <TableCell>
              <span style={{ display: 'flex' }}>
                <a
                  href={`${latestDataset?.validation_report?.url_html}`}
                  target='_blank'
                  rel='noreferrer'
                >
                  Open Full Report
                </a>
                <OpenInNewOutlined />
              </span>
            </TableCell>
          )}
          {latestDataset?.validation_report?.url_json !== undefined && (
            <TableCell>
              <span style={{ display: 'flex' }}>
                <a
                  href={`${latestDataset?.validation_report?.url_json}`}
                  target='_blank'
                  rel='noreferrer'
                >
                  Open JSON Report
                </a>
                <OpenInNewOutlined />
              </span>
            </TableCell>
          )}
        </TableRow>
      </TableContainer>
    </ContentBox>
  );
}
