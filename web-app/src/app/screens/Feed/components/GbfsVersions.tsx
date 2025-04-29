import * as React from 'react';
import { ContentBox } from '../../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Link,
  Snackbar,
  Typography,
  useTheme,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
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

export const sortVersions = (
  a: GBFSVersionType,
  b: GBFSVersionType,
): number => {
  const na = parseFloat(String(a.version ?? '0').replace(/[^0-9.]/g, ''));
  const nb = parseFloat(String(b.version ?? '0').replace(/[^0-9.]/g, ''));
  if (Number.isNaN(na) || Number.isNaN(nb)) {
    return -1;
  }
  return nb - na;
};

export default function GbfsVersions({
  feed,
}: GbfsVersionsProps): React.ReactElement {
  const [snackbarOpen, setSnackbarOpen] = React.useState(false);
  const theme = useTheme();
  const { t } = useTranslation('gbfs');

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

  if (feed?.versions == null || feed?.versions?.length === 0) {
    return <></>;
  }

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
        {[...(feed?.versions ?? [])]
          .sort((a, b) => sortVersions(a, b))
          .map((item, index) => (
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
                      alignItems: 'center',
                    }}
                  >
                    v{item.version}
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
                      sx={{ ml: 2 }}
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
                    <Link
                      sx={{ wordWrap: 'break-word', wordBreak: 'break-all' }}
                      href='https://data.lime.bike/api/partners/v2/gbfs/louisville/gbfs.json'
                      target='_blank'
                      rel='noreferrer'
                    >
                      https://data.lime.bike/api/partners/v2/gbfs/louisville/gbfs.json
                    </Link>
                    {/* TODO: href={item.autoDiscovery}{item.autoDiscovery} */}
                    <ContentCopyIcon
                      titleAccess={t('feedUrlCopied')}
                      sx={{ cursor: 'pointer', ml: 1 }}
                      onClick={() => {
                        if (feed?.source_info?.producer_url !== undefined) {
                          setSnackbarOpen(true);
                          void navigator.clipboard
                            .writeText(
                              'https://data.lime.bike/api/partners/v2/gbfs/louisville/gbfs.json',
                            )
                            .then((value) => {});
                        }
                      }}
                    ></ContentCopyIcon>
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
                      sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}
                    >
                      {getGbfsFeatures(item).map((endpoint, index) => (
                        <>
                          {endpoint.name != null && item.version != null && (
                            <Chip
                              component={Link}
                              key={index}
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
                        </>
                      ))}
                    </Box>
                  </Box>
                </Box>
              </Box>
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
                  href={''} // TODO: `https://gbfs-validator.mobilitydata.org/validator?url=${item.autoDiscovery}`
                  target='_blank'
                  rel='noreferrer'
                  endIcon={<OpenInNewIcon></OpenInNewIcon>}
                >
                  {t('runValidationReport')}
                </Button>
                <Button
                  variant='contained'
                  color='primary'
                  href='' // TODO: item.autoDiscovery
                  target='_blank'
                  rel='noreferrer'
                  endIcon={<OpenInNewIcon></OpenInNewIcon>}
                >
                  {t('openFeedUrl')}
                </Button>
              </Box>
            </ContentBox>
          ))}
      </Box>
    </>
  );
}
