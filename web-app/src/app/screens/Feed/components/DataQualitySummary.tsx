import * as React from 'react';
import { Box, Chip } from '@mui/material';
import { CheckCircle, ReportOutlined } from '@mui/icons-material';
import { type components } from '../../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { WarningContentBox } from '../../../components/WarningContentBox';
import { FeedStatusChip } from '../../../components/FeedStatus';
import OfficialChip from '../../../components/OfficialChip';
import { getTranslations } from 'next-intl/server';
import { getRemoteConfigValues } from '../../../../lib/remote-config.server';

export interface DataQualitySummaryProps {
  feedStatus: components['schemas']['Feed']['status'];
  isOfficialFeed: boolean;
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default async function DataQualitySummary({
  feedStatus,
  isOfficialFeed,
  latestDataset,
}: DataQualitySummaryProps): Promise<React.ReactElement> {
  const t = await getTranslations('feeds');
  const tCommon = await getTranslations('common');
  const config = await getRemoteConfigValues();

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
                        ?.unique_error_count} ${tCommon('feedback.errors')}`
                    : tCommon('feedback.noErrors')
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
                        ?.unique_warning_count} ${tCommon('feedback.warnings')}`
                    : tCommon('feedback.noWarnings')
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
                } ${tCommon('feedback.infoNotices')}`}
                color='primary'
                variant='outlined'
              />
            </>
          )}
      </Box>
    </Box>
  );
}
