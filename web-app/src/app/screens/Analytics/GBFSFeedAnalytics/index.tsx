import React, { useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import FormHelperText from '@mui/material/FormHelperText';
import { mkConfig, generateCsv, download } from 'export-to-csv';
import DownloadIcon from '@mui/icons-material/Download';

import {
  MaterialReactTable,
  type MRT_Row,
  useMaterialReactTable,
} from 'material-react-table';
import {
  Alert,
  AlertTitle,
  Autocomplete,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  type SelectChangeEvent,
  TextField,
  Typography,
} from '@mui/material';

import '../analytics.css';
import { useLocation } from 'react-router-dom';
import {
  fetchAvailableFilesStart,
  selectFile,
} from '../../../store/gbfs-analytics-reducer';
import {
  selectGBFSFeedMetrics,
  selectGBFSAnalyticsStatus,
  selectGBFSAnalyticsError,
} from '../../../store/gbfs-analytics-selector';
import { useTableColumns } from './GBFSFeedAnalyticsTable';
import { type RootState } from '../../../store/store';
import { type AnalyticsFile, type GBFSFeedMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import DetailPanel from './DetailPanel';

let globalAnalyticsBucketEndpoint: string | undefined;
export const getAnalyticsBucketEndpoint = (): string | undefined =>
  globalAnalyticsBucketEndpoint;

export default function GBFSFeedAnalytics(): React.ReactElement {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const { config } = useRemoteConfig();
  const [schemaPathFilters, setSchemaPathFilters] = React.useState<string[]>(
    [],
  );

  const versionFilter = params.get('version');
  const schemaPathInitFilter = decodeURIComponent(
    params.get('schemaPath') ?? '',
  );

  const dispatch = useDispatch();
  const rawData = useSelector(selectGBFSFeedMetrics);
  const status = useSelector(selectGBFSAnalyticsStatus);
  const error = useSelector(selectGBFSAnalyticsError);

  const availableFiles = useSelector(
    (state: RootState) => state.gbfsAnalytics.availableFiles,
  );
  const selectedFile = useSelector(
    (state: RootState) => state.gbfsAnalytics.selectedFile,
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
    globalAnalyticsBucketEndpoint = config.gbfsMetricsBucketEndpoint;
    dispatch(fetchAvailableFilesStart());
  }, [dispatch, config.gbfsMetricsBucketEndpoint]);

  const data = useMemo(() => {
    // Keep only the feeds that have errors matching the selected schema path
    // filters
    const filteredData = rawData.filter((item) => {
      return schemaPathFilters.every((filter) =>
        item.notices.some((notice) => notice.schema_path === filter),
      );
    });
    return filteredData.map((item) => ({
      ...item,
      error_count: item.notices.length,
    }));
  }, [rawData, schemaPathFilters]);

  const schemaPathFilterOptions = useMemo(() => {
    return Array.from(
      new Set(
        rawData.flatMap((item) =>
          item.notices.map((notice) => notice.schema_path),
        ),
      ),
    );
  }, [rawData]);

  const handleFileChange = (event: SelectChangeEvent<string>): void => {
    const fileName = event.target.value;
    dispatch(selectFile(fileName));
  };

  const initialFilters = useMemo(() => {
    const filters = [];
    if (versionFilter != null) {
      filters.push({ id: 'versions', value: versionFilter });
    }
    return filters;
  }, [versionFilter]);

  useMemo(() => {
    if (
      schemaPathInitFilter != null &&
      schemaPathFilterOptions.includes(schemaPathInitFilter)
    ) {
      setSchemaPathFilters([schemaPathInitFilter]);
    }
  }, [schemaPathInitFilter, schemaPathFilterOptions]);

  const columns = useTableColumns();
  const csvConfig = mkConfig({
    fieldSeparator: ',',
    decimalSeparator: '.',
    useKeysAsHeaders: true,
    filename: 'gbfs-feed-metrics',
  });
  const handleExportRows = (
    rows: Array<MRT_Row<GBFSFeedMetrics & { error_count: number }>>,
  ): void => {
    const rowData = rows.map((row) => row.original);
    const expandedTables = rowData.map((row) => {
      const filteredRow = {
        ...row,
        notices: row.notices.reduce(
          (acc, notice) => acc.concat(notice.schema_path, ' | '),
          '',
        ),
        versions: row.versions.reduce(
          (acc, version) => acc.concat(version, ' | '),
          '',
        ),
        locations: row.locations_string,
        locations_string: null,
        metrics: null,
        errors_count: null,
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
        snapshot_id: false,
        locations_string: false,
        auto_discovery_url: false,
        snapshot_hosted_url: false,
      },
    },
    state: {
      isLoading: status === 'loading',
      showSkeletons: status === 'loading',
      showProgressBars: status === 'loading',
    },
    enableStickyHeader: true,
    enableRowVirtualization: true,
    enablePagination: false,
    enableGrouping: true,
    enableFacetedValues: true,
    enableStickyFooter: true,
    muiTableContainerProps: { sx: { maxHeight: '70vh' } },
    renderDetailPanel: ({ row }) => <DetailPanel row={row} />,
    renderTopToolbarCustomActions: ({ table }) => (
      <Box sx={{ minWidth: 800, display: 'flex', alignItems: 'flex-start' }}>
        <FormControl
          fullWidth
          variant='outlined'
          sx={{ marginRight: 2, maxWidth: 200 }}
        >
          <InputLabel id='select-file-label'>Metrics Compute Date</InputLabel>
          <Select
            variant='outlined'
            labelId='select-file-label'
            value={selectedFile ?? ''}
            onChange={(event) => {
              handleFileChange(event);
            }}
            label='Metrics Compute Date'
          >
            {availableFiles.map((file) => (
              <MenuItem key={file.file_name} value={file.file_name}>
                {getFileDisplayKey(file)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl variant='outlined'>
          <Autocomplete
            multiple
            limitTags={1}
            id='multiple-limit-tags'
            options={schemaPathFilterOptions}
            value={schemaPathFilters}
            onChange={(_, newValue: string[] | null) => {
              if (newValue == null) {
                setSchemaPathFilters([]);
              } else {
                setSchemaPathFilters(newValue);
              }
            }}
            renderInput={(params) => (
              <TextField
                {...params}
                label='Schema Path Error Filter'
                placeholder='Error Filters'
              />
            )}
          />
          <FormHelperText>
            Filter feeds by the <b>Schema Path</b> values of errors. Selecting
            multiple values will apply an AND condition.
          </FormHelperText>
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
        GBFS Feeds Metrics
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
