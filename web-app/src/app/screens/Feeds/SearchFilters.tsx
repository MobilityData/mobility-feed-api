import { Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import NestedCheckboxList, {
  type CheckboxStructure,
} from '../../components/NestedCheckboxList';
import { useTranslations } from 'next-intl';
import { useRemoteConfig } from '../../context/RemoteConfigProvider';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useEffect, useState } from 'react';
import { DATASET_FEATURES, groupFeaturesByComponent } from '../../utils/consts';
import { type GbfsVersionConfig } from '../../interface/RemoteConfig';
import { SearchHeader } from '../../styles/Filters.styles';

function setInitialExpandGroup(): Record<string, boolean> {
  const expandGroup: Record<string, boolean> = {};
  Object.keys(
    groupFeaturesByComponent(Object.keys(DATASET_FEATURES), true),
  ).forEach((featureGroup) => {
    expandGroup[featureGroup] = false;
  });
  return expandGroup;
}

interface SearchFiltersProps {
  selectedFeedTypes: Record<string, boolean>;
  isOfficialFeedSearch: boolean;
  selectedFeatures: string[];
  selectedGbfsVersions: string[];
  setSelectedFeedTypes: (selectedFeedTypes: Record<string, boolean>) => void;
  setIsOfficialFeedSearch: (isOfficialFeedSearch: boolean) => void;
  setSelectedFeatures: (selectedFeatures: string[]) => void;
  setSelectedGbfsVerions: (selectedVersions: string[]) => void;
  isOfficialTagFilterEnabled: boolean;
  areFeatureFiltersEnabled: boolean;
  areGBFSFiltersEnabled: boolean;
}

export function SearchFilters({
  selectedFeedTypes,
  isOfficialFeedSearch,
  selectedFeatures,
  selectedGbfsVersions,
  setSelectedFeedTypes,
  setIsOfficialFeedSearch,
  setSelectedFeatures,
  setSelectedGbfsVerions,
  isOfficialTagFilterEnabled,
  areFeatureFiltersEnabled,
  areGBFSFiltersEnabled,
}: SearchFiltersProps): React.ReactElement {
  const t = useTranslations('feeds');
  const tCommon = useTranslations('common');
  const { config } = useRemoteConfig();

  const gbfsVersionsObject: GbfsVersionConfig = JSON.parse(config.gbfsVersions);

  const [expandedCategories, setExpandedCategories] = useState<
    Record<string, boolean>
  >({
    features: areFeatureFiltersEnabled,
    tags: isOfficialTagFilterEnabled,
    gbfsVersions: true,
  });
  const [featureCheckboxData, setFeatureCheckboxData] = useState<
    CheckboxStructure[]
  >([]);
  const [expandedElements, setExpandedElements] = useState<
    Record<string, boolean>
  >(setInitialExpandGroup());

  const dataTypesCheckboxData: CheckboxStructure[] = [
    {
      title: tCommon('gtfsSchedule'),
      checked: selectedFeedTypes.gtfs,
      type: 'checkbox',
    },
    {
      title: tCommon('gtfsRealtime'),
      checked: selectedFeedTypes.gtfs_rt,
      type: 'checkbox',
    },
    {
      title: t('common:gbfs'),
      checked: selectedFeedTypes.gbfs,
      type: 'checkbox',
    },
  ];

  function generateCheckboxStructure(): CheckboxStructure[] {
    const groupedFeatures = groupFeaturesByComponent(
      Object.keys(DATASET_FEATURES),
      true,
    );
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

  useEffect(() => {
    setFeatureCheckboxData(generateCheckboxStructure());
  }, [selectedFeatures]);

  return (
    <>
      <SearchHeader variant='h6' className='no-collapse'>
        {t('dataType')}
      </SearchHeader>
      <NestedCheckboxList
        debounceTime={500}
        checkboxData={dataTypesCheckboxData}
        onCheckboxChange={(checkboxData) => {
          const checkedFeedTypes = {
            ...selectedFeedTypes,
            gtfs: checkboxData[0].checked,
            gtfs_rt: checkboxData[1].checked,
            gbfs: checkboxData[2].checked,
          };
          setSelectedFeedTypes(checkedFeedTypes);
        }}
      ></NestedCheckboxList>

      <>
        <SearchHeader
          variant='h6'
          sx={isOfficialTagFilterEnabled ? {} : { opacity: 0.5 }}
          className='no-collapse'
        >
          Tags
        </SearchHeader>
        <NestedCheckboxList
          disableAll={!isOfficialTagFilterEnabled}
          checkboxData={[
            {
              title: 'Official Feeds',
              checked: isOfficialFeedSearch,
              type: 'checkbox',
            },
          ]}
          onCheckboxChange={(checkboxData) => {
            setIsOfficialFeedSearch(checkboxData[0].checked);
          }}
        ></NestedCheckboxList>
      </>

      <Accordion
        disableGutters
        sx={{ border: 0 }}
        variant={'outlined'}
        expanded={expandedCategories.features && areFeatureFiltersEnabled}
        onChange={() => {
          setExpandedCategories({
            ...expandedCategories,
            features: !expandedCategories.features,
          });
        }}
      >
        <AccordionSummary
          expandIcon={<ExpandMoreIcon />}
          aria-controls='panel1bh-content'
          sx={{
            px: 0,
          }}
        >
          <SearchHeader
            variant='h6'
            sx={areFeatureFiltersEnabled ? {} : { opacity: 0.5 }}
          >
            Features
          </SearchHeader>
        </AccordionSummary>
        <AccordionDetails
          sx={{
            p: 0,
            m: 0,
            border: 0,
            '&.Mui-expanded': { m: 0, minHeight: 'initial' },
          }}
        >
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
              setSelectedFeatures([...selelectedFeatures]);
            }}
          />
        </AccordionDetails>
      </Accordion>

      <Accordion
        disableGutters
        variant={'outlined'}
        sx={{
          border: 0,
          '&::before': {
            display: 'none',
          },
        }}
        expanded={expandedCategories.gbfsVersions && areGBFSFiltersEnabled}
        onChange={() => {
          setExpandedCategories({
            ...expandedCategories,
            gbfsVersions: !expandedCategories.gbfsVersions,
          });
        }}
      >
        <AccordionSummary
          expandIcon={<ExpandMoreIcon />}
          aria-controls='panel1bh-content'
          sx={{
            px: 0,
          }}
        >
          <SearchHeader
            variant='h6'
            sx={areGBFSFiltersEnabled ? {} : { opacity: 0.5 }}
          >
            GBFS Versions
          </SearchHeader>
        </AccordionSummary>
        <AccordionDetails sx={{ p: 0, m: 0, border: 0 }}>
          <NestedCheckboxList
            disableAll={!areGBFSFiltersEnabled}
            debounceTime={500}
            checkboxData={gbfsVersionsObject.map((version) => ({
              title: version,
              checked: selectedGbfsVersions.includes(version),
              type: 'checkbox',
            }))}
            onCheckboxChange={(checkboxData) => {
              const selectedVersions: string[] = [];
              checkboxData.forEach((checkbox) => {
                if (checkbox.checked) {
                  selectedVersions.push(checkbox.title);
                }
              });
              setSelectedGbfsVerions([...selectedVersions]);
            }}
          ></NestedCheckboxList>
        </AccordionDetails>
      </Accordion>
    </>
  );
}
