import React from 'react';
import { Box, Typography, Grid, Button } from '@mui/material';
import { format } from 'date-fns';
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
  LocationOn,
  Business,
  TrendingUp,
  InfoOutlined,
  Key,
  CalendarToday,
} from '@mui/icons-material';
import { type GTFSFeedMetrics } from '../types';
import { getLocationName } from '../../../services/feeds/utils';

interface RowData {
  original: GTFSFeedMetrics;
}

interface RenderDetailPanelProps {
  row: RowData;
}

const getTrendDescription = (current: number, previous: number): string => {
  if (current > previous) {
    return 'Increase';
  } else if (current < previous) {
    return 'Decrease';
  } else {
    return 'No Change';
  }
};

const DetailPanel: React.FC<RenderDetailPanelProps> = ({ row }) => {
  const theme = useTheme();
  const { metrics, locations, provider } = row.original;

  if (metrics == null) {
    return <div>No metrics available</div>;
  }

  const chartData = metrics.computed_on.map((date, index) => {
    const utcDate = new Date(date).toLocaleDateString('en-CA', {
      timeZone: 'UTC',
    }); // Converts the date to UTC

    return {
      date: utcDate,
      errors: metrics.errors_count[index],
      warnings: metrics.warnings_count[index],
      infos: metrics.infos_count[index],
    };
  });

  const domain = [
    new Date(metrics.computed_on[0]).getTime(),
    new Date().getTime(),
  ];

  const lastErrors = metrics.errors_count.slice(-2);
  const lastWarnings = metrics.warnings_count.slice(-2);
  const lastInfos = metrics.infos_count.slice(-2);

  return (
    <Box sx={{ maxWidth: '800px', margin: 'auto', padding: 2 }}>
      <Grid container spacing={3}>
        <Grid size={{xs: 12, md: 6}}>
          <Typography variant='subtitle1' gutterBottom>
            Monthly Feed Validation Metrics
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
                dataKey='errors'
                stroke={theme.palette.error.main}
                strokeWidth={2}
              />
              <Line dataKey='warnings' stroke='#fdba06' strokeWidth={2} />
              <Line dataKey='infos' stroke='#9ae095' strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <Box
            sx={{
              padding: 2,
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: 2,
              backgroundColor: theme.palette.background.paper,
            }}
          >
            <Typography variant='subtitle1' gutterBottom color='primary'>
              Feed Details
            </Typography>
            <Typography
              variant='body1'
              gutterBottom
              display='flex'
              alignItems='center'
            >
              <Key
                fontSize='small'
                sx={{ marginRight: 1, transform: 'rotate(45deg)' }}
              />
              <strong style={{ marginRight: 5 }}>Feed ID:</strong>{' '}
              {row.original.feed_id}
            </Typography>
            <Typography
              variant='body1'
              gutterBottom
              display='flex'
              alignItems='center'
            >
              <CalendarToday style={{ marginRight: 5 }} fontSize={'small'} />
              <strong style={{ marginRight: 5 }}>Added On:</strong>{' '}
              {format(new Date(row.original.created_on), 'yyyy-MM-dd')}
            </Typography>
            <Typography
              variant='body1'
              gutterBottom
              display='flex'
              alignItems='center'
            >
              <LocationOn fontSize='small' sx={{ marginRight: 1 }} />
              <strong style={{ marginRight: 5 }}>Locations:</strong>
              {getLocationName(locations)}
            </Typography>
            <Typography
              variant='body1'
              gutterBottom
              display='flex'
              alignItems='center'
            >
              <Business fontSize='small' sx={{ marginRight: 1 }} />
              <strong style={{ marginRight: 5 }}>Provider:</strong> {provider}
            </Typography>
            <Typography
              variant='subtitle1'
              gutterBottom
              display='flex'
              alignItems='center'
            >
              <TrendingUp fontSize='small' sx={{ marginRight: 1 }} />
              <strong>Trends:</strong>
            </Typography>
            <div style={{ marginLeft: 25 }}>
              <Typography variant='body2' gutterBottom>
                Errors: {getTrendDescription(lastErrors[1], lastErrors[0])}
              </Typography>
              <Typography variant='body2' gutterBottom>
                Warnings:{' '}
                {getTrendDescription(lastWarnings[1], lastWarnings[0])}
              </Typography>
              <Typography variant='body2' gutterBottom>
                Infos: {getTrendDescription(lastInfos[1], lastInfos[0])}
              </Typography>
            </div>
            <div>
              <Typography
                variant='body2'
                gutterBottom
                display='flex'
                alignItems='center'
              >
                <InfoOutlined fontSize='small' style={{ marginRight: 2 }} />{' '}
                Visit the
                <Button
                  variant='text'
                  className='inline'
                  href={`/feeds/${row.original.feed_id}`}
                >
                  feed&apos;s page
                </Button>
                page for more information.
              </Typography>
            </div>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DetailPanel;
