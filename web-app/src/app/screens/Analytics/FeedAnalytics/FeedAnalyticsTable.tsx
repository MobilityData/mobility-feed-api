import React, { useMemo } from 'react';
import { type MRT_Cell, type MRT_ColumnDef } from 'material-react-table';
import { format } from 'date-fns';
import { type FeedMetrics } from '../types';
import { groupFeatures, getGroupColor } from '../../../utils/analytics';
import { useNavigate } from 'react-router-dom';
import { Box, Stack } from '@mui/material';

/**
 * Returns the columns for the feed analytics table.
 * @param uniqueErrors list of unique errors
 * @param uniqueWarnings list of unique warnings
 * @param uniqueInfos list of unique infos
 * @param avgErrors average number of errors
 * @param avgWarnings average number of warnings
 * @param avgInfos average number of infos
 * @returns the columns for the feed analytics table
 */
export const useTableColumns = (
  uniqueErrors: string[],
  uniqueWarnings: string[],
  uniqueInfos: string[],
  avgErrors: number,
  avgWarnings: number,
  avgInfos: number,
): Array<MRT_ColumnDef<FeedMetrics>> => {
  const navigate = useNavigate();

  return useMemo<Array<MRT_ColumnDef<FeedMetrics>>>(
    () => [
      {
        accessorKey: 'feed_id',
        header: 'Feed ID',
        enableColumnPinning: true,
        enableHiding: false,
        size: 200,
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<FeedMetrics>;
          renderedCellValue: React.ReactNode;
        }) => (
          <div
            className={'navigable-list-item'}
            onClick={() => {
              navigate(`/feeds/${cell.getValue<string>()}`);
            }}
          >
            {renderedCellValue}
          </div>
        ),
      },
      {
        accessorKey: 'created_on',
        header: 'Created On',
        Cell: ({ cell }) =>
          format(new Date(cell.getValue<number>()), 'yyyy-MM-dd'),
        filterVariant: 'date-range',
        size: 150,
      },
      {
        accessorKey: 'country_code',
        header: 'Country Code',
        size: 100,
      },
      {
        accessorKey: 'country',
        header: 'Country',
        size: 100,
      },
      {
        accessorKey: 'subdivision_name',
        header: 'Subdivision Name',
        size: 100,
      },
      {
        accessorKey: 'municipality',
        header: 'Municipality',
        size: 100,
      },
      {
        accessorKey: 'provider',
        header: 'Provider',
        size: 100,
      },
      {
        accessorKey: 'notices.errors',
        header: 'Errors',
        enableSorting: false,
        Cell: ({ cell }: { cell: MRT_Cell<FeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>().map((error, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/analytics/notices/${error}`);
                }}
              >
                {error}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueErrors,
        size: 150,
        Header: (
          <span>
            Notice Severity :
            <span
              style={{
                background: '#d54402',
                color: 'white',
                borderRadius: '5px',
                padding: 5,
                marginLeft: 5,
              }}
            >
              ERROR
            </span>
          </span>
        ),
        Footer: () => (
          <Stack>
            Average Number of Errors:
            <Box color='warning.main'>{avgErrors}</Box>
          </Stack>
        ),
      },
      {
        accessorKey: 'notices.warnings',
        header: 'Warnings',
        enableSorting: false,
        Cell: ({ cell }: { cell: MRT_Cell<FeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>().map((warning, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/analytics/notices/${warning}`);
                }}
              >
                {warning}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueWarnings,
        size: 150,
        Header: (
          <span>
            Notice Severity :
            <span
              style={{
                background: '#fdba06',
                color: 'black',
                borderRadius: '5px',
                padding: 5,
                marginLeft: 5,
              }}
            >
              WARNING
            </span>
          </span>
        ),
        Footer: () => (
          <Stack>
            Average Number of Warnings:
            <Box color='warning.main'>{avgWarnings}</Box>
          </Stack>
        ),
      },
      {
        accessorKey: 'notices.infos',
        header: 'Infos',
        enableSorting: false,
        Header: (
          <span>
            Notice Severity :
            <span
              style={{
                background: '#9ae095',
                color: 'black',
                borderRadius: '5px',
                padding: 5,
                marginLeft: 5,
              }}
            >
              INFO
            </span>
          </span>
        ),
        Cell: ({ cell }: { cell: MRT_Cell<FeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>().map((info, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/analytics/notices/${info}`);
                }}
              >
                {info}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueInfos,
        size: 150,
        Footer: () => (
          <Stack>
            Average Number of Infos:
            <Box color='warning.main'>{avgInfos}</Box>
          </Stack>
        ),
      },
      {
        accessorKey: 'features',
        header: 'Features',
        enableSorting: false,
        Cell: ({ cell }: { cell: MRT_Cell<FeedMetrics> }) => {
          const { groupedFeatures, otherFeatures } = groupFeatures(
            cell.getValue<string[]>(),
          );
          return (
            <div>
              {Object.entries(groupedFeatures).map(
                ([group, features], index) => (
                  <div key={index} style={{ marginBottom: '10px' }}>
                    <div
                      style={{
                        background: getGroupColor(group),
                        color: 'black',
                        borderRadius: '5px',
                        padding: 5,
                        marginLeft: 5,
                        marginBottom: 5,
                        width: 'fit-content',
                      }}
                    >
                      {group}:
                    </div>
                    {features.map((feature, index) => (
                      <div
                        key={index}
                        style={{ cursor: 'pointer', marginLeft: '10px' }}
                        className={'navigable-list-item'}
                        onClick={() => {
                          navigate(`/features/${feature}`);
                        }}
                      >
                        {feature}
                      </div>
                    ))}
                  </div>
                ),
              )}
              {otherFeatures.length > 0 && (
                <div>
                  <div
                    style={{
                      background: getGroupColor('Other'),
                      color: 'black',
                      borderRadius: '5px',
                      padding: 5,
                      marginLeft: 5,
                      marginBottom: 5,
                      width: 'fit-content',
                    }}
                  >
                    Empty Group:
                  </div>
                  {otherFeatures.map((feature, index) => (
                    <div
                      key={index}
                      style={{ cursor: 'pointer', marginLeft: '10px' }}
                      className={'navigable-list-item'}
                      onClick={() => {
                        navigate(`/analytics/features/${feature}`);
                      }}
                    >
                      {feature}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        },
        size: 300,
      },
      {
        accessorKey: 'dataset_id',
        header: 'Dataset ID',
        size: 200,
      },
    ],
    [
      navigate,
      uniqueErrors,
      uniqueWarnings,
      uniqueInfos,
      avgErrors,
      avgWarnings,
      avgInfos,
    ],
  );
};
