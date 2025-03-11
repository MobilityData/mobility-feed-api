import React, { useMemo, useState } from 'react';
import {
  MaterialReactTable,
  useMaterialReactTable,
  type MRT_ColumnDef,
  type MRT_ColumnFiltersState,
} from 'material-react-table';
import { Box, Tabs, Tab, Typography, Chip, Tooltip } from '@mui/material';
import { getEmojiFlag, type TCountryCode } from 'countries-list';
import { type EntityLocations, getLocationName } from '../services/feeds/utils';

export interface LocationTableProps {
  locations: EntityLocations;
}

export default function Locations({
  locations,
}: LocationTableProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState(0);
  const [tableFilters, setTableFilters] = useState<MRT_ColumnFiltersState>([]);
  const [showFilters, setShowFilters] = useState<boolean>(false);

  const tableData = useMemo(
    () =>
      locations.map((loc) => ({
        country: `${getEmojiFlag(loc.country_code as TCountryCode)} ${
          loc.country ?? ''
        }`,
        country_code: (loc.country_code as TCountryCode) ?? 'Undetermined',
        subdivision: loc.subdivision_name ?? 'Undetermined',
        municipality: loc.municipality ?? 'Undetermined',
      })),
    [locations],
  );

  const uniqueCountries = useMemo(() => {
    const countriesSet = new Set<string>();
    tableData.forEach((loc) => {
      countriesSet.add(loc.country_code); // Use raw country code
    });
    return Array.from(countriesSet);
  }, [tableData]);

  const columns = useMemo<Array<MRT_ColumnDef<(typeof tableData)[0]>>>(
    () => [
      {
        accessorKey: 'country',
        header: 'Country',
        size: 200,
      },
      {
        accessorKey: 'subdivision',
        header: 'Subdivision',
        size: 200,
      },
      {
        accessorKey: 'municipality',
        header: 'Municipality',
        size: 250,
      },
    ],
    [],
  );

  const table = useMaterialReactTable({
    columns,
    data: tableData,
    initialState: {
      sorting: [
        { id: 'country', desc: false },
        { id: 'subdivision', desc: false },
        { id: 'municipality', desc: false },
      ],
      density: 'compact',
    },
    state: {
      columnFilters: tableFilters,
      showColumnFilters: showFilters,
    },
    onColumnFiltersChange: (updater) => {
      const newFilters =
        typeof updater === 'function' ? updater(tableFilters) : updater;
      setTableFilters(newFilters);
    },
    onShowColumnFiltersChange: (show) => {
      setShowFilters(show);
    },
    enableRowVirtualization: true,
    enableHiding: false,
    enableDensityToggle: false,
    enableFacetedValues: true,
    enableGrouping: true,
    enableColumnFilters: true,
    enableExpanding: true,
    enablePagination: false,
    enableStickyHeader: true,
    maxLeafRowFilterDepth: 10,
    enableStickyFooter: false,
    enableColumnResizing: true,
    groupedColumnMode: false,
    positionToolbarAlertBanner: 'none',
    rowVirtualizerOptions: {
      overscan: 10,
    },
    renderBottomToolbar: () => '',
    muiTableContainerProps: { sx: { maxHeight: '250px' } },
  });

  return (
    <Box>
      <Tabs
        value={activeTab}
        onChange={(_, newValue) => {
          setActiveTab(newValue);
        }}
      >
        <Tab label='Summary' sx={{ textTransform: 'none' }} />
        <Tab label='Full List' sx={{ textTransform: 'none' }} />
      </Tabs>

      {activeTab === 0 && (
        <Box sx={{ p: 2, m: 0 }}>
          {locations.length === 1 ? (
            <Typography variant='body1'>
              {getLocationName(locations)}
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {uniqueCountries.map((countryCode) => {
                const subdivisions = new Set<string>();
                const municipalities = new Set<string>();
                const countryName = tableData.find(
                  (loc) => loc.country_code === countryCode,
                )?.country;

                tableData
                  .filter((loc) => loc.country_code === countryCode)
                  .forEach((loc) => {
                    subdivisions.add(loc.subdivision);
                    municipalities.add(loc.municipality);
                  });

                const tooltipText = `${subdivisions.size} subdivisions and ${municipalities.size} municipalities within this country.\nClick for more details.`;

                return (
                  <Tooltip key={countryCode} title={tooltipText} arrow>
                    <Chip
                      label={countryName}
                      onClick={() => {
                        setActiveTab(1);
                        setTableFilters([
                          { id: 'country', value: countryName ?? '' },
                        ]);
                        setShowFilters(true);
                      }}
                      clickable
                    />
                  </Tooltip>
                );
              })}
            </Box>
          )}
        </Box>
      )}

      {activeTab === 1 && (
        <Box sx={{ p: 2 }}>
          <MaterialReactTable table={table} />
        </Box>
      )}
    </Box>
  );
}
