import { getFunctions, httpsCallable } from 'firebase/functions';
import { app } from '../../../firebase';
import { type FeedSubmissionFormBody } from '../../screens/FeedSubmission/Form';

export const submitNewFeedForm = async (
  formData: FeedSubmissionFormBody,
): Promise<void> => {
  const functions = getFunctions(app, 'northamerica-northeast1');
  const writeToSheet = httpsCallable(functions, 'writeToSheet');
  await writeToSheet(formData);
};
