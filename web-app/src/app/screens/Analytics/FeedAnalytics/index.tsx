import React, { useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  MaterialReactTable,
  useMaterialReactTable,
} from 'material-react-table';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  type SelectChangeEvent,
  Typography,
} from '@mui/material';

import '../analytics.css';
import { useLocation } from 'react-router-dom';
import {
  fetchAvailableFilesStart,
  selectFile,
} from '../../../store/analytics-reducer';
import {
  selectFeedMetrics,
  selectAnalyticsStatus,
  selectAnalyticsError,
} from '../../../store/analytics-selector';
import { useTableColumns } from './FeedAnalyticsTable';
import DetailPanel from './DetailPanel';
import { type RootState } from '../../../store/store';

export default function FeedAnalytics(): React.ReactElement {
  const { search } = useLocation();
  const params = new URLSearchParams(search);

  const severity = params.get('severity');
  const noticeCode = params.get('noticeCode');
  const featureName = params.get('featureName');

  const dispatch = useDispatch();
  const data = useSelector(selectFeedMetrics);
  const status = useSelector(selectAnalyticsStatus);
  const error = useSelector(selectAnalyticsError);

  const availableFiles = useSelector(
    (state: RootState) => state.analytics.availableFiles,
  );
  const selectedFile = useSelector(
    (state: RootState) => state.analytics.selectedFile,
  );

  React.useEffect(() => {
    dispatch(fetchAvailableFilesStart());
  }, [dispatch]);

  const handleFileChange = (event: SelectChangeEvent<unknown>): void => {
    const fileName = event.target.value as string;
    dispatch(selectFile(fileName));
  };

  const uniqueErrors = useMemo(() => {
    const errors = data.flatMap((item) => item.notices?.errors);
    return Array.from(new Set(errors)).sort();
  }, [data]);

  const uniqueWarnings = useMemo(() => {
    const warnings = data.flatMap((item) => item.notices?.warnings);
    return Array.from(new Set(warnings)).sort();
  }, [data]);

  const uniqueInfos = useMemo(() => {
    const infos = data.flatMap((item) => item.notices?.infos);
    return Array.from(new Set(infos)).sort();
  }, [data]);

  const uniqueFeatures = useMemo(() => {
    const features = data.flatMap((item) => item?.features);
    return Array.from(new Set(features)).sort();
  }, [data]);

  const avgErrors = useMemo(() => {
    const totalErrors = data.reduce(
      (acc, item) => acc + item.notices?.errors.length,
      0,
    );
    return Math.round(totalErrors / data.length);
  }, [data]);

  const avgWarnings = useMemo(() => {
    const totalWarnings = data.reduce(
      (acc, item) => acc + item.notices?.warnings.length,
      0,
    );
    return Math.round(totalWarnings / data.length);
  }, [data]);

  const avgInfos = useMemo(() => {
    const totalInfos = data.reduce(
      (acc, item) => acc + item.notices?.infos.length,
      0,
    );
    return Math.round(totalInfos / data.length);
  }, [data]);

  const initialFilters = useMemo(() => {
    const filters = [];
    if (featureName != null) {
      filters.push({
        id: 'features',
        value: featureName,
      });
    }
    if (severity != null && noticeCode != null) {
      const id =
        severity === 'ERROR'
          ? 'notices.errors'
          : severity === 'WARNING'
            ? 'notices.warnings'
            : severity === 'INFO'
              ? 'notices.infos'
              : undefined;
      if (id != null) {
        filters.push({
          id,
          value: [noticeCode],
        });
      }
    }
    return filters;
  }, [severity, noticeCode, featureName]);

  const columns = useTableColumns(
    uniqueErrors,
    uniqueWarnings,
    uniqueInfos,
    uniqueFeatures,
    avgErrors,
    avgWarnings,
    avgInfos,
  );

  const table = useMaterialReactTable({
    columns,
    data,
    initialState: {
      showColumnFilters: initialFilters.length > 0,
      columnPinning: { left: ['mrt-row-expand', 'feed_id'] },
      density: 'compact',
      sorting: [{ id: 'feed_id', desc: false }],
      columnFilters: initialFilters,
      columnVisibility: {
        created_on: false,
        dataset_id: false,
        country_code: false,
        country: false,
        subdivision_name: false,
        municipality: false,
        provider: false,
      },
    },
    enableStickyHeader: true,
    enableStickyFooter: true,
    muiTableContainerProps: { sx: { maxHeight: '70vh' } },
    renderDetailPanel: ({ row }) => <DetailPanel row={row} />,
    renderTopToolbarCustomActions: ({ table }) => (
      <Box sx={{ minWidth: 200 }}>
        <FormControl fullWidth variant='outlined' sx={{ marginBottom: 2 }}>
          <InputLabel id='select-file-label'>Analytics Compute Date</InputLabel>
          <Select
            labelId='select-file-label'
            value={selectedFile ?? ''}
            onChange={(event) => {
              handleFileChange(event);
            }}
            label='Analytics Compute Date'
          >
            {availableFiles.map((file) => (
              <MenuItem key={file.file_name} value={file.file_name}>
                {new Date(file.created_on).toLocaleDateString('en-CA', {
                  year: 'numeric',
                  month: 'long',
                })}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
    ),
  });

  // TODO improve this code
  if (status === 'loading') {
    return <div>Loading...</div>;
  }

  // TODO improve this code
  if (status === 'failed') {
    return <div>Error: {error}</div>;
  }

  return (
    <Box sx={{ m: 10 }}>
      <Typography variant='h5' color='primary' sx={{ fontWeight: 700 }}>
        Feeds Analytics{' '}
      </Typography>

      <MaterialReactTable table={table} />
    </Box>
  );
}
