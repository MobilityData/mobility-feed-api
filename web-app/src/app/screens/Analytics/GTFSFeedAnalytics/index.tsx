import React, { useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  MaterialReactTable,
  type MRT_Row,
  useMaterialReactTable,
} from 'material-react-table';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
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
} from '../../../store/gtfs-analytics-reducer';
import {
  selectGTFSFeedMetrics,
  selectGTFSAnalyticsStatus,
  selectGTFSAnalyticsError,
} from '../../../store/gtfs-analytics-selector';
import { useTableColumns } from './GTFSFeedAnalyticsTable';
import DetailPanel from './DetailPanel';
import { type RootState } from '../../../store/store';
import { type AnalyticsFile, type GTFSFeedMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import DownloadIcon from '@mui/icons-material/Download';
import { download, generateCsv, mkConfig } from 'export-to-csv';

let globalAnalyticsBucketEndpoint: string | undefined;
export const getAnalyticsBucketEndpoint = (): string | undefined =>
  globalAnalyticsBucketEndpoint;

export default function GTFSFeedAnalytics(): React.ReactElement {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const { config } = useRemoteConfig();

  const severity = params.get('severity');
  const noticeCode = params.get('noticeCode');
  const featureName = params.get('featureName');

  const dispatch = useDispatch();
  const data = useSelector(selectGTFSFeedMetrics);
  const status = useSelector(selectGTFSAnalyticsStatus);
  const error = useSelector(selectGTFSAnalyticsError);

  const availableFiles = useSelector(
    (state: RootState) => state.gtfsAnalytics.availableFiles,
  );
  const selectedFile = useSelector(
    (state: RootState) => state.gtfsAnalytics.selectedFile,
  );

  const getFileDisplayKey = (file: AnalyticsFile): React.ReactElement => {
    const dateString = file.file_name.split('_')[1]; // Extracting the year and month
    const date = new Date(dateString.replace('.json', '')); // Creating a date object
    const formattedDate = date.toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      timeZone: 'UTC',
    });

    return (
      <MenuItem key={file.file_name} value={file.file_name}>
        {formattedDate}
      </MenuItem>
    );
  };

  React.useEffect(() => {
    globalAnalyticsBucketEndpoint = config.gtfsMetricsBucketEndpoint;
    dispatch(fetchAvailableFilesStart());
  }, [dispatch, config.gtfsMetricsBucketEndpoint]);

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

  const csvConfig = mkConfig({
    fieldSeparator: ',',
    decimalSeparator: '.',
    useKeysAsHeaders: true,
    filename: 'gtfs-feed-metrics',
  });
  const handleExportRows = (rows: Array<MRT_Row<GTFSFeedMetrics>>): void => {
    const rowData = rows.map((row) => row.original);
    const expandedTables = rowData.map((row) => {
      const filteredRow = {
        ...row,
        created_on: new Date(row.created_on).toISOString(),
        last_modified: new Date(row.last_modified).toISOString(),
        errors: row.notices.errors.reduce(
          (acc, error) => acc.concat(error, ' | '),
          '',
        ),
        warnings: row.notices.warnings.reduce(
          (acc, warning) => acc.concat(warning, ' | '),
          '',
        ),
        infos: row.notices.infos.reduce(
          (acc, info) => acc.concat(info, ' | '),
          '',
        ),
        features: row.features.reduce(
          (acc, feature) => acc.concat(feature, ' | '),
          '',
        ),
        notices: null,
        locations: row.locations_string,
        locations_string: null,
        metrics: null,
      };

      // Create a new object without null values
      const rowWithNoNulls = Object.fromEntries(
        Object.entries(filteredRow).filter(([_, value]) => value !== null),
      );

      return rowWithNoNulls as typeof filteredRow;
    });

    const csv = generateCsv(csvConfig)(expandedTables);
    download(csvConfig)(csv);
  };

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
        locations_string: false,
        provider: false,
      },
    },
    state: {
      isLoading: status === 'loading',
      showSkeletons: status === 'loading',
      showProgressBars: status === 'loading',
    },
    filterFns: {
      doesNotInclude: (row, id, filterValue) => {
        if (filterValue == null) {
          return true;
        }
        const cellValue = row.getValue(id);

        if (typeof cellValue === 'string' && typeof filterValue === 'string') {
          return !cellValue.toLowerCase().includes(filterValue.toLowerCase());
        }
        throw new Error('doesNotInclude filter only supports string values');
      },
    },
    enableColumnFilters: true,
    enableStickyHeader: true,
    enableDensityToggle: false,
    enableColumnFilterModes: true,
    maxLeafRowFilterDepth: 10,
    enableGrouping: true,
    enableRowVirtualization: true,
    enablePagination: false,
    enableStickyFooter: true,
    enableFacetedValues: true,
    enableColumnResizing: true,
    rowVirtualizerOptions: {
      overscan: 10,
    },
    layoutMode: 'grid',
    muiTableContainerProps: { sx: { maxHeight: '70vh' } },
    renderDetailPanel: ({ row }) => <DetailPanel row={row} />,
    renderTopToolbarCustomActions: ({ table }) => (
      <Box sx={{ minWidth: 200, display: 'flex', alignItems: 'flex-start' }}>
        <FormControl variant='outlined' sx={{ marginBottom: 2 }}>
          <InputLabel id='select-file-label'>Analytics Compute Date</InputLabel>
          <Select
            variant='outlined'
            labelId='select-file-label'
            value={selectedFile ?? ''}
            onChange={(event) => {
              handleFileChange(event);
            }}
            label='Analytics Compute Date'
          >
            {availableFiles.map((file) => (
              <MenuItem key={file.file_name} value={file.file_name}>
                {getFileDisplayKey(file)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant='contained'
          disabled={table.getPrePaginationRowModel().rows.length === 0}
          // export all rows, including from the next page, (still respects filtering and sorting)
          onClick={() => {
            handleExportRows(table.getPrePaginationRowModel().rows);
          }}
          endIcon={<DownloadIcon />}
          sx={{ ml: 2, mt: 1 }}
        >
          Download as CSV
        </Button>
      </Box>
    ),
  });

  return (
    <Box sx={{ mx: 6 }}>
      <Typography
        component='h1'
        variant='h4'
        color='primary'
        sx={{ fontWeight: 700, mb: 2 }}
      >
        GTFS Feeds Metrics{' '}
      </Typography>
      {error != null && (
        <Alert severity='error'>
          <AlertTitle>Error</AlertTitle>
          There was an error fetching the data: {error}. Please try again later.
        </Alert>
      )}
      <MaterialReactTable table={table} />
    </Box>
  );
}
