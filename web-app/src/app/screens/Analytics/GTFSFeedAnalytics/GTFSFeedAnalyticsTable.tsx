import React, { useMemo } from 'react';
import { type MRT_Cell, type MRT_ColumnDef } from 'material-react-table';
import { format } from 'date-fns';
import { type GTFSFeedMetrics } from '../types';
import { groupFeatures, getGroupColor } from '../../../utils/analytics';
import { useNavigate } from 'react-router-dom';
import { Box, MenuItem, Stack, Tooltip } from '@mui/material';
import { OpenInNew } from '@mui/icons-material';

/**
 * Returns the columns for the feed analytics table.
 * @param uniqueErrors list of unique errors
 * @param uniqueWarnings list of unique warnings
 * @param uniqueInfos list of unique infos
 * @param uniqueFeatures list of unique features
 * @param avgErrors average number of errors
 * @param avgWarnings average number of warnings
 * @param avgInfos average number of infos
 * @returns the columns for the feed analytics table
 */
export const useTableColumns = (
  uniqueErrors: string[],
  uniqueWarnings: string[],
  uniqueInfos: string[],
  uniqueFeatures: string[],
  avgErrors: number,
  avgWarnings: number,
  avgInfos: number,
): Array<MRT_ColumnDef<GTFSFeedMetrics>> => {
  const navigate = useNavigate();

  return useMemo<Array<MRT_ColumnDef<GTFSFeedMetrics>>>(
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
          cell: MRT_Cell<GTFSFeedMetrics>;
          renderedCellValue: React.ReactNode;
        }) => (
          <Tooltip
            title={`Open feed ${cell.getValue<string>()} page in new tab`}
            placement='top-start'
          >
            <div
              className={'navigable-list-item'}
              onClick={() => {
                const url = `/feeds/${cell.getValue<string>()}`;
                window.open(url, '_blank');
              }}
            >
              {renderedCellValue}{' '}
              <OpenInNew sx={{ verticalAlign: 'middle' }} fontSize='small' />
            </div>
          </Tooltip>
        ),
      },
      {
        accessorKey: 'created_on',
        header: 'Created On',
        Cell: ({ cell }) =>
          format(new Date(cell.getValue<number>()), 'yyyy-MM-dd'),
        filterVariant: 'date-range',
        size: 180,
      },
      {
        accessorKey: 'locations_string',
        header: 'Locations',
        size: 220,
        filterVariant: 'autocomplete',
        filterFn: 'contains',
        columnFilterModeOptions: [
          'contains',
          'startsWith',
          'equalsString',
          'doesNotInclude',
        ],
        renderColumnFilterModeMenuItems: ({ onSelectFilterMode }) => [
          <MenuItem
            key='contains'
            onClick={() => {
              onSelectFilterMode('contains');
            }}
          >
            Contains
          </MenuItem>,
          <MenuItem
            key='startsWith'
            onClick={() => {
              onSelectFilterMode('startsWith');
            }}
          >
            Starts With
          </MenuItem>,
          <MenuItem
            key='equalsString'
            onClick={() => {
              onSelectFilterMode('equalsString');
            }}
          >
            Equals String
          </MenuItem>,
          <MenuItem
            key='notEquals'
            onClick={() => {
              onSelectFilterMode('notEquals');
            }}
          >
            Not Equals
          </MenuItem>,
          <MenuItem
            key='doesNotInclude'
            onClick={() => {
              onSelectFilterMode('doesNotInclude');
            }}
          >
            Does Not Include
          </MenuItem>,
        ],
      },
      {
        accessorKey: 'provider',
        header: 'Provider',
        Cell: ({
          cell,
          renderedCellValue,
        }: {
          cell: MRT_Cell<GTFSFeedMetrics>;
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
        accessorKey: 'notices.errors',
        header: 'Errors',
        enableSorting: false,
        Cell: ({ cell }: { cell: MRT_Cell<GTFSFeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>()?.map((error, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/metrics/gtfs/notices?noticeCode=${error}`);
                }}
              >
                {error}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueErrors,
        size: 300,
        Header: (
          <span>
            Notice Severity :
            <span className='notice-severity-error notice-severity-label'>
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
        Cell: ({ cell }: { cell: MRT_Cell<GTFSFeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>()?.map((warning, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/metrics/gtfs/notices?noticeCode=${warning}`);
                }}
              >
                {warning}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueWarnings,
        size: 300,
        Header: (
          <span>
            Notice Severity :
            <span className='notice-severity-warning notice-severity-label'>
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
            <span className='notice-severity-info notice-severity-label'>
              INFO
            </span>
          </span>
        ),
        Cell: ({ cell }: { cell: MRT_Cell<GTFSFeedMetrics> }) => (
          <div>
            {cell.getValue<string[]>()?.map((info, index) => (
              <div
                key={index}
                style={{
                  cursor: 'pointer',
                  marginBottom: 2,
                  padding: 1,
                }}
                className={'navigable-list-item'}
                onClick={() => {
                  navigate(`/metrics/gtfs/notices?noticeCode=${info}`);
                }}
              >
                {info}
              </div>
            ))}
          </div>
        ),
        filterVariant: 'multi-select',
        filterSelectOptions: uniqueInfos,
        size: 300,
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
        filterFn: (value, _, filterValue) => {
          const originalValue = value.original;
          const features = originalValue.features;
          return features.some((feature) => {
            return feature.toLowerCase().includes(filterValue.toLowerCase());
          });
        },
        enableSorting: false,
        Cell: ({ cell }: { cell: MRT_Cell<GTFSFeedMetrics> }) => {
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
                          navigate(
                            `/metrics/gtfs/features?featureName=${feature}`,
                          );
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
                        navigate(
                          `/metrics/gtfs/features?featureName=${feature}`,
                        );
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
        size: 200,
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
      uniqueFeatures,
      avgErrors,
      avgWarnings,
      avgInfos,
    ],
  );
};
