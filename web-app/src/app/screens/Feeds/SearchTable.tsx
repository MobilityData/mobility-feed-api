import * as React from 'react';
import {
  Box,
  Chip,
  IconButton,
  Popover,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  colors,
  styled,
} from '@mui/material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
  type AllFeedsType,
  getLocationName,
} from '../../services/feeds/utils';
import BusAlertIcon from '@mui/icons-material/BusAlert';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import GtfsRtEntities from './GtfsRtEntities';
import CloseIcon from '@mui/icons-material/Close';

export interface SearchTableProps {
  feedsData: AllFeedsType | undefined;
}

const HeaderTableCell = styled(TableCell)(() => ({
  fontWeight: 'bold',
  fontSize: '18px',
  border: 'none',
}));

export const getDataTypeElement = (
  dataType: 'gtfs' | 'gtfs_rt',
): JSX.Element => {
  const { t } = useTranslation('feeds');
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
          justifyContent: 'flex-start',
        }}
      >
        {children}
      </Box>
    );
  };
  if (dataType === 'gtfs') {
    return (
      <DataTypeHolder>
        <DirectionsBusIcon sx={{ m: 1, ml: 0 }}></DirectionsBusIcon>
        {t('common:gtfsSchedule')}
      </DataTypeHolder>
    );
  } else {
    return (
      <DataTypeHolder>
        <BusAlertIcon sx={{ m: 1, ml: 0 }}></BusAlertIcon>
        {t('common:gtfsRealtime')}
      </DataTypeHolder>
    );
  }
};

export default function SearchTable({
  feedsData,
}: SearchTableProps): React.ReactElement {
  const [providersPopoverData, setProvidersPopoverData] = React.useState<
    string[] | undefined
  >(undefined);
  const { t } = useTranslation('feeds');
  if (feedsData === undefined) return <></>;
  const navigate = useNavigate();

  const getProviderElement = (
    feed: GTFSFeedType | GTFSRTFeedType,
  ): JSX.Element => {
    const providers =
      feed?.provider
        ?.split(',')
        .filter((x) => x)
        .sort() ?? [];
    const displayName = providers[0];
    let manyProviders: JSX.Element | undefined;
    if (providers.length > 1) {
      manyProviders = (
        <a
          style={{
            fontStyle: 'italic',
            fontSize: '14px',
            fontWeight: 'bold',
            color: colors.blue[900],
          }}
          onClick={(event) => {
            event.stopPropagation();
            setProvidersPopoverData(providers);
          }}
        >
          +&nbsp;{providers.length - 1}
        </a>
      );
    }
    return (
      <>
        {displayName} {manyProviders}
        {feed?.status === 'deprecated' && (
          <Box sx={{ mt: '5px' }}>
            <Chip
              label={t('deprecated')}
              icon={<ErrorOutlineIcon />}
              color='error'
              size='small'
              variant='outlined'
            />
          </Box>
        )}
      </>
    );
  };

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
          <HeaderTableCell>{t('transitProvider')}</HeaderTableCell>
          <HeaderTableCell>{t('location')}</HeaderTableCell>
          <HeaderTableCell>{t('feedDescription')}</HeaderTableCell>
          <HeaderTableCell>{t('dataType')}</HeaderTableCell>
        </TableRow>
      </TableHead>

      <TableBody
        sx={{
          'tr:first-of-type td:last-child': {
            borderTopRightRadius: '6px',
          },
          'tr:first-of-type td:first-of-type': {
            borderTopLeftRadius: '6px',
          },
          'tr:first-of-type td': {
            borderTop: '1px solid black',
          },
          'tr:last-child td:last-child': {
            borderBottomRightRadius: '6px',
          },
          'tr:last-child td:first-of-type': {
            borderBottomLeftRadius: '6px',
          },
          'tr:last-child td': {
            borderBottom: '1px solid black',
          },
          'tr td:first-of-type': {
            borderLeft: '1px solid black',
          },
          'tr td:last-child': {
            borderRight: '1px solid black',
            minWidth: '210px',
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
            <TableCell>{getProviderElement(feed)}</TableCell>
            <TableCell>{getLocationName(feed.locations)}</TableCell>
            <TableCell>{feed.feed_name}</TableCell>
            <TableCell>
              <Box sx={{ display: 'flex' }}>
                {getDataTypeElement(feed.data_type)}
                {feed.data_type === 'gtfs_rt' && (
                  <GtfsRtEntities entities={feed.entity_types}></GtfsRtEntities>
                )}
              </Box>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
      {providersPopoverData !== undefined && (
        <Popover
          open={providersPopoverData !== undefined}
          onClose={() => {
            setProvidersPopoverData(undefined);
          }}
          anchorReference='none'
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '10px',
              width: '500px',
              maxWidth: '100%',
            }}
          >
            <Typography variant='h6' sx={{ p: 0 }}>
              Transit Providers - {providersPopoverData[0]}
            </Typography>
            <IconButton
              onClick={() => {
                setProvidersPopoverData(undefined);
              }}
            >
              <CloseIcon />
            </IconButton>
          </Box>

          <Box sx={{ maxHeight: '700px', overflowY: 'scroll' }}>
            <ul>
              {providersPopoverData.map((provider) => (
                <li key={provider}>{provider}</li>
              ))}
            </ul>
          </Box>
        </Popover>
      )}
    </Table>
  );
}
