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
import {
  Typography,
  Button,
  IconButton,
  Alert,
  AlertTitle,
} from '@mui/material';
import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import { InfoOutlined, ListAltOutlined } from '@mui/icons-material';
import { type FeatureMetrics } from '../types';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import MUITooltip from '@mui/material/Tooltip';
import { GTFS_ORG_LINK } from '../../../constants/Navigation';
import {
  DATASET_FEATURES,
  getComponentDecorators,
} from '../../../utils/consts';

export default function GTFSFeatureAnalytics(): React.ReactElement {
  const navigateTo = useNavigate();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const featureName = params.get('featureName');
  const [data, setData] = useState<FeatureMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { config } = useRemoteConfig();

  const getUniqueKeyStringValues = (key: keyof FeatureMetrics): string[] => {
    const subGroups = new Set<string>();
    data.forEach((item) => {
      if (item[key] !== undefined) {
        subGroups.add(item[key] as string);
      }
    });
    return Array.from(subGroups);
  };

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
        const dataWithGroups = fetchedData.map((feature: FeatureMetrics) => {
          return {
            ...feature,
            latest_feed_count: feature.feeds_count.slice(-1)[0],
            feature_group: DATASET_FEATURES[feature.feature]?.component,
            feature_sub_group:
              DATASET_FEATURES[feature.feature]?.componentSubgroup,
          };
        });
        setData(dataWithGroups);
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

  const columns = useMemo<Array<MRT_ColumnDef<FeatureMetrics>>>(
    () => [
      {
        accessorKey: 'feature',
        header: 'Feature Name',
        size: 300,
        enableClickToCopy: true,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<FeatureMetrics>;
          renderedCellValue: React.ReactNode;
        }) => {
          return (
            <div>
              {renderedCellValue}
              <MUITooltip
                title={`View ${cell.getValue<string>()} definition`}
                arrow
              >
                <IconButton
                  onClick={() => {
                    window.open(
                      `${GTFS_ORG_LINK}/getting_started/features/base_add-ons/#${cell
                        .getValue<string>()
                        .toLowerCase()}`,
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
        accessorKey: 'feature_group',
        header: 'Feature Group',
        size: 200,
        filterVariant: 'multi-select',
        filterSelectOptions: getUniqueKeyStringValues('feature_group'),
        Cell: ({ cell }: { cell: MRT_Cell<FeatureMetrics> }) => {
          const group = cell.getValue<string>();
          return group == null ? null : (
            <span
              style={{
                backgroundColor: getComponentDecorators(group).color,
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
        accessorKey: 'feature_sub_group',
        header: 'Feature Sub Group',
        size: 200,
        filterVariant: 'multi-select',
        filterSelectOptions: getUniqueKeyStringValues('feature_sub_group'),
        Cell: ({ cell }: { cell: MRT_Cell<FeatureMetrics> }) => {
          const group = cell.getValue<string>();
          return group == null ? null : (
            <span
              style={{
                backgroundColor: getComponentDecorators(group).color,
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

  return (
    <Box sx={{ mx: 6 }}>
      <Typography
        component='h1'
        variant='h4'
        color='primary'
        sx={{ fontWeight: 700, mb: 2 }}
      >
        GTFS Features Metrics{' '}
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
