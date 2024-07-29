import React, { useMemo } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  MaterialReactTable,
  useMaterialReactTable,
} from 'material-react-table';
import { Box, Typography } from '@mui/material';
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
import { fetchDataStart } from '../../../store/analytics-reducer';
import {
  selectFeedMetrics,
  selectAnalyticsStatus,
  selectAnalyticsError,
} from '../../../store/analytics-selector';
import { useTableColumns } from './FeedAnalyticsTable';

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

  React.useEffect(() => {
    dispatch(fetchDataStart());
  }, [dispatch]);

  const uniqueErrors = useMemo(() => {
    const errors = data.flatMap((item) => item.notices.errors);
    return Array.from(new Set(errors)).sort();
  }, [data]);

  const uniqueWarnings = useMemo(() => {
    const warnings = data.flatMap((item) => item.notices.warnings);
    return Array.from(new Set(warnings)).sort();
  }, [data]);

  const uniqueInfos = useMemo(() => {
    const infos = data.flatMap((item) => item.notices.infos);
    return Array.from(new Set(infos)).sort();
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
    renderDetailPanel: ({ row }) => {
      const theme = useTheme();
      const metrics = row.original.metrics;

      if (metrics == null) {
        return <div>No metrics available</div>;
      }

      const chartData = metrics.computed_on.map((date, index) => ({
        date: format(new Date(date), 'yyyy-MM'),
        errors: metrics.errors_count[index],
        warnings: metrics.warnings_count[index],
        infos: metrics.infos_count[index],
      }));
      const domain = [
        new Date(metrics?.computed_on[0]).getTime(),
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
  });

  if (status === 'loading') {
    return <div>Loading...</div>;
  }

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
