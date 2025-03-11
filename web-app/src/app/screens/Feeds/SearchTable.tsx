import * as React from 'react';
import {
  Box,
  Chip,
  Popper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
  styled,
  useTheme,
} from '@mui/material';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
  type AllFeedsType,
  getLocationName,
  getCountryLocationSummaries,
} from '../../services/feeds/utils';
import BusAlertIcon from '@mui/icons-material/BusAlert';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useTranslation } from 'react-i18next';
import GtfsRtEntities from './GtfsRtEntities';
import { Link } from 'react-router-dom';
import VerifiedIcon from '@mui/icons-material/Verified';
import { verificationBadgeStyle } from '../../styles/VerificationBadge.styles';
import { getEmojiFlag, type TCountryCode } from 'countries-list';

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
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [providersPopoverData, setProvidersPopoverData] = React.useState<
    string[] | undefined
  >(undefined);
  const { t } = useTranslation('feeds');
  if (feedsData === undefined) return <></>;

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
        <span
          style={{
            fontStyle: 'italic',
            fontSize: '14px',
            fontWeight: 'bold',
            color: theme.palette.primary.main,
            padding: 2,
          }}
          onMouseEnter={(event) => {
            setProvidersPopoverData(providers);
            setAnchorEl(event.currentTarget);
          }}
          onMouseLeave={() => {
            setProvidersPopoverData(undefined);
            setAnchorEl(null);
          }}
        >
          +&nbsp;{providers.length - 1}
        </span>
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

  // Reason for all component overrite is for SEO purposes.
  // TODO: This code is stretching the limits using <Table> to refactor out of table
  return (
    <Table
      component={Box}
      size='small'
      sx={{
        minWidth: 650,
        borderCollapse: 'separate',
      }}
      aria-label='simple table'
    >
      <TableHead
        component={Box}
        sx={{
          fontWeight: 'bold',
        }}
      >
        <TableRow component={Box}>
          <HeaderTableCell component={'h6'}>
            {t('transitProvider')}
          </HeaderTableCell>
          <HeaderTableCell component={'h6'}>{t('locations')}</HeaderTableCell>
          <HeaderTableCell component={'h6'}>
            {t('feedDescription')}
          </HeaderTableCell>
          <HeaderTableCell component={'h6'}>{t('dataType')}</HeaderTableCell>
        </TableRow>
      </TableHead>
      <TableBody
        component={Box}
        sx={{
          '.feed-row:first-of-type .feed-column:last-child': {
            borderTopRightRadius: '6px',
          },
          '.feed-row:first-of-type .feed-column:first-of-type': {
            borderTopLeftRadius: '6px',
          },
          '.feed-row:first-of-type .feed-column': {
            borderTop: `1px solid ${theme.palette.divider}`,
          },
          '.feed-row:last-child .feed-column:last-child': {
            borderBottomRightRadius: '6px',
          },
          '.feed-row:last-child .feed-column:first-of-type': {
            borderBottomLeftRadius: '6px',
          },
          '.feed-row:last-child .feed-column': {
            borderBottom: `1px solid ${theme.palette.divider}`,
          },
          '.feed-row .feed-column:first-of-type': {
            borderLeft: `1px solid ${theme.palette.divider}`,
          },
          '.feed-row .feed-column:last-child': {
            borderRight: `1px solid ${theme.palette.divider}`,
            minWidth: '210px',
          },
        }}
      >
        {feedsData?.results?.map((feed) => (
          <TableRow
            className='feed-row'
            component={Link}
            to={`/feeds/${feed.data_type}/${feed.id}`}
            key={feed.id}
            sx={{
              textDecoration: 'none',
              backgroundColor: theme.palette.background.default,
              '.feed-column': {
                fontSize: '16px',
                borderBottom: `1px solid ${theme.palette.divider}`,
              },
              '&:hover, &:focus': {
                backgroundColor: theme.palette.background.paper,
                cursor: 'pointer',
              },
            }}
          >
            <TableCell className='feed-column' component={Box}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                {getProviderElement(feed)}
                {feed.official === true && (
                  <Tooltip
                    title={t('officialFeedTooltipShort')}
                    placement='top'
                  >
                    <VerifiedIcon
                      sx={(theme) => ({
                        display: 'block',
                        borderRadius: '50%',
                        padding: '0.1rem',
                        ml: 1,
                        ...verificationBadgeStyle(theme),
                      })}
                    ></VerifiedIcon>
                  </Tooltip>
                )}
              </Box>
            </TableCell>
            <TableCell className='feed-column' component={Box}>
              {feed.locations != null && feed.locations.length > 1 ? (
                <>
                  {getCountryLocationSummaries(feed.locations).map(
                    (summary) => {
                      const tooltipText = `${summary.subdivisions.size} subdivisions and ${summary.municipalities.size} municipalities within ${summary.country}.`;

                      return (
                        <Tooltip
                          key={summary.country_code}
                          title={tooltipText}
                          arrow
                        >
                          <Chip
                            label={`${getEmojiFlag(
                              summary.country_code as TCountryCode,
                            )} ${summary.country}`}
                            size='medium'
                            sx={{ mr: 1, mt: 1 }}
                          />
                        </Tooltip>
                      );
                    },
                  )}
                </>
              ) : (
                <Chip
                  key={
                    feed.locations != null
                      ? feed.locations[0].country_code
                      : 'cc-key'
                  }
                  label={getLocationName(feed.locations)}
                  size='medium'
                  sx={{ mr: 1 }}
                />
              )}
            </TableCell>
            <TableCell className='feed-column' component={Box}>
              {feed.feed_name}
            </TableCell>
            <TableCell className='feed-column' component={Box}>
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
        <Popper
          open={providersPopoverData !== undefined}
          anchorEl={anchorEl}
          placement='top'
          sx={{
            backgroundColor: theme.palette.background.paper,
            boxShadow: '0px 1px 4px 2px rgba(0,0,0,0.2)',
            zIndex: 1000,
          }}
        >
          <Box
            sx={{
              padding: '10px',
              pb: 0,
              width: '400px',
              maxWidth: '100%',
            }}
          >
            <Typography variant='h6' sx={{ p: 0, fontSize: '16px' }}>
              {t('transitProvider')} - {providersPopoverData[0]}
            </Typography>
          </Box>

          <Box sx={{ fontSize: '14px', display: 'inline' }}>
            <ul>
              {providersPopoverData.slice(0, 10).map((provider) => (
                <li key={provider}>{provider}</li>
              ))}
              {providersPopoverData.length > 10 && (
                <li>
                  <b>
                    {t('seeDetailPageProviders', {
                      providersCount: providersPopoverData.length - 10,
                    })}
                  </b>
                </li>
              )}
            </ul>
          </Box>
        </Popper>
      )}
    </Table>
  );
}
