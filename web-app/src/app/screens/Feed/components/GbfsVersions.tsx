'use client';

import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Link,
  Snackbar,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import { useTranslations } from 'next-intl';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {
  type GBFSVersionEndpointType,
  type GBFSFeedType,
  type GBFSVersionType,
} from '../../../services/feeds/utils';
import { displayFormattedDate } from '../../../utils/date';
import { featureChipsStyle } from '../Feed.styles';
import { sortGbfsVersions } from '../Feed.functions';
import { WarningContentBox } from '../../../components/WarningContentBox';

export interface GbfsVersionsProps {
  feed: GBFSFeedType;
}

// gbfs endpoints need to be filtered if they are not features
// and this function will return only the features of the language with the most features
export const getGbfsFeatures = (
  gbfsVersionElement: GBFSVersionType,
): GBFSVersionEndpointType[] => {
  const featuresByLanguage = new Map<string, GBFSVersionEndpointType[]>();
  let maxLanguageElements = 0;
  let maxLanguage = 'no-lang';
  gbfsVersionElement.endpoints?.forEach((endpoint) => {
    if (endpoint.name != null && endpoint.is_feature === true) {
      if (!featuresByLanguage.has(endpoint.language ?? 'no-lang')) {
        featuresByLanguage.set(endpoint.language ?? 'no-lang', []);
      }
      featuresByLanguage.get(endpoint.language ?? 'no-lang')?.push(endpoint);
      if (
        (featuresByLanguage.get(endpoint.language ?? 'no-lang')?.length ?? 0) >
        maxLanguageElements
      ) {
        maxLanguageElements =
          featuresByLanguage.get(endpoint.language ?? 'no-lang')?.length ?? 0;
        maxLanguage = endpoint.language ?? 'no-lang';
      }
    }
  });
  return featuresByLanguage.get(maxLanguage) ?? [];
};

export default function GbfsVersions({
  feed,
}: GbfsVersionsProps): React.ReactElement {
  const [snackbarOpen, setSnackbarOpen] = React.useState(false);
  const theme = useTheme();
  const t = useTranslations('gbfs');

  const getGbfsVersionUrl = (version: string, feature: string): string => {
    if (
      version === '1.1' ||
      version === '2.0' ||
      version === '2.1' ||
      version === '2.2'
    ) {
      switch (feature) {
        case 'gbfs_versions':
          return `https://github.com/MobilityData/gbfs/blob/v${version}/gbfs.md#gbfs_versionsjson-added-in-v11`;
        case 'vehicle_types':
          return `https://github.com/MobilityData/gbfs/blob/v${version}/gbfs.md#vehicle_typesjson-added-in-v21`;
        case 'geofencing_zones':
          return `https://github.com/MobilityData/gbfs/blob/v${version}/gbfs.md#geofencing_zonesjson-added-in-v21`;
      }
    }
    return `https://github.com/MobilityData/gbfs/blob/v${version}/gbfs.md#${feature}json`;
  };

  const sortedVersions = [...(feed?.versions ?? [])].sort(sortGbfsVersions);

  return (
    <>
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        {t('versions')}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: 3,
          justifyContent: 'flex-end',
        }}
      >
        {feed?.versions == null ||
          (feed.versions.length === 0 && (
            <WarningContentBox>{t('unableToDetectVersions')}</WarningContentBox>
          ))}
        {sortedVersions.map((item, index) => {
          const autoDiscoveryUrl = item.endpoints?.find(
            (endpoint) => endpoint.name === 'gbfs',
          )?.url;
          return (
            <ContentBox
              key={index}
              title={``}
              outlineColor={theme.palette.secondary.main}
              padding={2}
              sx={{
                my: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
              width={{ xs: '100%' }}
            >
              <Box>
                <Box>
                  <Typography
                    variant='h5'
                    sx={{
                      mb: 1,
                      fontWeight: 'bold',
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      gap: 2,
                    }}
                  >
                    v{item.version}
                    {item.source === 'gbfs_versions' && (
                      <Tooltip title={t('feedVersionTooltip')} placement='top'>
                        <Chip
                          label={t('gbfsVersionsJson')}
                          sx={{
                            backgroundColor: theme.palette.primary.dark,
                            color: theme.palette.secondary.contrastText,
                          }}
                          variant='filled'
                        ></Chip>
                      </Tooltip>
                    )}
                    <Chip
                      icon={
                        item.latest_validation_report?.total_error === 0 ? (
                          <CheckCircleIcon />
                        ) : (
                          <ErrorIcon />
                        )
                      }
                      label={
                        item.latest_validation_report?.total_error != null &&
                        item.latest_validation_report?.total_error > 0
                          ? `${item.latest_validation_report?.total_error} ${t(
                              'common:feedback.errors',
                            )}`
                          : t('common:feedback.noErrors')
                      }
                      variant='outlined'
                      color={
                        item.latest_validation_report?.total_error != null &&
                        item.latest_validation_report?.total_error > 0
                          ? 'error'
                          : 'success'
                      }
                      clickable
                      component={Link}
                      href={item.latest_validation_report?.report_summary_url}
                      target='_blank'
                      rel='noreferrer'
                    />
                  </Typography>
                  <Typography
                    variant='caption'
                    component={'div'}
                    sx={{ mt: '-2px', mb: 2 }}
                  >
                    {t('feeds:qualityReportUpdated')}
                    {': '}
                    {displayFormattedDate(
                      item.latest_validation_report?.validated_at ?? '',
                    )}
                  </Typography>
                  <Typography variant='h6' sx={{ fontSize: '1.1rem' }}>
                    {t('feedUrl')}
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      mb: 2,
                    }}
                  >
                    {autoDiscoveryUrl != null && (
                      <>
                        <Link
                          sx={{
                            wordWrap: 'break-word',
                            wordBreak: 'break-all',
                          }}
                          href={autoDiscoveryUrl}
                          target='_blank'
                          rel='noreferrer'
                        >
                          {autoDiscoveryUrl}
                        </Link>
                        <ContentCopyIcon
                          titleAccess={t('feedUrlCopied')}
                          sx={{ cursor: 'pointer', ml: 1 }}
                          onClick={() => {
                            if (feed?.source_info?.producer_url !== undefined) {
                              setSnackbarOpen(true);
                              void navigator.clipboard
                                .writeText(autoDiscoveryUrl)
                                .then((value) => {});
                            }
                          }}
                        ></ContentCopyIcon>
                      </>
                    )}
                    <Snackbar
                      anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
                      open={snackbarOpen}
                      autoHideDuration={5000}
                      onClose={() => {
                        setSnackbarOpen(false);
                      }}
                      message={t('feedUrlCopied')}
                    />
                  </Box>
                  <Box>
                    <Typography variant='h6' sx={{ mt: 1, fontSize: '1.1rem' }}>
                      {t('feeds:features')}
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1,
                        mt: 1,
                      }}
                    >
                      {getGbfsFeatures(item).map((endpoint, index) => (
                        <Box key={index}>
                          {endpoint.name != null && item.version != null && (
                            <Chip
                              component={Link}
                              label={t('features.' + endpoint.name)}
                              color='info'
                              variant='filled'
                              sx={featureChipsStyle}
                              clickable
                              target='_blank'
                              rel='noreferrer'
                              href={getGbfsVersionUrl(
                                item.version,
                                endpoint.name,
                              )}
                            />
                          )}
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </Box>
              </Box>
              {autoDiscoveryUrl != null && (
                <Box
                  sx={{
                    width: '100%',
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 2,
                    mt: 3,
                  }}
                >
                  <Button
                    variant='text'
                    color='primary'
                    href={`https://gbfs-validator.mobilitydata.org/validator?url=${autoDiscoveryUrl}`}
                    target='_blank'
                    rel='noreferrer'
                    endIcon={<OpenInNewIcon></OpenInNewIcon>}
                  >
                    {t('runValidationReport')}
                  </Button>
                  <Button
                    variant='contained'
                    color='primary'
                    href={autoDiscoveryUrl}
                    target='_blank'
                    rel='noreferrer'
                    endIcon={<OpenInNewIcon></OpenInNewIcon>}
                  >
                    {item.source === 'autodiscovery'
                      ? t('openAutoDiscoveryUrl')
                      : t('openFeedUrl')}
                  </Button>
                </Box>
              )}
            </ContentBox>
          );
        })}
      </Box>
    </>
  );
}
