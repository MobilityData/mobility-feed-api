import React, { useMemo } from 'react';
import { type MRT_Cell, type MRT_ColumnDef } from 'material-react-table';
import { format } from 'date-fns';
import { type GBFSFeedMetrics } from '../types';
import { useNavigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { OpenInNew } from '@mui/icons-material';

/**
 * Returns the columns for the GBFS feed analytics table.
 * @returns the columns for the GBFS feed analytics table
 */
export const useTableColumns = (): Array<
  MRT_ColumnDef<GBFSFeedMetrics & { error_count: number }>
> => {
  const navigate = useNavigate();

  return useMemo<
    Array<MRT_ColumnDef<GBFSFeedMetrics & { error_count: number }>>
  >(
    () => [
      {
        accessorKey: 'feed_id',
        header: 'Feed ID',
        enableColumnPinning: true,
        enableHiding: false,
        size: 200,
      },
      {
        accessorKey: 'system_id',
        header: 'System ID',
        size: 200,
      },
      {
        accessorKey: 'created_on',
        header: 'Created On',
        Cell: ({ cell }) =>
          format(new Date(cell.getValue<string>()), 'yyyy-MM-dd'),
        filterVariant: 'date-range',
        size: 180,
      },
      {
        accessorKey: 'locations_string',
        header: 'Locations',
        size: 220,
      },
      {
        accessorKey: 'operator',
        header: 'Operator',
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<GBFSFeedMetrics & { error_count: number }>;
          renderedCellValue: React.ReactNode;
        }) => (
          <Box
            sx={{
              maxWidth: 200,
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
            }}
          >
            {renderedCellValue}
          </Box>
        ),
        size: 150,
      },
      {
        accessorKey: 'error_count',
        header: 'Nb of Errors',
        filterVariant: 'range-slider',
        filterFn: 'betweenInclusive',
        muiFilterSliderProps: {
          marks: true,
          step: 1,
        },
        size: 180,
      },
      {
        accessorKey: 'versions',
        header: 'Versions',
        enableSorting: false,
        Cell: ({
          cell,
        }: {
          cell: MRT_Cell<GBFSFeedMetrics & { error_count: number }>;
        }) => (
          <div>
            {cell.getValue<string[]>()?.map((version, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/metrics/gbfs/versions?version=${version}`);
                }}
              >
                {version}
              </div>
            ))}
          </div>
        ),
      },
      {
        accessorKey: 'snapshot_hosted_url',
        header: 'Hosted URL',
        size: 200,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<GBFSFeedMetrics & { error_count: number }>;
          renderedCellValue: React.ReactNode;
        }) => (
          <a href={cell.getValue<string>()} target='_blank' rel='noreferrer'>
            {renderedCellValue}{' '}
            <OpenInNew fontSize='small' sx={{ verticalAlign: 'middle' }} />
          </a>
        ),
      },
      {
        accessorKey: 'auto_discovery_url',
        header: 'Auto Discovery URL',
        size: 200,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<GBFSFeedMetrics & { error_count: number }>;
          renderedCellValue: React.ReactNode;
        }) => (
          <a href={cell.getValue<string>()} target='_blank' rel='noreferrer'>
            {renderedCellValue}{' '}
            <OpenInNew fontSize='small' sx={{ verticalAlign: 'middle' }} />
          </a>
        ),
      },
      {
        accessorKey: 'snapshot_id',
        header: 'Snapshot ID',
        size: 200,
      },
    ],
    [navigate],
  );
};
