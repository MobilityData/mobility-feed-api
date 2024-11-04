import { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
} from 'material-react-table';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Brush,
  Line,
  LineChart,
  Tooltip,
} from 'recharts';
import Box from '@mui/material/Box';

import { Typography, Button, Alert, AlertTitle } from '@mui/material';
import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import { InfoOutlined, ListAltOutlined } from '@mui/icons-material';
import { type GBFSNoticeMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';

export default function GBFSNoticeAnalytics(): React.ReactElement {
  const navigateTo = useNavigate();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const noticeCode = params.get('noticeCode');
  const [data, setData] = useState<GBFSNoticeMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { config } = useRemoteConfig();

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(
          `${config.gbfsMetricsBucketEndpoint}/notices_metrics.json`,
        );
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedData = await response.json();
        const dataWLatestCount = fetchedData.map(
          (notice: GBFSNoticeMetrics) => ({
            ...notice,
            latest_feed_count: notice.feeds_count.slice(-1)[0],
          }),
        );
        setData(dataWLatestCount);
      } catch (error) {
        if (error instanceof Error) {
          setError(error.message);
        } else {
          setError('An unknown error occurred');
        }
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, []);

  const columns = useMemo<Array<MRT_ColumnDef<GBFSNoticeMetrics>>>(
    () => [
      {
        accessorKey: 'keyword',
        header: 'Keyword',
        size: 300,
      },
      {
        accessorKey: 'gbfs_file',
        header: 'GBFS File',
        size: 150,
      },
      {
        accessorKey: 'schema_path',
        header: 'Schema Path',
      },
      {
        accessorKey: 'latest_feed_count',
        header: 'Number of Feeds',
        size: 150,
        filterVariant: 'range-slider',
        muiFilterSliderProps: {
          marks: true,
          max: data.reduce(
            (max, notice) => Math.max(max, notice.feeds_count.slice(-1)[0]),
            0,
          ),
          min: 0,
          step: 5,
        },
      },
    ],
    [data],
  );

  const initialFilters =
    noticeCode != null
      ? [
          {
            id: 'keyword',
            value: noticeCode,
          },
        ]
      : [];

  const table = useMaterialReactTable({
    columns,
    data,
    initialState: {
      showColumnFilters: true,
      columnPinning: { left: ['mrt-row-expand', 'keyword'] },
      density: 'compact',
      sorting: [{ id: 'keyword', desc: false }],
      columnFilters: initialFilters,
      expanded: initialFilters.length > 0 ? true : {},
    },
    state: {
      isLoading: loading,
      showSkeletons: loading,
      showProgressBars: loading,
    },
    enableDensityToggle: false,
    enableStickyHeader: true,
    enableStickyFooter: true,
    muiTableContainerProps: { sx: { maxHeight: '70vh' } },
    renderDetailPanel: ({ row }) => {
      const theme = useTheme();
      const metrics = row.original;

      const chartData = metrics.computed_on.map((date, index) => ({
        date: new Date(date).toLocaleDateString('en-CA', { timeZone: 'UTC' }),
        feeds: metrics.feeds_count[index],
      }));
      const domain = [
        new Date(metrics.computed_on[0]).getTime(),
        new Date().getTime(),
      ];

      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'row',
            margin: 'auto',
          }}
        >
          <Box sx={{ flex: 1, paddingRight: 2 }}>
            <Typography gutterBottom>Monthly Notice Metrics</Typography>
            <ResponsiveContainer width='100%' height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray='3 3' />
                <XAxis dataKey='date' tick={false} domain={domain} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Brush
                  dataKey='date'
                  height={30}
                  stroke={theme.palette.primary.main}
                />
                <Line
                  type='monotone'
                  dataKey='feeds'
                  stroke={theme.palette.primary.main}
                />
              </LineChart>
            </ResponsiveContainer>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Box sx={{ maxWidth: '500px' }}>
              <Typography variant='body1' sx={{ mb: 2 }}>
                <InfoOutlined
                  sx={{
                    verticalAlign: 'middle',
                  }}
                />
                This graph shows the monthly feed validation metrics, including
                the count of feeds associated with each notice over time.
              </Typography>
              <Button
                variant='contained'
                color='primary'
                sx={{ mb: 2 }}
                startIcon={<ListAltOutlined />}
                onClick={() => {
                  navigateTo(
                    `/metrics/gbfs/feeds?schemaPath=${encodeURIComponent(
                      metrics.schema_path,
                    )}`,
                  );
                }}
              >
                Show Feeds
              </Button>
            </Box>
          </Box>
        </Box>
      );
    },
  });

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Box sx={{ mx: 6 }}>
      <Typography variant='h4' color='primary' sx={{ fontWeight: 700, mb: 2 }}>
        GBFS Notices Metrics
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
