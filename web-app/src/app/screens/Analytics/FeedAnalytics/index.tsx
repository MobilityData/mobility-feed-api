import { useMemo } from 'react';
import {
  MaterialReactTable,
  useMaterialReactTable,
} from 'material-react-table';
import { Box, Typography } from '@mui/material';
import { useFetchData, useFetchMetrics } from './hooks';
import { useTableColumns } from './FeedAnalyticsTable';
import { format } from 'date-fns';
import { useTheme } from '@mui/material/styles';
import {
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import '../analytics.css';
import { useLocation } from 'react-router-dom';

export default function FeedAnalytics(): React.ReactElement {
  const { search } = useLocation();
  const params = new URLSearchParams(search);

  const severity = params.get('severity');
  const noticeCode = params.get('noticeCode');
  const featureName = params.get('featureName');

  const { data, loading } = useFetchData(
    'https://storage.googleapis.com/mobilitydata-analytics-dev/analytics_2024_07.json',
  );
  const metrics = useFetchMetrics(
    'https://storage.googleapis.com/mobilitydata-analytics-dev/feed_metrics.json',
  );

  const dataWithMetrics = useMemo(() => {
    return data.map((feed) => ({
      ...feed,
      metrics: metrics.find((metric) => metric.feed_id === feed.feed_id),
    }));
  }, [data, metrics]);

  const uniqueErrors = useMemo(() => {
    const errors = data.map((item) => item.notices.errors).flat();
    errors.sort();
    return Array.from(new Set(errors));
  }, [data]);

  const uniqueWarnings = useMemo(() => {
    const warnings = data.map((item) => item.notices.warnings).flat();
    warnings.sort();
    return Array.from(new Set(warnings));
  }, [data]);

  const uniqueInfos = useMemo(() => {
    const infos = data.map((item) => item.notices.infos).flat();
    infos.sort();
    return Array.from(new Set(infos));
  }, [data]);

  const avgErrors = useMemo(() => {
    const totalErrors = data.reduce(
      (acc, item) => acc + item.notices.errors.length,
      0,
    );
    return Math.round(totalErrors / data.length);
  }, [data]);

  const avgWarnings = useMemo(() => {
    const totalWarnings = data.reduce(
      (acc, item) => acc + item.notices.warnings.length,
      0,
    );
    return Math.round(totalWarnings / data.length);
  }, [data]);

  const avgInfos = useMemo(() => {
    const totalInfos = data.reduce(
      (acc, item) => acc + item.notices.infos.length,
      0,
    );
    return Math.round(totalInfos / data.length);
  }, [data]);

  const initialFilters = useMemo(() => {
    const filters = [];
    filters.push({
      id: 'features',
      value: featureName,
    });
    if (severity != null && noticeCode != null) {
      const id =
        severity === 'ERROR'
          ? 'notices.errors'
          : severity === 'WARNING'
            ? 'notices.warnings'
            : severity === 'INFO'
              ? 'notices.infos'
              : undefined;
      if (id !== undefined) {
        filters.push({
          id,
          value: [noticeCode],
        });
      }
    }
    console.log('filters', filters);
    return filters;
  }, [severity, noticeCode, featureName]);

  const columns = useTableColumns(
    uniqueErrors,
    uniqueWarnings,
    uniqueInfos,
    avgErrors,
    avgWarnings,
    avgInfos,
  );

  const table = useMaterialReactTable({
    columns,
    data: dataWithMetrics,
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
    renderDetailPanel: ({ row }) => {
      const theme = useTheme();
      const metrics = row.original.metrics;

      if (metrics === undefined) {
        return <div>No metrics available</div>;
      }

      const chartData = metrics.computed_on.map((date, index) => ({
        date: format(new Date(date), 'yyyy-MM'),
        errors: metrics.errors_count[index],
        warnings: metrics.warnings_count[index],
        infos: metrics.infos_count[index],
      }));
      const domain = [
        new Date(metrics.computed_on[0]).getTime(),
        new Date().getTime(),
      ];

      return (
        <Box sx={{ maxWidth: '600px', margin: 'auto' }}>
          <Typography gutterBottom>Monthly Feed Validation Metrics</Typography>
          <ResponsiveContainer width='100%' height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray='3 3' />
              <XAxis
                dataKey='date'
                tick={false}
                tickFormatter={(date) => format(new Date(date), 'yyyy-MM')}
                domain={domain}
              />

              <YAxis />
              <Tooltip
                labelFormatter={(label) => format(new Date(label), 'yyyy-MM')}
              />
              <Legend />
              <Brush
                dataKey='date'
                height={30}
                stroke={theme.palette.primary.main}
              />
              <Bar dataKey='errors' fill={theme.palette.error.main} />
              <Bar dataKey='warnings' fill={'#fbba18'} />
              <Bar dataKey='infos' fill={'#9ee199'} />
            </BarChart>
          </ResponsiveContainer>
        </Box>
      );
    },
    muiTableBodyCellProps: ({ cell }) => ({
      onClick: (event) => {
        console.info(event, cell.id);
      },
    }),
  });

  if (loading) {
    return <div>Loading...</div>;
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
