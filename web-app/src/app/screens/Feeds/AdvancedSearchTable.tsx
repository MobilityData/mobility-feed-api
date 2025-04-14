import {
  Box,
  Card,
  CardActionArea,
  Chip,
  type SxProps,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import {
  type AllFeedsType,
  getCountryLocationSummaries,
  getLocationName,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import * as React from 'react';
import { FeedStatusIndicator } from '../../components/FeedStatus';
import { useTranslation } from 'react-i18next';
import LockIcon from '@mui/icons-material/Lock';
import GtfsRtEntities from './GtfsRtEntities';
import { getEmojiFlag, type TCountryCode } from 'countries-list';
import OfficialChip from '../../components/OfficialChip';
import { getFeatureComponentDecorators } from '../../utils/consts';
import PopoverList from './PopoverList';
import ProviderTitle from './ProviderTitle';

// TODO: remove when features are fixed
const fakeFeatures = [
  'Route Colors',
  'Shapes',
  'Headsigns',
  'Feed Information',
  'Location Types',
  'Stops Wheelchair Accessibility',
  'Trips Wheelchair Accessibility',
  'Transfers',
  'Translations',
  'Fare Media',
  'Fare Products',
  'Levels',
  'Booking Rules',
  'Pathway Signs',
];

export interface AdvancedSearchTableProps {
  feedsData: AllFeedsType | undefined;
  selectedFeatures: string[] | undefined;
}

const renderGTFSDetails = (
  gtfsFeed: GTFSFeedType,
  selectedFeatures: string[],
): React.ReactElement => {
  const theme = useTheme();
  const number = Number(gtfsFeed?.id?.split('-')[1]) % 14;
  const displayFeatures = fakeFeatures.slice(0, number);
  return (
    <>
      <Typography variant='body1' sx={{ mb: 1 }}>
        {gtfsFeed?.feed_name}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {/* TODO: uncomment when features are fixed
        {gtfsFeed?.latest_dataset?.validation_report?.features?.map((feature: any, index: number) => (
                <Chip label={feature} key={index} size='small' variant='outlined' sx={{ mr: 1 }} />
        )} */}
        {displayFeatures.map((feature: string, index: number) => {
          const featureData = getFeatureComponentDecorators(feature);
          return (
            <Tooltip
              title={`Group: ${featureData.component}`}
              key={index}
              placement='top'
            >
              <Chip
                label={feature}
                key={index}
                size='small'
                sx={{
                  background: featureData.color,
                  border: selectedFeatures.includes(feature)
                    ? `2px solid ${theme.palette.primary.main}`
                    : 'none',
                  color: 'black',
                }}
              />
            </Tooltip>
          );
        })}
      </Box>
    </>
  );
};

const renderGTFSRTDetails = (gtfsRtFeed: GTFSRTFeedType): React.ReactElement => {
  return (
    <GtfsRtEntities
      entities={gtfsRtFeed?.entity_types}
      includeName={true}
    ></GtfsRtEntities>
  );
};

// TODO: Finalize with types and versions when GBFS endpoint is implemented
// const renderGBFSDetails = (gbfsFeed: any) => {
//   const fakeVersions = ['v3.0', 'v2.0', 'v1.0'];
//   return (
//     <>
//       {fakeVersions.map((version: string, index: number) => (
//         <Chip
//           label={version}
//           key={index}
//           size='small'
//           variant='outlined'
//           sx={{ mr: 1 }}
//         />
//       ))}
//     </>
//   );
// };

export default function AdvancedSearchTable({
  feedsData,
  selectedFeatures,
}: AdvancedSearchTableProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [popoverData, setPopoverData] = React.useState<string[] | undefined>(
    undefined,
  );
  const [popoverTitle, setPopoverTitle] = React.useState<string | undefined>();
  const theme = useTheme();

  const descriptionDividerStyle: SxProps = {
    py: 1,
    borderTop: `1px solid ${theme.palette.divider}`,
    mt: 1,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'baseline',
  };

  return (
    <>
      {feedsData?.results?.map((feed, index) => {
        if (feed == null) {
          return <></>;
        }
        return (
          <Card
            component={'a'}
            href={`/feeds/${feed.data_type}/${feed.id}`}
            key={index}
            sx={{
              my: 2,
              width: '100%',
              display: 'block',
              textDecoration: 'none',
              bgcolor: 'background.default',
            }}
          >
            <CardActionArea sx={{ p: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Typography variant='h6' sx={{ mr: 1, fontWeight: 'bold' }}>
                    <ProviderTitle
                      feed={feed}
                      setPopoverData={(popoverData) => {
                        setPopoverTitle(
                          `${t('transitProvider')} - ${popoverData?.[0]}`,
                        );
                        setPopoverData(popoverData);
                      }}
                      setAnchorEl={(el) => {
                        setAnchorEl(el);
                      }}
                    ></ProviderTitle>
                  </Typography>

                  {feed.official === true && (
                    <OfficialChip isLongDisplay={false}></OfficialChip>
                  )}
                  <FeedStatusIndicator
                    status={feed.status}
                  ></FeedStatusIndicator>
                </Box>

                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  {feed.source_info?.authentication_type !== 0 && (
                    <Tooltip
                      title={t('authenticationRequired')}
                      placement='top'
                    >
                      <LockIcon></LockIcon>
                    </Tooltip>
                  )}
                  <Typography
                    variant='body1'
                    sx={{ mr: 1, fontWeight: 'bold' }}
                  >
                    {t(`common:${feed.data_type}`)}
                  </Typography>
                </Box>
              </Box>
              <Box>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  {feed.locations != null && feed.locations?.length > 1 ? (
                    <>
                      {getCountryLocationSummaries(feed.locations).map(
                        (location, index) => {
                          const locationForCountry = feed.locations?.filter(
                            (l) => l.country_code === location.country_code,
                          );
                          return (
                            <Box
                              key={index}
                              sx={{ display: 'flex', alignItems: 'center' }}
                            >
                              <Typography>
                                {getEmojiFlag(
                                  location.country_code as TCountryCode,
                                )}{' '}
                                {location.country}
                              </Typography>
                              <Typography
                                sx={{
                                  fontStyle: 'italic',
                                  mr: 1,
                                  fontWeight: 'bold'
                                }}
                                variant='caption'
                                onMouseEnter={(event) => {
                                  setPopoverData(
                                    locationForCountry?.map(
                                      (l) =>
                                        `${l.municipality}, (${l.subdivision_name})`,
                                    ),
                                  );
                                  setAnchorEl(event.currentTarget);
                                  setPopoverTitle(location.country);
                                }}
                                onMouseLeave={() => {
                                  setPopoverData(undefined);
                                  setAnchorEl(null);
                                  setPopoverTitle(undefined);
                                }}
                              >
                                &nbsp;(
                                {locationForCountry?.length})
                              </Typography>
                            </Box>
                          );
                        },
                      )}
                    </>
                  ) : (
                    <Typography variant='body1'>
                      {getLocationName(feed.locations)}
                    </Typography>
                  )}
                </Box>
              </Box>
              <Box>
                {feed.data_type === 'gtfs' && (
                  <Box
                    sx={
                      // TODO: address : feed.latest_dataset?.validation_report?.features.length > 0
                      3 > 2 ? descriptionDividerStyle : {}
                    }
                  >
                    {renderGTFSDetails(
                      feed as GTFSFeedType,
                      selectedFeatures ?? [],
                    )}
                  </Box>
                )}
                {feed.data_type === 'gtfs_rt' && (
                  <Box sx={descriptionDividerStyle}>
                    {renderGTFSRTDetails(feed as GTFSRTFeedType)}
                  </Box>
                )}
                {/*
              TODO: uncomment when GBFS option is available
              {feed.data_type === ('gbfs' as any) && (
                <Box>{renderGBFSDetails(feed)}</Box>
              )} */}
              </Box>
            </CardActionArea>
          </Card>
        );
      })}
      {popoverData !== undefined && (
        <PopoverList
          popoverData={popoverData}
          anchorEl={anchorEl}
          title={popoverTitle ?? ''}
        ></PopoverList>
      )}
    </>
  );
}
