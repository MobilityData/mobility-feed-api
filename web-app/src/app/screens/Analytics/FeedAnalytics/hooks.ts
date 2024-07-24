import { useState, useEffect } from 'react';
import { type Feed, type Metrics } from '../types';

/**
 * Fetches data from the given URL and returns it along with the loading state
 * @param url URL to fetch the data from
 * @returns Object with the data and loading state
 */
export const useFetchData = (
  url: string,
): { data: Feed[]; loading: boolean } => {
  const [data, setData] = useState<Feed[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async (): Promise<void> => {
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedData = await response.json();
        const transformedData = fetchedData.map((item: Feed) => ({
          ...item,
          created_on: new Date(item.created_on),
          last_modified: new Date(item.last_modified),
        }));
        setData(transformedData);
      } finally {
        setLoading(false);
      }
    };
    void fetchData();
  }, [url]);

  return { data, loading };
};

/**
 * Fetches metrics data from the given URL
 * @param url URL to fetch the metrics data from
 * @returns Array of metrics data
 */
export const useFetchMetrics = (url: string): Metrics[] => {
  const [metrics, setMetrics] = useState<Metrics[]>([]);

  useEffect(() => {
    const fetchMetrics = async (): Promise<void> => {
      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const fetchedMetrics: Metrics[] = await response.json();
        setMetrics(fetchedMetrics);
      } catch (error) {
        console.error('Error fetching metrics data:', error);
      }
    };

    void fetchMetrics();
  }, [url]);

  return metrics;
};
