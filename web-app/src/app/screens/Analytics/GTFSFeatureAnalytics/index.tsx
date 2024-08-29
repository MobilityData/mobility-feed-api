import { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  MaterialReactTable,
  type MRT_ColumnDef,
  type MRT_Cell,
  useMaterialReactTable,
} from 'material-react-table';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
  Line,
  LineChart,
} from 'recharts';
import Box from '@mui/material/Box';
import { Typography, Button } from '@mui/material';
import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import { InfoOutlined, ListAltOutlined } from '@mui/icons-material';
import { featureGroups, getGroupColor } from '../../../utils/analytics';
import { type FeatureMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';

export default function GTFSFeatureAnalytics(): React.ReactElement {
  const navigateTo = useNavigate();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const featureName = params.get('featureName');
  const [data, setData] = useState<FeatureMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const { config } = useRemoteConfig();

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(
          `${config.gtfsMetricsBucketEndpoint}/features_metrics.json`,
        );
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedData = await response.json();
        const dataWithGroups = fetchedData.map((feature: FeatureMetrics) => ({
          ...feature,
          latest_feed_count: feature.feeds_count.slice(-1)[0],
          feature_group: Object.keys(featureGroups).find((group) =>
            featureGroups[group].includes(feature.feature),
          ),
        }));
        setData(dataWithGroups);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, []);

  const columns = useMemo<Array<MRT_ColumnDef<FeatureMetrics>>>(
    () => [
      {
        accessorKey: 'feature',
        header: 'Feature Name',
        size: 300,
        enableClickToCopy: true,
      },
      {
        accessorKey: 'feature_group',
        header: 'Feature Group',
        size: 200,
        filterVariant: 'multi-select',
        filterSelectOptions: Object.keys(featureGroups),
        Cell: ({ cell }: { cell: MRT_Cell<FeatureMetrics> }) => {
          const group = cell.getValue<string>();
          return group == null ? null : (
            <span
              style={{
                backgroundColor: getGroupColor(group),
                borderRadius: '5px',
                padding: '2px 8px',
              }}
            >
              {group}
            </span>
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
            (max, feature) => Math.max(max, feature.latest_feed_count),
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
    featureName != null
      ? [
          {
            id: 'feature',
            value: featureName,
          },
        ]
      : [];

  const table = useMaterialReactTable({
    columns,
    data,
    initialState: {
      showColumnFilters: true,
      columnPinning: { left: ['mrt-row-expand', 'feature'] },
      density: 'compact',
      sorting: [{ id: 'feature', desc: false }],
      columnFilters: initialFilters,
      expanded: initialFilters.length > 0 ? true : {},
    },
    enableStickyHeader: true,
    enableStickyFooter: true,
    muiTableContainerProps: { sx: { maxHeight: '70vh' } },
    renderDetailPanel: ({ row }) => {
      const theme = useTheme();
      const metrics = row.original;

      const chartData = metrics.computed_on.map((date, index) => ({
        date: new Date(date).toLocaleDateString('en-CA', {
          timeZone: 'UTC',
        }),
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
            <Typography gutterBottom>Monthly Feature Metrics</Typography>
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
                This graph shows the monthly feed metrics, including the count
                of feeds associated with each feature over time.
              </Typography>
              <Button
                variant='contained'
                color='primary'
                sx={{ mb: 2 }}
                startIcon={<ListAltOutlined />}
                onClick={() => {
                  navigateTo(
                    `/metrics/gtfs/feeds?featureName=${metrics.feature}`,
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
    <Box sx={{ m: 10 }}>
      <Typography variant='h5' color='primary' sx={{ fontWeight: 700 }}>
        Features Analytics{' '}
      </Typography>
      <MaterialReactTable table={table} />
    </Box>
  );
}
