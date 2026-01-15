import * as React from 'react';
import { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import {
  Box,
  Button,
  Chip,
  Container,
  CssBaseline,
  Grid,
  InputAdornment,
  Pagination,
  Skeleton,
  TableContainer,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useTheme,
} from '@mui/material';
import { Search } from '@mui/icons-material';
import { selectUserProfile } from '../../store/profile-selectors';
import { useAppDispatch } from '../../hooks';
import { loadingFeeds } from '../../store/feeds-reducer';
import {
  selectFeedsData,
  selectFeedsStatus,
} from '../../store/feeds-selectors';
import { useSearchParams } from 'react-router-dom';
import SearchTable from './SearchTable';
import { Trans, useTranslation } from 'react-i18next';
import {
  getDataTypeParamFromSelectedFeedTypes,
  getInitialSelectedFeedTypes,
} from './utility';
import {
  chipHolderStyles,
  searchBarStyles,
  stickyHeaderStyles,
} from './Feeds.styles';
import { MainPageHeader } from '../../styles/PageHeader.style';
import { ColoredContainer } from '../../styles/PageLayout.style';
import AdvancedSearchTable from './AdvancedSearchTable';
import ViewHeadlineIcon from '@mui/icons-material/ViewHeadline';
import GridViewIcon from '@mui/icons-material/GridView';
import { SearchFilters } from './SearchFilters';

export default function Feed(): React.ReactElement {
  const theme = useTheme();
  const { t } = useTranslation('feeds');
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchLimit] = useState(20); // leaving possibility to edit in future
  const [selectedFeedTypes, setSelectedFeedTypes] = useState(
    getInitialSelectedFeedTypes(searchParams),
  );
  const [isSticky, setIsSticky] = useState(false);
  const [activeSearch, setActiveSearch] = useState(searchParams.get('q') ?? '');
  const [isOfficialFeedSearch, setIsOfficialFeedSearch] = useState(
    Boolean(searchParams.get('official')) ?? false,
  );
  const [searchQuery, setSearchQuery] = useState(activeSearch);

  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(
    searchParams.get('features')?.split(',') ?? [],
  );
  const [selectGbfsVersions, setSelectGbfsVersions] = useState<string[]>(
    searchParams.get('gbfs_versions')?.split(',') ?? [],
  );
  const [activePagination, setActivePagination] = useState(
    searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1,
  );
  const [searchView, setSearchView] = useState<'simple' | 'advanced'>(
    'advanced',
  );
  const user = useSelector(selectUserProfile);
  const dispatch = useAppDispatch();
  const feedsData = useSelector(selectFeedsData);
  const feedStatus = useSelector(selectFeedsStatus);

  const hasTransitFeedsRedirectParam =
    searchParams.get('utm_source') === 'transitfeeds';

  // features i/o
  const areNoDataTypesSelected =
    !selectedFeedTypes.gtfs &&
    !selectedFeedTypes.gtfs_rt &&
    !selectedFeedTypes.gbfs;
  const isOfficialTagFilterEnabled =
    selectedFeedTypes.gtfs ||
    selectedFeedTypes.gtfs_rt ||
    areNoDataTypesSelected;
  const areFeatureFiltersEnabled =
    (!selectedFeedTypes.gtfs_rt && !selectedFeedTypes.gbfs) ||
    selectedFeedTypes.gtfs;
  const areGBFSFiltersEnabled =
    selectedFeedTypes.gbfs &&
    !selectedFeedTypes.gtfs_rt &&
    !selectedFeedTypes.gtfs;

  const getPaginationOffset = (activePagination?: number): number => {
    const paginationParam =
      searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1;
    const pagination = activePagination ?? paginationParam;
    const paginationOffset = (pagination - 1) * searchLimit;
    return paginationOffset;
  };

  useEffect(() => {
    if (user == null) return;

    const paginationOffset = getPaginationOffset(activePagination);
    dispatch(
      loadingFeeds({
        params: {
          query: {
            limit: searchLimit,
            offset: paginationOffset,
            search_query: activeSearch,
            data_type: getDataTypeParamFromSelectedFeedTypes(selectedFeedTypes),
            is_official: isOfficialTagFilterEnabled
              ? isOfficialFeedSearch || undefined
              : undefined,
            // Fixed status values for now, until a status filter is implemented
            // Filtering out deprecated feeds
            status: ['active', 'inactive', 'development', 'future'],
            feature: areFeatureFiltersEnabled ? selectedFeatures : undefined,
            version: areGBFSFiltersEnabled
              ? selectGbfsVersions.join(',').replaceAll('v', '')
              : undefined,
          },
        },
      }),
    );
  }, [
    user,
    activeSearch,
    activePagination,
    selectedFeedTypes,
    searchLimit,
    isOfficialFeedSearch,
    selectedFeatures,
    selectGbfsVersions,
  ]);

  useEffect(() => {
    const newSearchParams = new URLSearchParams();
    if (activeSearch !== '') {
      newSearchParams.set('q', activeSearch);
    }

    if (activePagination !== 1) {
      newSearchParams.set('o', activePagination.toString());
    }
    if (selectedFeedTypes.gtfs) {
      newSearchParams.set('gtfs', 'true');
    }
    if (selectedFeedTypes.gtfs_rt) {
      newSearchParams.set('gtfs_rt', 'true');
    }
    if (selectedFeedTypes.gbfs) {
      newSearchParams.set('gbfs', 'true');
    }
    if (selectedFeatures.length > 0) {
      newSearchParams.set('features', selectedFeatures.join(','));
    }
    if (selectGbfsVersions.length > 0) {
      newSearchParams.set('gbfs_versions', selectGbfsVersions.join(','));
    }
    if (isOfficialFeedSearch) {
      newSearchParams.set('official', 'true');
    }
    if (searchParams.get('utm_source') === 'transitfeeds') {
      newSearchParams.set('utm_source', 'transitfeeds');
    }
    if (searchParams.toString() !== newSearchParams.toString()) {
      setSearchParams(newSearchParams, { replace: false });
    }
  }, [
    activeSearch,
    activePagination,
    selectedFeedTypes,
    selectedFeatures,
    selectGbfsVersions,
    isOfficialFeedSearch,
  ]);

  // When url updates, it will update the state of the search page
  // This is to ensure that the search page is in sync with the url
  useEffect(() => {
    const newQuery = searchParams.get('q') ?? '';
    if (newQuery !== searchQuery) {
      setSearchQuery(newQuery);
      setActiveSearch(newQuery);
    }
    const newOffset =
      searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1;
    if (newOffset !== activePagination) {
      setActivePagination(newOffset);
    }

    const newFeatures = searchParams.get('features')?.split(',') ?? [];
    if (newFeatures.join(',') !== selectedFeatures.join(',')) {
      setSelectedFeatures([...newFeatures]);
    }

    const newGbfsVersions = searchParams.get('gbfs_versions')?.split(',') ?? [];
    if (newGbfsVersions.join(',') !== selectGbfsVersions.join(',')) {
      setSelectGbfsVersions([...newGbfsVersions]);
    }

    const newSearchOfficial = Boolean(searchParams.get('official')) ?? false;
    if (newSearchOfficial !== isOfficialFeedSearch) {
      setIsOfficialFeedSearch(newSearchOfficial);
    }

    const newFeedTypes = getInitialSelectedFeedTypes(searchParams);
    if (newFeedTypes.gtfs !== selectedFeedTypes.gtfs) {
      setSelectedFeedTypes({
        ...selectedFeedTypes,
        gtfs: newFeedTypes.gtfs,
      });
    }

    if (newFeedTypes.gtfs_rt !== selectedFeedTypes.gtfs_rt) {
      setSelectedFeedTypes({
        ...selectedFeedTypes,
        gtfs_rt: newFeedTypes.gtfs_rt,
      });
    }

    if (newFeedTypes.gbfs !== selectedFeedTypes.gbfs) {
      setSelectedFeedTypes({
        ...selectedFeedTypes,
        gbfs: newFeedTypes.gbfs,
      });
    }
  }, [searchParams]);

  const getSearchResultNumbers = (): string => {
    if (feedsData?.total !== undefined && feedsData?.total > 0) {
      const offset = getPaginationOffset(activePagination);
      const limit = offset + searchLimit;

      const startResult = 1 + offset;
      const endResult = limit > feedsData?.total ? feedsData.total : limit;
      const totalResults = feedsData?.total ?? '';
      return t('resultsFor', { startResult, endResult, totalResults });
    } else {
      return '';
    }
  };

  function clearAllFilters(): void {
    setActivePagination(1);
    setSelectedFeedTypes({
      gtfs: false,
      gtfs_rt: false,
      gbfs: false,
    });
    setSelectedFeatures([]);
    setSelectGbfsVersions([]);
    setIsOfficialFeedSearch(false);
  }

  const containerRef = React.useRef(null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsSticky(!entry.isIntersecting);
      },
      { threshold: 1.0 },
    );

    if (containerRef.current !== null) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  const handleViewChange = (
    event: React.MouseEvent<HTMLElement>,
    newSearchView: 'simple' | 'advanced' | null,
  ): void => {
    if (newSearchView != null) {
      setSearchView(newSearchView);
    }
  };

  return (
    <Container
      component='main'
      maxWidth={false}
      sx={{
        overflowX: 'initial',
      }}
    >
      <CssBaseline />
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
        }}
        mx={{ xs: 0, md: 'auto' }}
      >
        <Container
          disableGutters
          maxWidth={'xl'}
          sx={{ boxSizing: 'content-box' }}
        >
          <MainPageHeader ref={containerRef}>
            {t('common:feeds')}
          </MainPageHeader>
          {activeSearch !== '' && (
            <Typography variant='subtitle1'>
              {t('searchFor')}: <b>{activeSearch}</b>
            </Typography>
          )}
        </Container>
        <Box
          sx={stickyHeaderStyles({
            theme,
            isSticky,
            headerBannerVisible: hasTransitFeedsRedirectParam,
          })}
        >
          <Container
            maxWidth={'xl'}
            component='form'
            onSubmit={(event) => {
              event.preventDefault();
              setActivePagination(1);
              setActiveSearch(searchQuery.trim());
            }}
            sx={searchBarStyles}
          >
            <TextField
              sx={{
                width: 'calc(100% - 85px)',
              }}
              value={searchQuery}
              placeholder={t('searchPlaceholder')}
              onChange={(e) => {
                setSearchQuery(e.target.value);
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment
                    style={{
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      setActivePagination(1);
                      setActiveSearch(searchQuery.trim());
                    }}
                    position='start'
                  >
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
            <Button
              variant='contained'
              type='submit'
              sx={{ m: 1, height: '55px', mr: 0 }}
            >
              {t('common:search')}
            </Button>
          </Container>
        </Box>

        <ColoredContainer maxWidth={'xl'} sx={{ pt: 2 }}>
          <Grid
            container
            spacing={1}
            sx={{
              fontSize: '18px',
              mt: 0,
              flexWrap: { xs: 'wrap', md: 'nowrap' },
            }}
          >
            <Grid
              item
              xs={12}
              md={2}
              sx={{
                minWidth: '275px',
                pr: 2,
              }}
            >
              <SearchFilters
                selectedFeedTypes={selectedFeedTypes}
                isOfficialFeedSearch={isOfficialFeedSearch}
                selectedFeatures={selectedFeatures}
                selectedGbfsVersions={selectGbfsVersions}
                setSelectedFeedTypes={(feedTypes) => {
                  setActivePagination(1);
                  setSelectedFeedTypes(feedTypes);
                }}
                setIsOfficialFeedSearch={(isOfficial) => {
                  setActivePagination(1);
                  setIsOfficialFeedSearch(isOfficial);
                }}
                setSelectedFeatures={(features) => {
                  setActivePagination(1);
                  setSelectedFeatures(features);
                }}
                setSelectedGbfsVerions={(versions) => {
                  setSelectGbfsVersions(versions);
                  setActivePagination(1);
                }}
                isOfficialTagFilterEnabled={isOfficialTagFilterEnabled}
                areFeatureFiltersEnabled={areFeatureFiltersEnabled}
                areGBFSFiltersEnabled={areGBFSFiltersEnabled}
              ></SearchFilters>
            </Grid>

            <Grid item xs={12} md={10}>
              <Box sx={chipHolderStyles}>
                {selectedFeedTypes.gtfs && (
                  <Chip
                    color='primary'
                    variant='outlined'
                    size='small'
                    label={t('common:gtfsSchedule')}
                    onDelete={() => {
                      setActivePagination(1);
                      setSelectedFeedTypes({
                        ...selectedFeedTypes,
                        gtfs: false,
                      });
                    }}
                  />
                )}
                {selectedFeedTypes.gtfs_rt && (
                  <Chip
                    color='primary'
                    variant='outlined'
                    size='small'
                    label={t('common:gtfsRealtime')}
                    onDelete={() => {
                      setActivePagination(1);
                      setSelectedFeedTypes({
                        ...selectedFeedTypes,
                        gtfs_rt: false,
                      });
                    }}
                  />
                )}
                {selectedFeedTypes.gbfs && (
                  <Chip
                    color='primary'
                    variant='outlined'
                    size='small'
                    label={t('common:gbfs')}
                    onDelete={() => {
                      setActivePagination(1);
                      setSelectedFeedTypes({
                        ...selectedFeedTypes,
                        gbfs: false,
                      });
                    }}
                  />
                )}
                {isOfficialFeedSearch && isOfficialTagFilterEnabled && (
                  <Chip
                    color='primary'
                    variant='outlined'
                    size='small'
                    label={'Official Feeds'}
                    onDelete={() => {
                      setActivePagination(1);
                      setIsOfficialFeedSearch(false);
                    }}
                  />
                )}
                {areFeatureFiltersEnabled &&
                  selectedFeatures.map((feature) => (
                    <Chip
                      color='primary'
                      variant='outlined'
                      size='small'
                      label={feature}
                      key={feature}
                      onDelete={() => {
                        setSelectedFeatures([
                          ...selectedFeatures.filter((sf) => sf !== feature),
                        ]);
                      }}
                    />
                  ))}

                {areGBFSFiltersEnabled &&
                  selectGbfsVersions.map((gbfsVersion) => (
                    <Chip
                      color='primary'
                      variant='outlined'
                      size='small'
                      label={gbfsVersion}
                      key={gbfsVersion}
                      onDelete={() => {
                        setSelectGbfsVersions([
                          ...selectGbfsVersions.filter(
                            (sv) => sv !== gbfsVersion,
                          ),
                        ]);
                      }}
                    />
                  ))}

                {(selectedFeatures.length > 0 ||
                  selectGbfsVersions.length > 0 ||
                  isOfficialFeedSearch ||
                  selectedFeedTypes.gtfs_rt ||
                  selectedFeedTypes.gtfs ||
                  selectedFeedTypes.gbfs) && (
                  <Button
                    variant={'text'}
                    onClick={clearAllFilters}
                    size={'small'}
                    color={'primary'}
                  >
                    Clear All
                  </Button>
                )}
              </Box>
              {feedStatus === 'loading' && (
                <Grid item xs={12}>
                  <Skeleton
                    animation='wave'
                    variant='text'
                    sx={{ fontSize: '1rem', width: '200px' }}
                  />
                  <Skeleton
                    animation='wave'
                    variant='text'
                    sx={{ fontSize: '2rem', width: '100%' }}
                  />
                  <Skeleton
                    animation='wave'
                    variant='rectangular'
                    width={'100%'}
                    height={'1118px'}
                  />
                  <Skeleton
                    animation='wave'
                    variant='text'
                    sx={{ fontSize: '2rem', width: '320px' }}
                  />
                </Grid>
              )}

              {feedStatus === 'error' && (
                <Grid item xs={12}>
                  <h3>{t('common:errors.generic')}</h3>
                  <Typography>
                    <Trans i18nKey='errorAndContact'>
                      Please check your internet connection and try again. If
                      the problem persists
                      <Button
                        variant='text'
                        className='inline'
                        href={'mailto:api@mobilitydata.org'}
                      >
                        contact us
                      </Button>
                      for for further assistance.
                    </Trans>
                  </Typography>
                </Grid>
              )}

              {feedsData !== undefined && feedStatus === 'loaded' && (
                <>
                  {feedsData?.results?.length === 0 && (
                    <Grid item xs={12}>
                      <h3>{t('noResults', { activeSearch })}</h3>
                      <Typography>{t('searchSuggestions')}</Typography>
                      <ul>
                        <li>
                          <Typography>{t('searchTips.twoDigit')}</Typography>
                        </li>
                        <li>
                          <Typography>{t('searchTips.fullName')}</Typography>
                        </li>
                        <li>
                          <Typography>
                            Try adjusting your filters, or removing strict
                            criteria
                          </Typography>
                        </li>
                        <li>
                          <Typography>
                            {t('searchTips.checkSpelling')}
                          </Typography>
                        </li>
                      </ul>
                    </Grid>
                  )}
                  {feedsData?.results !== undefined &&
                    feedsData?.results !== null &&
                    feedsData?.results?.length > 0 && (
                      <TableContainer sx={{ overflowX: 'initial' }}>
                        <Grid
                          item
                          xs={12}
                          sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'self-end',
                          }}
                        >
                          <Typography
                            variant='subtitle2'
                            sx={{ fontWeight: 'bold' }}
                            gutterBottom
                          >
                            {getSearchResultNumbers()}
                          </Typography>
                          <ToggleButtonGroup
                            color='primary'
                            value={searchView}
                            exclusive
                            onChange={handleViewChange}
                            aria-label='Platform'
                          >
                            <ToggleButton
                              value='simple'
                              aria-label='Simple Search View'
                            >
                              <ViewHeadlineIcon></ViewHeadlineIcon>
                            </ToggleButton>
                            <ToggleButton
                              value='advanced'
                              aria-label='Advanced Search View'
                            >
                              <GridViewIcon></GridViewIcon>
                            </ToggleButton>
                          </ToggleButtonGroup>
                        </Grid>
                        {searchView === 'simple' ? (
                          <SearchTable feedsData={feedsData} />
                        ) : (
                          <AdvancedSearchTable
                            feedsData={feedsData}
                            selectedFeatures={selectedFeatures}
                            selectedGbfsVersions={selectGbfsVersions}
                          />
                        )}

                        <Pagination
                          sx={{
                            mt: 2,
                            button: {
                              backgroundColor: theme.palette.background.default,
                              color: theme.palette.primary.main,
                              '&.Mui-selected': {
                                backgroundColor: theme.palette.primary.main,
                                color: theme.palette.background.default,
                              },
                            },
                          }}
                          color='primary'
                          page={activePagination}
                          shape='rounded'
                          count={
                            feedsData.total !== undefined
                              ? Math.ceil(feedsData.total / searchLimit)
                              : 1
                          }
                          onChange={(event, value) => {
                            event.preventDefault();
                            setActivePagination(value);
                          }}
                        />
                      </TableContainer>
                    )}
                </>
              )}
            </Grid>
          </Grid>
        </ColoredContainer>
      </Box>
    </Container>
  );
}
