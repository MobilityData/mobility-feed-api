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
import { groupFeaturesByComponent } from '../../utils/consts';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../components/NestedCheckboxList';
import {
  getDataTypeParamFromSelectedFeedTypes,
  getInitialSelectedFeedTypes,
} from './utility';
import {
  chipHolderStyles,
  searchBarStyles,
  SearchHeader,
  stickyHeaderStyles,
} from './Feeds.styles';
import { useRemoteConfig } from '../../context/RemoteConfigProvider';
import { MainPageHeader } from '../../styles/PageHeader.style';
import { ColoredContainer } from '../../styles/PageLayout.style';

export default function Feed(): React.ReactElement {
  const theme = useTheme();
  const { t } = useTranslation('feeds');
  const { config } = useRemoteConfig();
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
  const [expandedElements, setExpandedElements] = useState<
    Record<string, boolean>
  >(setInitialExpandGroup());
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>(
    searchParams.get('features')?.split(',') ?? [],
  );
  const [featureCheckboxData, setFeatureCheckboxData] = useState<
    CheckboxStructure[]
  >([]);
  const [activePagination, setActivePagination] = useState(
    searchParams.get('o') !== null ? Number(searchParams.get('o')) : 1,
  );
  const user = useSelector(selectUserProfile);
  const dispatch = useAppDispatch();
  const feedsData = useSelector(selectFeedsData);
  const feedStatus = useSelector(selectFeedsStatus);

  // features i/o
  const areFeatureFiltersEnabled =
    !selectedFeedTypes.gtfs_rt || selectedFeedTypes.gtfs;

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
            is_official: isOfficialFeedSearch || undefined,
            // Fixed status values for now, until a status filter is implemented
            // Filtering out deprecated feeds
            status: ['active', 'inactive', 'development'],
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
    if (selectedFeatures.length > 0) {
      newSearchParams.set('features', selectedFeatures.join(','));
    }
    if (isOfficialFeedSearch) {
      newSearchParams.set('official', 'true');
    }
    if (searchParams.toString() !== newSearchParams.toString()) {
      setSearchParams(newSearchParams, { replace: false });
    }
  }, [
    activeSearch,
    activePagination,
    selectedFeedTypes,
    selectedFeatures,
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

  function setInitialExpandGroup(): Record<string, boolean> {
    const expandGroup: Record<string, boolean> = {};
    Object.keys(groupFeaturesByComponent()).forEach((featureGroup) => {
      expandGroup[featureGroup] = false;
    });
    return expandGroup;
  }

  function generateCheckboxStructure(): CheckboxStructure[] {
    const groupedFeatures = groupFeaturesByComponent();
    return Object.entries(groupedFeatures)
      .filter(([parent]) => parent !== 'Other')
      .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
      .map(([parent, features]) => ({
        title: parent,
        checked: features.every((feature) =>
          selectedFeatures.includes(feature.feature),
        ),
        seeChildren: expandedElements[parent],
        type: 'checkbox',
        children: features.map((feature) => {
          return {
            title: feature.feature,
            type: 'checkbox',
            checked: selectedFeatures.some(
              (selectedFeature) => selectedFeature === feature.feature,
            ),
          };
        }),
      }));
  }

  function clearAllFilters(): void {
    setActivePagination(1);
    setSelectedFeedTypes({
      gtfs: false,
      gtfs_rt: false,
    });
    setSelectedFeatures([]);
    setIsOfficialFeedSearch(false);
  }

  React.useEffect(() => {
    setFeatureCheckboxData(generateCheckboxStructure());
  }, [selectedFeatures]);

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

  return (
    <Container component='main' maxWidth={false}>
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
        <Box sx={stickyHeaderStyles({ theme, isSticky })}>
          <Container
            maxWidth={'xl'}
            component='form'
            onSubmit={(event) => {
              event.preventDefault();
              setActivePagination(1);
              setActiveSearch(searchQuery);
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
                      setActiveSearch(searchQuery);
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
                minWidth: config.enableFeatureFilterSearch ? '275px' : '220px',
                pr: 2,
              }}
            >
              <SearchHeader variant='h6'>{t('dataType')}</SearchHeader>
              <NestedCheckboxList
                checkboxData={[
                  {
                    title: t('common:gtfsSchedule'),
                    checked: selectedFeedTypes.gtfs,
                    type: 'checkbox',
                  },
                  {
                    title: t('common:gtfsRealtime'),
                    checked: selectedFeedTypes.gtfs_rt,
                    type: 'checkbox',
                  },
                ]}
                onCheckboxChange={(checkboxData) => {
                  setActivePagination(1);
                  setSelectedFeedTypes({
                    ...selectedFeedTypes,
                    gtfs: checkboxData[0].checked,
                    gtfs_rt: checkboxData[1].checked,
                  });
                }}
              ></NestedCheckboxList>
              {config.enableIsOfficialFilterSearch && (
                <>
                  <SearchHeader variant='h6'>Tags</SearchHeader>
                  <NestedCheckboxList
                    checkboxData={[
                      {
                        title: 'Official Feeds',
                        checked: isOfficialFeedSearch,
                        type: 'checkbox',
                      },
                    ]}
                    onCheckboxChange={(checkboxData) => {
                      setActivePagination(1);
                      setIsOfficialFeedSearch(checkboxData[0].checked);
                    }}
                  ></NestedCheckboxList>
                </>
              )}

              {(config.enableFeatureFilterSearch || 3 > 2) && (
                <>
                  <SearchHeader
                    variant='h6'
                    sx={areFeatureFiltersEnabled ? {} : { opacity: 0.5 }}
                  >
                    Features
                  </SearchHeader>
                  <NestedCheckboxList
                    disableAll={!areFeatureFiltersEnabled}
                    debounceTime={500}
                    checkboxData={featureCheckboxData}
                    onExpandGroupChange={(checkboxData) => {
                      const newExpandGroup: Record<string, boolean> = {};
                      checkboxData.forEach((cd) => {
                        if (cd.seeChildren !== undefined) {
                          newExpandGroup[cd.title] = cd.seeChildren;
                        }
                      });
                      setExpandedElements({
                        ...expandedElements,
                        ...newExpandGroup,
                      });
                    }}
                    onCheckboxChange={(checkboxData) => {
                      const selelectedFeatures: string[] = [];
                      checkboxData.forEach((checkbox) => {
                        if (checkbox.children !== undefined) {
                          checkbox.children.forEach((child) => {
                            if (child.checked) {
                              selelectedFeatures.push(child.title);
                            }
                          });
                        }
                      });
                      setActivePagination(1);
                      setSelectedFeatures([...selelectedFeatures]);
                    }}
                  />
                </>
              )}
            </Grid>

            <Grid item xs={12} md={10}>
              <Box sx={chipHolderStyles}>
                {selectedFeedTypes.gtfs && (
                  <Chip
                    color='secondary'
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
                    color='secondary'
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
                {isOfficialFeedSearch && (
                  <Chip
                    color='secondary'
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
                      color='secondary'
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
                {(selectedFeatures.length > 0 ||
                  isOfficialFeedSearch ||
                  selectedFeedTypes.gtfs_rt ||
                  selectedFeedTypes.gtfs) && (
                  <Button
                    variant={'text'}
                    onClick={clearAllFilters}
                    size={'small'}
                    color={'secondary'}
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
                      <TableContainer>
                        <Grid item xs={12}>
                          <Typography
                            variant='subtitle2'
                            sx={{ fontWeight: 'bold' }}
                            gutterBottom
                          >
                            {getSearchResultNumbers()}
                          </Typography>
                        </Grid>
                        <SearchTable feedsData={feedsData} />
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
