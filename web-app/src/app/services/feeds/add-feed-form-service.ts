import { getFunctions, httpsCallable } from 'firebase/functions';
import { app } from '../../../firebase';
import { type FeedSubmissionFormFormInput } from '../../screens/FeedSubmission/Form';

export const submitNewFeedForm = async (
  formData: FeedSubmissionFormFormInput,
): Promise<void> => {
  const functions = getFunctions(app, 'northamerica-northeast1');
  const writeToSheet = httpsCallable(functions, 'writeToSheet');
  await writeToSheet(formData);
};
