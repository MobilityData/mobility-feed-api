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
  type AllFeedsType,
  getLocationName,
  getCountryLocationSummaries,
} from '../../services/feeds/utils';
import { useTranslations } from 'next-intl';
import GtfsRtEntities from './GtfsRtEntities';
import { Link } from 'react-router-dom';
import { getEmojiFlag, type TCountryCode } from 'countries-list';
import OfficialChip from '../../components/OfficialChip';
import ProviderTitle from './ProviderTitle';

export interface SearchTableProps {
  feedsData: AllFeedsType | undefined;
}

const HeaderTableCell = styled(TableCell)(() => ({
  fontWeight: 'bold',
  fontSize: '18px',
  border: 'none',
}));

export const getDataTypeElement = (
  dataType: 'gtfs' | 'gtfs_rt' | 'gbfs',
): JSX.Element => {
  const t = useTranslations('feeds');
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
    return <DataTypeHolder>{t('common:gtfsSchedule')}</DataTypeHolder>;
  } else if (dataType === 'gtfs_rt') {
    return <DataTypeHolder>{t('common:gtfsRealtime')}</DataTypeHolder>;
  } else {
    return <DataTypeHolder>{t('common:gbfs')}</DataTypeHolder>;
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
  const t = useTranslations('feeds');
  if (feedsData === undefined) return <></>;

  // Reason for all component overrite is for SEO purposes.
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
            minWidth: '180px',
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
                <ProviderTitle
                  feed={feed}
                  setPopoverData={(popoverData) => {
                    setProvidersPopoverData(popoverData);
                  }}
                  setAnchorEl={(el) => {
                    setAnchorEl(el);
                  }}
                ></ProviderTitle>
                {feed.official === true && (
                  <OfficialChip isLongDisplay={false}></OfficialChip>
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
                <>
                  {feed.locations?.[0] != null && (
                    <Chip
                      key={
                        feed.locations?.[0] != null
                          ? feed.locations[0].country_code
                          : 'cc-key'
                      }
                      label={getLocationName(feed.locations)}
                      size='medium'
                      sx={{ mr: 1 }}
                    />
                  )}
                </>
              )}
            </TableCell>
            <TableCell className='feed-column' component={Box}>
              {feed.feed_name}
            </TableCell>
            <TableCell className='feed-column' component={Box}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
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
            boxShadow: theme.palette.boxShadow,
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
