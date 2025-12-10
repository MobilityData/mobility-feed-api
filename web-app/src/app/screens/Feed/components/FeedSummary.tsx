import { useMemo, useState } from 'react';
import { type components } from '../../../services/feeds/types';
import LicenseDialog from './LicenseDialog';
import {
  getCountryLocationSummaries,
  getLocationName,
  type GTFSFeedType,
  type GTFSRTFeedType,
  type GBFSFeedType,
} from '../../../services/feeds/utils';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  Grid,
  IconButton,
  Link,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { GroupCard, GroupHeader } from '../FeedSummary.styles';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import LayersIcon from '@mui/icons-material/Layers';
import EmailIcon from '@mui/icons-material/Email';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import LockIcon from '@mui/icons-material/Lock';
import DownloadIcon from '@mui/icons-material/Download';
import CloseIcon from '@mui/icons-material/Close';
import BusinessIcon from '@mui/icons-material/Business';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { FeedStatusChip } from '../../../components/FeedStatus';
import { getEmojiFlag, type TCountryCode } from 'countries-list';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import GavelIcon from '@mui/icons-material/Gavel';
import { getFeedStatusData } from '../../../utils/feedStatusConsts';
import { useSelector } from 'react-redux';
import { Link as RouterLink } from 'react-router-dom';
import ReactGA from 'react-ga4';
import {
  selectGtfsDatasetRoutesTotal,
  selectGtfsDatasetRouteTypes,
} from '../../../store/supporting-files-selectors';
import { getRouteTypeTranslatedName } from '../../../constants/RouteTypes';
import {
  featureChipsStyle,
  ResponsiveListItem,
  StyledListItem,
} from '../Feed.styles';
import { getFeatureComponentDecorators } from '../../../utils/consts';
import Locations from '../../../components/Locations';
import CopyLinkElement from './CopyLinkElement';
import { formatDateShort } from '../../../utils/date';
import ExternalIds from './ExternalIds';

export interface FeedSummaryProps {
  feed: GTFSFeedType | GTFSRTFeedType | GBFSFeedType | undefined;
  sortedProviders: string[];
  latestDataset?: components['schemas']['GtfsDataset'] | undefined;
  autoDiscoveryUrl?: string;
}

export default function FeedSummary({
  feed,
  sortedProviders,
  latestDataset,
  autoDiscoveryUrl,
}: FeedSummaryProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const theme = useTheme();
  const [openLocationDetails, setOpenLocationDetails] = useState<
    'summary' | 'fullList' | undefined
  >(undefined);
  const [openProvidersDetails, setOpenProvidersDetails] = useState(false);
  const [openLicenseDetails, setOpenLicenseDetails] = useState(false);
  const [showAllFeatures, setShowAllFeatures] = useState(false);

  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const totalRoutes = useSelector(selectGtfsDatasetRoutesTotal);
  const routeTypes = useSelector(selectGtfsDatasetRouteTypes);

  const uniqueCountries = useMemo(() => {
    return getCountryLocationSummaries(feed?.locations ?? []).map(
      (country) =>
        `${getEmojiFlag(country.country_code as TCountryCode)} ${
          country.country ?? ''
        }`,
    );
  }, [feed]);

  const handleOpenDetailedMapClick = (): void => {
    ReactGA.event({
      category: 'engagement',
      action: 'gtfs_visualization_open_detailed_map',
      label: 'Open Detailed Map',
    });
  };

  const hasRelatedLinks = (): boolean => {
    const relatedLinks = (feed as GTFSFeedType)?.related_links;
    const hasOtherLinks = relatedLinks != null && relatedLinks?.length > 0;
    return hasOtherLinks;
  };

  const hasLicenseData = (): boolean => {
    return (
      feed?.source_info?.license_url != undefined &&
      feed?.source_info?.license_url !== ''
    );
  };

  return (
    <>
      <GroupCard variant='outlined'>
        <GroupHeader variant='body1'>
          <BusinessIcon fontSize='inherit' />
          {feed?.data_type === 'gbfs' ? 'Producer' : 'Agency'}
        </GroupHeader>
        <Box sx={{ ml: 2 }}>
          <Typography variant='h6' fontWeight={700} mt={1} mb={0.5}>
            {sortedProviders.length > 0
              ? sortedProviders.slice(0, 4).join(', ')
              : t('noAgencyProvided')}
            {sortedProviders.length > 4 && (
              <Typography component='span' variant='subtitle2' sx={{ ml: 1 }}>
                and more
              </Typography>
            )}
          </Typography>
          {sortedProviders.length > 4 && (
            <Button
              variant='text'
              size='small'
              onClick={() => {
                setOpenProvidersDetails(true);
              }}
              sx={{ pl: 0 }}
            >
              View All {sortedProviders.length} Agencies
            </Button>
          )}

          {latestDataset?.agency_timezone != undefined && (
            <Tooltip title='Agency Timezone' placement='top'>
              <Typography
                variant='body2'
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  width: 'fit-content',
                }}
              >
                <>
                  <AccessTimeIcon fontSize='inherit' sx={{ mr: 1 }} />
                  {latestDataset.agency_timezone}
                </>
              </Typography>
            </Tooltip>
          )}

          {feed?.external_ids != null && feed.external_ids.length > 0 && (
            <ExternalIds externalIds={feed.external_ids} />
          )}
        </Box>
      </GroupCard>

      <GroupCard variant='outlined'>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1,
          }}
        >
          <GroupHeader variant='body1' sx={{ mb: 0 }}>
            <DatasetIcon fontSize='inherit' />
            Feed Details
          </GroupHeader>
          <Chip
            data-testid='data-type'
            size='small'
            label={t('common:' + feed?.data_type)}
            color='secondary'
          ></Chip>
        </Box>

        <Box sx={{ ml: 2, mt: 2, mr: 2 }}>
          <Typography
            variant='subtitle2'
            sx={{ fontWeight: 700, color: 'text.secondary' }}
          >
            Locations
          </Typography>
          <Box
            sx={{
              mb: 2,
              borderBottom: '1px solid',
              borderColor: 'divider',
              pb: 1,
            }}
          >
            <Box
              data-testid='location'
              sx={{
                mt: 0.5,
                mb: 0,
                display: 'flex',
                flexWrap: 'wrap',
              }}
            >
              {feed?.locations != null && feed?.locations?.length === 1 && (
                <Typography
                  variant='h6'
                  sx={{ whiteSpace: 'nowrap', fontWeight: 700, mr: 1, mb: 0 }}
                >
                  {getLocationName(feed?.locations)}
                </Typography>
              )}

              {feed?.locations != null &&
                feed?.locations?.length > 1 &&
                uniqueCountries.slice(0, 4).map((country, index) => (
                  <Typography
                    variant='h6'
                    component={'span'}
                    key={index}
                    sx={{ whiteSpace: 'nowrap', fontWeight: 700, mr: 1, mb: 0 }}
                  >
                    {country}
                    {index < 3 && index !== uniqueCountries.length - 1 && ', '}
                    {uniqueCountries.length > 4 && index === 3 && (
                      <Button
                        variant='text'
                        color='secondary'
                        size='small'
                        sx={{ ml: 1 }}
                        onClick={() => {
                          setOpenLocationDetails('summary');
                        }}
                      >
                        + {uniqueCountries.length - 4} more
                      </Button>
                    )}
                  </Typography>
                ))}
            </Box>

            {feed?.locations?.length != null && feed.locations.length > 1 && (
              <Button
                variant='text'
                color='secondary'
                size='small'
                onClick={() => {
                  setOpenLocationDetails('fullList');
                }}
                sx={{ height: 'fit-content', mt: 0.5, ml: '-5px' }}
              >
                Show Details ({feed?.locations?.length} Locations)
              </Button>
            )}
          </Box>

          {totalRoutes != undefined && routeTypes != undefined && (
            <>
              <Typography
                variant='subtitle2'
                sx={{ fontWeight: 700, color: 'text.secondary' }}
              >
                Routes
              </Typography>
              <Box
                sx={{
                  mb: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider',
                  pb: 1,
                }}
              >
                <Box sx={{ display: 'flex', flexWrap: 'wrap', mt: 0.5 }}>
                  {routeTypes?.map((routeType, index) => {
                    return (
                      <Box
                        key={routeType}
                        sx={{
                          whiteSpace: 'nowrap',
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        <Typography
                          component={'span'}
                          variant='h6'
                          sx={{ fontWeight: 700, mr: 0.5 }}
                        >
                          {getRouteTypeTranslatedName(routeType, t)}
                          {index < routeTypes.length - 1 ? ',' : ''}
                        </Typography>
                      </Box>
                    );
                  })}
                </Box>
                <Box sx={{ width: '100%', mt: 0.5 }}>
                  <Typography variant='body1'>{totalRoutes} routes</Typography>
                </Box>

                <Button
                  variant='text'
                  color='secondary'
                  size='small'
                  sx={{ height: 'fit-content', mt: 0.5, ml: '-5px' }}
                  component={RouterLink}
                  to='./map'
                  onClick={handleOpenDetailedMapClick}
                >
                  View On Map
                </Button>
              </Box>
            </>
          )}
        </Box>
        {feed?.source_info?.producer_url != undefined &&
          feed?.source_info?.producer_url !== '' && (
            <>
              <Box sx={{ ml: 2 }}>
                <Typography
                  variant='subtitle2'
                  sx={{ fontWeight: 700, color: 'text.secondary' }}
                >
                  {feed?.data_type === 'gbfs' && autoDiscoveryUrl != undefined
                    ? 'Auto-Discovery URL'
                    : 'Producer URL'}
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mr: 2,
                    mt: 0.5,
                  }}
                >
                  <Typography
                    data-testid='producer-url'
                    tabIndex={0}
                    variant='body1'
                    sx={{
                      maxWidth: 'calc(100% - 50px)',
                      width: '100%',
                      whiteSpace: 'nowrap',
                      overflowX: 'auto',
                      borderRadius: '5px',
                      backgroundColor: theme.palette.secondary.light,
                      color: theme.palette.text.lightContrast,
                      py: 1.5,
                      px: 2,
                      fontSize: '0.875em',
                    }}
                  >
                    {feed.data_type === 'gbfs'
                      ? autoDiscoveryUrl
                      : feed.source_info.producer_url}
                  </Typography>
                  <IconButton
                    component={Link}
                    href={
                      feed.data_type === 'gbfs'
                        ? autoDiscoveryUrl
                        : feed.source_info.producer_url
                    }
                    target='_blank'
                    rel='noreferrer'
                    color='secondary'
                    aria-label='download producer URL'
                  >
                    {feed.data_type === 'gbfs' ? (
                      <OpenInNewIcon />
                    ) : (
                      <DownloadIcon />
                    )}
                  </IconButton>
                </Box>
              </Box>
            </>
          )}

        {(feed as GBFSFeedType)?.provider_url != undefined &&
          (feed as GBFSFeedType)?.provider_url !== '' && (
            <>
              <Box sx={{ ml: 2, mt: 2 }}>
                <Typography
                  variant='subtitle2'
                  sx={{ fontWeight: 700, color: 'text.secondary' }}
                >
                  Provider Url
                </Typography>
                <Link
                  href={(feed as GBFSFeedType)?.provider_url}
                  target='_blank'
                  rel='noreferrer'
                  variant='body1'
                >
                  {(feed as GBFSFeedType)?.provider_url}
                </Link>
              </Box>
            </>
          )}
        {(feed as GBFSFeedType)?.system_id != undefined && (
          <Box sx={{ ml: 2, mt: 2 }}>
            <Typography
              variant='subtitle2'
              sx={{ fontWeight: 700, color: 'text.secondary' }}
            >
              System ID
            </Typography>
            <Typography variant='body1'>
              {(feed as GBFSFeedType)?.system_id}
            </Typography>
          </Box>
        )}
        {feed?.feed_contact_email != null &&
          feed?.feed_contact_email !== '' && (
            <Box sx={{ ml: 2, mt: 3 }}>
              <Typography
                variant='subtitle2'
                sx={{ fontWeight: 700, color: 'text.secondary' }}
              >
                Feed Contact Email
              </Typography>
              <Button
                sx={{ mt: 0.5 }}
                variant='outlined'
                color='secondary'
                size='small'
                startIcon={<EmailIcon />}
                component={Link}
                href={`mailto:${feed?.feed_contact_email}`}
              >
                {feed?.feed_contact_email}
              </Button>
            </Box>
          )}
      </GroupCard>

      {feed?.source_info?.authentication_info_url != undefined &&
        feed.source_info.authentication_type !== 0 &&
        feed?.source_info.authentication_info_url.trim() !== '' && (
          <GroupCard variant='outlined'>
            <GroupHeader variant='body1'>
              <LockIcon fontSize='inherit' />
              Feed Authentication
            </GroupHeader>
            <Box sx={{ ml: 2 }}>
              <Typography variant='h6' sx={{ fontWeight: 700 }}>
                {feed?.source_info?.authentication_type === 1 &&
                  t('common:apiKey')}
                {feed?.source_info?.authentication_type === 2 &&
                  t('common:httpHeader')}
              </Typography>
              {feed?.source_info?.authentication_info_url != undefined && (
                <Button
                  disableElevation
                  variant='text'
                  size='small'
                  href={feed?.source_info?.authentication_info_url}
                  target='_blank'
                  rel='noreferrer'
                  endIcon={<OpenInNewIcon />}
                  sx={{ pl: 0 }}
                >
                  {t('registerToDownloadFeed')}
                </Button>
              )}
            </Box>
          </GroupCard>
        )}

      {latestDataset?.service_date_range_start != undefined &&
        latestDataset.service_date_range_end != undefined && (
          <GroupCard variant='outlined'>
            <GroupHeader variant='body1'>
              <CalendarTodayIcon fontSize='inherit' />
              Service Date Range
              <Tooltip title={t('serviceDateRangeTooltip')} placement='top'>
                <IconButton size='small'>
                  <InfoOutlinedIcon fontSize='inherit' />
                </IconButton>
              </Tooltip>
            </GroupHeader>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 1,
                mt: 1,
                mx: 2,
              }}
            >
              <Box>
                <Typography variant='subtitle2' sx={{ lineHeight: 1.5 }}>
                  Start
                </Typography>
                <Typography variant='body1' sx={{ fontWeight: 700 }}>
                  {formatDateShort(
                    latestDataset.service_date_range_start,
                    latestDataset.agency_timezone,
                  )}
                </Typography>
              </Box>
              <Tooltip
                title={
                  getFeedStatusData(
                    (feed as GTFSFeedType)?.status ?? '',
                    theme,
                    t,
                  )?.toolTipLong ?? ''
                }
                placement='top'
              >
                <Box
                  sx={{
                    height: '30px',
                    flexGrow: 1,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <Box
                    position={'relative'}
                    sx={{
                      height: '1px',
                      width: '100%',
                      background: `radial-gradient(circle,${getFeedStatusData(
                        (feed as GTFSFeedType)?.status ?? '',
                        theme,
                        t,
                      )?.color} 54%, rgba(255, 255, 255, 0) 100%)`,
                    }}
                  >
                    {/* TODO: nice to have, a placement of the chip relative to the current date */}
                    {(feed as GTFSFeedType)?.status !== undefined &&
                      (feed as GTFSFeedType)?.status === 'active' && (
                        <Box
                          sx={{
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                          }}
                        >
                          <FeedStatusChip
                            status={(feed as GTFSFeedType)?.status ?? ''}
                            chipSize='small'
                            disableTooltip={true}
                          />
                        </Box>
                      )}
                  </Box>
                </Box>
              </Tooltip>

              <Box>
                <Typography variant='subtitle2' sx={{ lineHeight: 1.5 }}>
                  End
                </Typography>
                <Typography variant='body1' sx={{ fontWeight: 700 }}>
                  {formatDateShort(
                    latestDataset.service_date_range_end,
                    latestDataset.agency_timezone,
                  )}
                </Typography>
              </Box>
            </Box>
          </GroupCard>
        )}

      {latestDataset?.validation_report?.features != undefined &&
        latestDataset?.validation_report?.features.length > 0 && (
          <GroupCard variant='outlined'>
            <GroupHeader variant='body1'>
              <LayersIcon fontSize='inherit' />
              Features
              <Tooltip title='More Info' placement='top'>
                <IconButton
                  href='https://gtfs.org/getting_started/features/overview/'
                  target='_blank'
                  rel='noopener noreferrer'
                  size='small'
                >
                  <OpenInNewIcon fontSize='inherit' />
                </IconButton>
              </Tooltip>
            </GroupHeader>
            {(() => {
              const allFeatures =
                latestDataset?.validation_report?.features ?? [];
              const visible = showAllFeatures
                ? allFeatures
                : allFeatures.slice(0, 6);
              return (
                <>
                  <Grid container spacing={1} mt={1}>
                    {visible.map((feature, index) => {
                      const featureDecorators =
                        getFeatureComponentDecorators(feature);
                      return (
                        <Grid item key={feature} data-testid='feature-chips'>
                          <Tooltip
                            title={`Group: ${featureDecorators.component}`}
                            key={index}
                            placement='top'
                          >
                            <Chip
                              size='small'
                              component={Link}
                              label={feature}
                              variant='filled'
                              sx={{
                                ...featureChipsStyle,
                                fontWeight: 500,
                                background: featureDecorators.color,
                                color: 'initial',
                              }}
                              clickable
                              target='_blank'
                              rel='noreferrer'
                              href={featureDecorators?.linkToInfo}
                            />
                          </Tooltip>
                        </Grid>
                      );
                    })}
                    {allFeatures.length > 6 && (
                      <Box sx={{ mt: 1 }}>
                        <Button
                          variant='text'
                          color='secondary'
                          size='small'
                          onClick={() => {
                            setShowAllFeatures((v) => !v);
                          }}
                          sx={{ ml: 1 }}
                        >
                          {showAllFeatures
                            ? 'Show less'
                            : `Show ${allFeatures.length - 6} more`}
                        </Button>
                      </Box>
                    )}
                  </Grid>
                </>
              );
            })()}
          </GroupCard>
        )}

      {hasLicenseData() && (
        <GroupCard variant='outlined'>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              mb: 1,
            }}
          >
            <GroupHeader variant='body1' sx={{ mb: 0 }}>
              <GavelIcon fontSize='inherit' />
              License
            </GroupHeader>
            {feed?.source_info?.license_is_spdx != undefined &&
              feed.source_info.license_is_spdx && (
                <Tooltip
                  title='The Software Package Data Exchange (SPDX) is an open standard for communicating software bill of material information, including licenses.'
                  placement='top'
                >
                  <Chip
                    label='SPDX'
                    size='small'
                    color='info'
                    variant='outlined'
                  />
                </Tooltip>
              )}
          </Box>

          {feed?.source_info?.license_id != undefined &&
          feed.source_info.license_id != '' ? (
            <CopyLinkElement
              title={feed.source_info.license_id}
              url={feed.source_info.license_url ?? ''}
              titleInfo='License was added by the Mobility Database team based on either 1) a submission authorized by the transit provider 2) review of the transit providers website.'
              linkType='internal'
              internalClickAction={() => {
                setOpenLicenseDetails(true);
              }}
            />
          ) : (
            <Link
              href={feed?.source_info?.license_url ?? ''}
              target='_blank'
              rel='noopener noreferrer'
              sx={{ wordBreak: 'break-word' }}
              variant='body1'
            >
              {feed?.source_info?.license_url}
            </Link>
          )}
        </GroupCard>
      )}

      {hasRelatedLinks() && (
        <GroupCard variant='outlined'>
          <GroupHeader variant='body1'>
            <LinkIcon fontSize='inherit' />
            Related Links
          </GroupHeader>

          {(feed as GTFSFeedType)?.related_links?.map((link, index) => (
            <CopyLinkElement
              key={index}
              title={link.code ?? ''}
              url={link.url ?? ''}
              linkType='download'
              titleInfo={link.description ?? undefined}
            />
          ))}
        </GroupCard>
      )}

      <Dialog
        fullScreen={fullScreen}
        maxWidth='md'
        fullWidth
        onClose={() => {
          setOpenLocationDetails(undefined);
        }}
        open={openLocationDetails !== undefined}
      >
        <DialogTitle>Feed Locations</DialogTitle>
        <IconButton
          aria-label='close'
          onClick={() => {
            setOpenLocationDetails(undefined);
          }}
          sx={() => ({
            position: 'absolute',
            right: 8,
            top: 8,
          })}
        >
          <CloseIcon />
        </IconButton>
        {feed?.locations != null && (
          <Locations
            locations={feed?.locations}
            startingTab={openLocationDetails}
          />
        )}
      </Dialog>

      <Dialog
        fullScreen={fullScreen}
        maxWidth='md'
        fullWidth
        onClose={() => {
          setOpenProvidersDetails(false);
        }}
        open={openProvidersDetails}
      >
        <DialogTitle>Agencies</DialogTitle>
        <IconButton
          aria-label='close'
          onClick={() => {
            setOpenProvidersDetails(false);
          }}
          sx={() => ({
            position: 'absolute',
            right: 8,
            top: 8,
          })}
        >
          <CloseIcon />
        </IconButton>
        <Box sx={{ px: 2 }}>
          <ul
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              maxHeight: '500px',
              overflowY: 'auto',
            }}
          >
            {sortedProviders.map((provider) =>
              sortedProviders.length <= 1 ? (
                <StyledListItem key={provider}>{provider}</StyledListItem>
              ) : (
                <ResponsiveListItem key={provider}>
                  {provider}
                </ResponsiveListItem>
              ),
            )}
          </ul>
        </Box>
      </Dialog>
      <LicenseDialog
        open={openLicenseDetails}
        onClose={() => {
          setOpenLicenseDetails(false);
        }}
        licenseId={feed?.source_info?.license_id}
      />
    </>
  );
}
