export const featureGroups: Record<string, string[]> = {
  'Fares v2': [
    'Fare Products',
    'Route-Based Fares',
    'Fare Media',
    'Zone-Based Fares',
    'Time-Based Fares',
    'Transfer Fares',
  ],
  Pathways: ['Pathways', 'Pathways Directions', 'Levels'],
  'Flexible Services': ['Continuous Stops', 'Flex'],
};

/**
 * Groups the features based on the feature groups
 * @param features List of features
 * @returns Object with grouped features and other features
 */
export function groupFeatures(features: string[]): {
  groupedFeatures: Record<string, string[]>;
  otherFeatures: string[];
} {
  const groupedFeatures: Record<string, string[]> = {};
  const otherFeatures: string[] = [];

  features?.forEach((feature) => {
    let found = false;
    for (const [group, groupFeatures] of Object.entries(featureGroups)) {
      if (groupFeatures.includes(feature)) {
        if (groupedFeatures[group] === undefined) {
          groupedFeatures[group] = [];
        }
        groupedFeatures[group].push(feature);
        found = true;
        break;
      }
    }
    if (!found) {
      otherFeatures.push(feature);
    }
  });

  return { groupedFeatures, otherFeatures };
}

/**
 * Returns the color for the feature group
 * @param group Feature group
 * @returns Color for the feature group
 */
export function getGroupColor(group: string): string {
  if (group === 'Fares v2') {
    return '#d1e2ff';
  }
  if (group === 'Pathways') {
    return '#fdd4e0';
  }
  if (group === 'Flexible Services') {
    return '#fcb68e';
  }
  return '#f7f7f7';
}
