'use client';

import * as React from 'react';
import { Box, Chip } from '@mui/material';
import { CheckCircle, ReportOutlined } from '@mui/icons-material';
import { type components } from '../../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { WarningContentBox } from '../../../components/WarningContentBox';
import { useTranslations } from 'next-intl';
import { FeedStatusChip } from '../../../components/FeedStatus';
import { useRemoteConfig } from '../../../context/RemoteConfigProvider';
import OfficialChip from '../../../components/OfficialChip';

export interface DataQualitySummaryProps {
  feedStatus: components['schemas']['Feed']['status'];
  isOfficialFeed: boolean;
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default function DataQualitySummary({
  feedStatus,
  isOfficialFeed,
  latestDataset,
}: DataQualitySummaryProps): React.ReactElement {
  const t = useTranslations('feeds');
  const { config } = useRemoteConfig();
  return (
    <Box data-testid='data-quality-summary' sx={{ my: 2 }}>
      {latestDataset?.validation_report == undefined && (
        <WarningContentBox>{t('errorLoadingQualityReport')}</WarningContentBox>
      )}
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {config.enableFeedStatusBadge && (
          <FeedStatusChip status={feedStatus ?? ''}></FeedStatusChip>
        )}
        {isOfficialFeed && <OfficialChip></OfficialChip>}
        {latestDataset?.validation_report !== undefined &&
          latestDataset.validation_report !== null && (
            <>
              <Chip
                data-testid='error-count'
                clickable
                component='a'
                href={latestDataset?.validation_report?.url_html}
                target='_blank'
                rel='noopener noreferrer nofollow'
                icon={
                  latestDataset?.validation_report?.unique_error_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_error_count > 0 ? (
                    <ReportOutlined />
                  ) : (
                    <CheckCircle />
                  )
                }
                label={
                  latestDataset?.validation_report?.unique_error_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_error_count > 0
                    ? `${latestDataset?.validation_report
                        ?.unique_error_count} ${t('common:feedback.errors')}`
                    : t('common:feedback.noErrors')
                }
                color={
                  latestDataset?.validation_report?.unique_error_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_error_count > 0
                    ? 'error'
                    : 'success'
                }
                variant='outlined'
              />

              <Chip
                data-testid='warning-count'
                clickable
                component='a'
                href={latestDataset?.validation_report?.url_html}
                target='_blank'
                rel='noopener noreferrer nofollow'
                icon={
                  latestDataset?.validation_report?.unique_warning_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_warning_count > 0 ? (
                    <ReportOutlined />
                  ) : (
                    <CheckCircle />
                  )
                }
                label={
                  latestDataset?.validation_report?.unique_warning_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_warning_count > 0
                    ? `${latestDataset?.validation_report
                        ?.unique_warning_count} ${t(
                        'common:feedback.warnings',
                      )}`
                    : t('common:feedback.noWarnings')
                }
                color={
                  latestDataset?.validation_report?.unique_warning_count !==
                    undefined &&
                  latestDataset?.validation_report?.unique_warning_count > 0
                    ? 'warning'
                    : 'success'
                }
                variant='outlined'
              />

              <Chip
                data-testid='info-count'
                icon={<InfoOutlinedIcon />}
                clickable
                component='a'
                href={latestDataset?.validation_report?.url_html}
                target='_blank'
                rel='noopener noreferrer nofollow'
                label={`${
                  latestDataset?.validation_report?.unique_info_count ?? '0'
                } ${t('common:feedback.infoNotices')}`}
                color='primary'
                variant='outlined'
              />
            </>
          )}
      </Box>
    </Box>
  );
}
