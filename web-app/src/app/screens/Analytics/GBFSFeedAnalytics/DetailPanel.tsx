import React, { useMemo } from 'react';
import { Box, Typography, Grid } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import {
  Brush,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
} from 'material-react-table';
import { type GBFSFeedMetrics, type GBFSNotice } from '../types';
import { InfoOutlined } from '@mui/icons-material';

interface RowData {
  original: GBFSFeedMetrics;
}

interface RenderDetailPanelProps {
  row: RowData;
}

const DetailPanel: React.FC<RenderDetailPanelProps> = ({ row }) => {
  const theme = useTheme();
  const { notices, metrics } = row.original;

  if (metrics == null) {
    return <div>No metrics available</div>;
  }

  const chartData = metrics.computed_on.map((date, index) => {
    const utcDate = new Date(date).toLocaleDateString('en-CA', {
      timeZone: 'UTC',
    }); // Converts the date to UTC

    return {
      date: utcDate,
      count: metrics.errors_count[index],
    };
  });

  const domain = [
    new Date(chartData[0]?.date ?? '').getTime(),
    new Date().getTime(),
  ];

  // Define the columns for the notices table
  const columns = useMemo<Array<MRT_ColumnDef<GBFSNotice>>>(
    () => [
      {
        accessorKey: 'keyword',
        header: 'Keyword',
        size: 150,
      },
      {
        accessorKey: 'gbfs_file',
        header: 'GBFS File',
        size: 200,
      },
      {
        accessorKey: 'count',
        header: 'Count',
        size: 100,
      },
      {
        accessorKey: 'schema_path',
        header: 'Schema Path',
        size: 250,
      },
    ],
    [],
  );

  const table = useMaterialReactTable({
    columns,
    data: notices,
    initialState: {
      density: 'compact',
      sorting: [{ id: 'keyword', desc: false }],
    },
    enableStickyHeader: true,
    enableStickyFooter: true,
    muiTableContainerProps: { sx: { maxHeight: '50vh' } },
  });

  return (
    <Grid container spacing={3} sx={{ maxWidth: '1200px' }}>
      <Grid size={{xs: 12, md: 8}}>
        <Typography variant='subtitle1' gutterBottom>
          Notices
        </Typography>
        <MaterialReactTable table={table} />
        {notices.length === 0 && (
          <Box sx={{ textAlign: 'center', padding: 2 }}>
            <InfoOutlined
              sx={{ marginRight: 1, verticalAlign: 'middle' }}
              fontSize='small'
            />
            No errors found.
          </Box>
        )}
      </Grid>
      <Grid size={{xs: 12, md: 4}}>
        <Typography variant='subtitle1' gutterBottom>
          Monthly Notice Count Trends
        </Typography>
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
              dataKey='count'
              stroke={theme.palette.error.main}
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </Grid>
    </Grid>
  );
};

export default DetailPanel;
