import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

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
import { format } from 'date-fns';
import Box from '@mui/material/Box';
import MUITooltip from '@mui/material/Tooltip';

import { Typography, Button, IconButton } from '@mui/material';
import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import { InfoOutlined, ListAltOutlined } from '@mui/icons-material';
import { type NoticeMetrics } from '../types';

export default function GTFSNoticeAnalytics(): React.ReactElement {
  const navigateTo = useNavigate();
  const { noticeCode } = useParams<{ noticeCode?: string }>();
  const [data, setData] = useState<NoticeMetrics[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(
          'https://storage.googleapis.com/mobilitydata-gtfs-analytics-dev/notices_metrics.json',
        );
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedData = await response.json();
        const dataWLatestCount = fetchedData.map((notice: NoticeMetrics) => ({
          ...notice,
          latest_feed_count: notice.feeds_count.slice(-1)[0],
        }));
        setData(dataWLatestCount);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, []);

  const columns = useMemo<Array<MRT_ColumnDef<NoticeMetrics>>>(
    () => [
      {
        accessorKey: 'notice',
        header: 'Notice',
        size: 300,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<NoticeMetrics>;
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
                      `https://gtfs-validator.mobilitydata.org/rules.html#${cell.getValue<string>()}-rule`,
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
        accessorKey: 'severity',
        header: 'Severity',
        size: 150,
        filterVariant: 'multi-select',
        filterSelectOptions: ['ERROR', 'WARNING', 'INFO'],
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<NoticeMetrics>;
          renderedCellValue: React.ReactNode;
        }) => {
          const severity = cell.getValue<string>();
          const background =
            severity === 'ERROR'
              ? '#d54402'
              : severity === 'WARNING'
                ? '#fdba06'
                : '#9ae095';
          return (
            <span
              style={{
                background,
                color: background === '#d54402' ? 'white' : 'black',
                borderRadius: '5px',
                padding: 5,
              }}
            >
              {renderedCellValue}
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
            id: 'notice',
            value: noticeCode,
          },
        ]
      : [];

  const table = useMaterialReactTable({
    columns,
    data,
    initialState: {
      showColumnFilters: true,
      columnPinning: { left: ['mrt-row-expand', 'notice'] },
      density: 'compact',
      sorting: [{ id: 'notice', desc: false }],
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
        date: format(new Date(date), 'yyyy-MM'),
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
                    `/metrics/gtfs/feeds?severity=${metrics.severity}&noticeCode=${metrics.notice}`,
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
        Notices Analytics{' '}
      </Typography>
      <MaterialReactTable table={table} />
    </Box>
  );
}
