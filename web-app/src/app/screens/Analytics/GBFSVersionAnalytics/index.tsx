import { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
  type MRT_Cell,
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

import { Typography, Button, IconButton } from '@mui/material';
import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import { InfoOutlined, ListAltOutlined } from '@mui/icons-material';
import { type GBFSVersionMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import MUITooltip from '@mui/material/Tooltip';
import { GBFS_LINK } from '../../../constants/Navigation';

export default function GBFSVersionAnalytics(): React.ReactElement {
  const navigateTo = useNavigate();
  const [data, setData] = useState<GBFSVersionMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const { config } = useRemoteConfig();
  const params = new URLSearchParams(useLocation().search);
  const versionFilter = params.get('version');
  const initialFilter = useMemo(() => {
    if (versionFilter != null) {
      return [{ id: 'version', value: versionFilter }];
    }
    return [];
  }, [versionFilter]);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(
          `${config.gbfsMetricsBucketEndpoint}/versions_metrics.json`,
        );
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedData = await response.json();
        const dataWLatestCount = fetchedData.map(
          (version: GBFSVersionMetrics) => ({
            ...version,
            latest_feed_count: version.feeds_count.slice(-1)[0],
          }),
        );
        setData(dataWLatestCount);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, []);

  const columns = useMemo<Array<MRT_ColumnDef<GBFSVersionMetrics>>>(
    () => [
      {
        accessorKey: 'version',
        header: 'Version',
        size: 150,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<GBFSVersionMetrics>;
          renderedCellValue: React.ReactNode;
        }) => {
          return (
            <div>
              {renderedCellValue}
              <MUITooltip
                title={`View version v${cell.getValue<string>()} definition`}
                arrow
              >
                <IconButton
                  onClick={() => {
                    window.open(
                      `${GBFS_LINK}/blob/v${cell.getValue<string>()}/gbfs.md`,
                      '_blank',
                    );
                  }}
                >
                  <InfoOutlined />
                </IconButton>
              </MUITooltip>
            </div>
          );
        },
      },
      {
        accessorKey: 'latest_feed_count',
        header: 'Number of Feeds',
        size: 150,
        filterVariant: 'range-slider',
        muiFilterSliderProps: {
          marks: true,
          max: data.reduce(
            (max, version) => Math.max(max, version.feeds_count.slice(-1)[0]),
            0,
          ),
          min: 0,
          step: 5,
        },
      },
    ],
    [data, navigateTo],
  );

  const table = useMaterialReactTable({
    columns,
    data,
    initialState: {
      showColumnFilters: true,
      columnPinning: { left: ['mrt-row-expand', 'version'] },
      density: 'compact',
      sorting: [{ id: 'version', desc: false }],
      columnFilters: initialFilter,
      expanded: initialFilter.length > 0 ? true : {},
    },
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
            <Typography gutterBottom>Monthly Version Metrics</Typography>
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
                the count of feeds associated with each GBFS version over time.
              </Typography>
              <Button
                variant='contained'
                color='primary'
                sx={{ mb: 2 }}
                startIcon={<ListAltOutlined />}
                onClick={() => {
                  navigateTo(`/metrics/gbfs/feeds?version=${metrics.version}`);
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
    <Box sx={{ m: 10 }}>
      <Typography variant='h5' color='primary' sx={{ fontWeight: 700 }}>
        GBFS Versions Metrics{' '}
      </Typography>
      <MaterialReactTable table={table} />
    </Box>
  );
}
