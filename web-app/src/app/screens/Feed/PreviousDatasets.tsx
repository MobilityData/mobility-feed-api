import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Chip,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import {
  DownloadOutlined,
  ErrorOutlineOutlined,
  OpenInNewOutlined,
  ReportOutlined,
  ReportProblemOutlined,
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
    <ContentBox
      width={{ xs: '100%' }}
      title={'Previous Datasets'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableBody>
          {datasets?.map((dataset) => (
            <TableRow key={dataset.id}>
              {dataset.downloaded_at != null && (
                <TableCell>
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
                <div>
                  <Chip
                    icon={<ReportOutlined />}
                    label={`${
                      dataset?.validation_report?.total_error ?? '0'
                    } Error`}
                    color='error'
                    variant='outlined'
                  />
                  <Chip
                    icon={<ReportProblemOutlined />}
                    label={`${
                      dataset?.validation_report?.total_warning ?? '0'
                    } Warning`}
                    color='warning'
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
                </div>
              </TableCell>
              {dataset.validation_report != null &&
                dataset.validation_report !== undefined && (
                  <TableCell>
                    <span style={{ display: 'flex' }}>
                      <a
                        href={`${dataset?.validation_report?.url_html}`}
                        target='_blank'
                        rel='noreferrer'
                      >
                        Open Full Report
                      </a>
                      <OpenInNewOutlined />
                    </span>
                  </TableCell>
                )}
              {dataset.validation_report != null &&
                dataset.validation_report !== undefined && (
                  <TableCell>
                    <a
                      href={`${dataset?.validation_report?.url_json}`}
                      target='_blank'
                      rel='noreferrer'
                    >
                      Open JSON Report <OpenInNewOutlined />
                    </a>
                  </TableCell>
                )}
            </TableRow>
          ))}
        </TableBody>
      </TableContainer>
    </ContentBox>
  );
}
