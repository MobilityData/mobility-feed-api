import * as React from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  styled,
} from '@mui/material';
import { type AllFeedsType } from '../../services/feeds/utils';
import { type FeedLocations } from '../../types';
import BusAlertIcon from '@mui/icons-material/BusAlert';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import { useNavigate } from 'react-router-dom';

export interface SearchTableProps {
  feedsData: AllFeedsType | undefined;
}

const HeaderTableCell = styled(TableCell)(() => ({
  fontWeight: 'bold',
  fontSize: '18px',
  border: 'none',
}));

const getDataTypeElement = (dataType: 'gtfs' | 'gtfs_rt'): JSX.Element => {
  const DataTypeHolder = ({
    children,
  }: {
    children: React.ReactNode;
  }): JSX.Element => {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          p: 1,
          justifyContent: 'flex-end',
        }}
      >
        {children}
      </Box>
    );
  };
  if (dataType === 'gtfs') {
    return (
      <DataTypeHolder>
        <DirectionsBusIcon sx={{ m: 1 }}></DirectionsBusIcon>
        GTFS Schedule
      </DataTypeHolder>
    );
  } else {
    return (
      <DataTypeHolder>
        <BusAlertIcon sx={{ m: 1 }}></BusAlertIcon>
        GTFS Realtime
      </DataTypeHolder>
    );
  }
};

const getLocationName = (locations: FeedLocations): string => {
  if (locations?.[0] === undefined) {
    return '';
  }
  const firstLocation = locations[0];
  const municipality =
    firstLocation.municipality !== undefined &&
    firstLocation.municipality !== null
      ? `${firstLocation.municipality}, `
      : '';
  const subdivison =
    firstLocation.subdivision_name !== undefined &&
    firstLocation.subdivision_name !== null
      ? `${firstLocation.subdivision_name}, `
      : '';
  const countryCode = firstLocation.country_code ?? '';
  return municipality + subdivison + countryCode;
};

export default function SearchTable({
  feedsData,
}: SearchTableProps): React.ReactElement {
  if (feedsData === undefined) return <></>;
  const navigate = useNavigate();
  return (
    <Table
      size='small'
      sx={{
        minWidth: 650,
        borderCollapse: 'separate',
      }}
      aria-label='simple table'
    >
      <TableHead
        sx={{
          fontWeight: 'bold',
        }}
      >
        <TableRow>
          <HeaderTableCell>Transit Provider</HeaderTableCell>
          <HeaderTableCell>Location</HeaderTableCell>
          <HeaderTableCell align='right'>Feed Description</HeaderTableCell>
          <HeaderTableCell align='right'>Data Type</HeaderTableCell>
        </TableRow>
      </TableHead>

      <TableBody
        sx={{
          'tr:first-child td:last-child': {
            borderTopRightRadius: '6px',
          },
          'tr:first-child td:first-child': {
            borderTopLeftRadius: '6px',
          },
          'tr:first-child td': {
            borderTop: '1px solid black',
          },
          'tr:last-child td:last-child': {
            borderBottomRightRadius: '6px',
          },
          'tr:last-child td:first-child': {
            borderBottomLeftRadius: '6px',
          },
          'tr:last-child td': {
            borderBottom: '1px solid black',
          },
          'tr td:first-child': {
            borderLeft: '1px solid black',
          },
          'tr td:last-child': {
            borderRight: '1px solid black',
            minWidth: '205px',
          },
        }}
      >
        {feedsData?.results?.map((feed) => (
          <TableRow
            key={feed.id}
            sx={{
              backgroundColor: 'white',
              td: {
                fontSize: '16px',
                borderBottom: '1px solid black',
              },
              '&:hover': {
                backgroundColor: '#F8F5F5',
                cursor: 'pointer',
              },
            }}
            onClick={() => {
              navigate(`/feeds/${feed.id}`);
            }}
          >
            <TableCell>{feed.provider}</TableCell>
            <TableCell>{getLocationName(feed.locations)}</TableCell>
            <TableCell align='right'>{feed.note}</TableCell>
            <TableCell align='left'>
              {getDataTypeElement(feed.data_type)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
