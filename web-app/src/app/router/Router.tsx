import React, { useEffect } from 'react';
import { Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import SignIn from '../screens/SignIn';
import SignUp from '../screens/SignUp';
import Account from '../screens/Account';
import ContactInformation from '../screens/ContactInformation';
import { ProtectedRoute } from './ProtectedRoute';
import CompleteRegistration from '../screens/CompleteRegistration';
import ChangePassword from '../screens/ChangePassword';
import Home from '../screens/Home';
import ForgotPassword from '../screens/ForgotPassword';
import FAQ from '../screens/FAQ';
import PostRegistration from '../screens/PostRegistration';
import TermsAndConditions from '../screens/TermsAndConditions';
import PrivacyPolicy from '../screens/PrivacyPolicy';
import Feed from '../screens/Feed';
import Feeds from '../screens/Feeds';
import { SIGN_OUT_TARGET } from '../constants/Navigation';
import {
  LOGIN_CHANNEL,
  LOGOUT_CHANNEL,
  createBroadcastChannel,
} from '../services/channel-service';
import { useAppDispatch } from '../hooks';
import { logout } from '../store/profile-reducer';
import FeedSubmission from '../screens/FeedSubmission';
import FeedSubmissionFAQ from '../screens/FeedSubmissionFAQ';
import FeedSubmitted from '../screens/FeedSubmitted';
import GTFSFeedAnalytics from '../screens/Analytics/GTFSFeedAnalytics';
import GTFSNoticeAnalytics from '../screens/Analytics/GTFSNoticeAnalytics';
import GTFSFeatureAnalytics from '../screens/Analytics/GTFSFeatureAnalytics';
import GBFSFeedAnalytics from '../screens/Analytics/GBFSFeedAnalytics';
import GBFSNoticeAnalytics from '../screens/Analytics/GBFSNoticeAnalytics';
import GBFSVersionAnalytics from '../screens/Analytics/GBFSVersionAnalytics';
import ContactUs from '../screens/ContactUs';
import FullMapView from '../screens/Feed/components/FullMapView';
import GbfsValidator from '../screens/GbfsValidator';
import { GbfsAuthProvider } from '../context/GbfsAuthProvider';

export const AppRouter: React.FC = () => {
  const navigateTo = useNavigate();
  const dispatch = useAppDispatch();

  /**
   * Logs out the user and redirects to the sign-out target screen after a logout event is received on the other sessions.
   */
  const logoutUserCallback = (): void => {
    dispatch(
      logout({ redirectScreen: SIGN_OUT_TARGET, navigateTo, propagate: false }),
    );
  };

  /**
   * Refreshes the page to ensure the user is authenticated after a login event is received on the other sessions.
   */
  const loginUserCallback = (): void => {
    window.location.reload();
  };

  /**
   * The channel creation is placed in this component rather than the App.tsx file due to the need of the navigateTo instance.
   * The navigateTo instance is only available within the scope the Router including its children.
   * The callback functions are used to handle the logout and login events received from other sessions.
   */
  useEffect(() => {
    createBroadcastChannel(LOGOUT_CHANNEL, logoutUserCallback);
    createBroadcastChannel(LOGIN_CHANNEL, loginUserCallback);
  }, []);

  return (
    <Routes>
      <Route path='/' element={<Home />} />
      <Route path='sign-in' element={<SignIn />} />
      <Route path='sign-up' element={<SignUp />} />
      <Route element={<ProtectedRoute targetStatus='authenticated' />}>
        <Route
          path='complete-registration'
          element={<CompleteRegistration />}
        />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route path='account' element={<Account />} />
      </Route>
      <Route path='contact-info' element={<ContactInformation />} />
      <Route element={<ProtectedRoute />}>
        <Route path='change-password' element={<ChangePassword />} />
      </Route>
      <Route element={<ProtectedRoute targetStatus='unverified' />}>
        <Route path='verify-email' element={<PostRegistration />} />
      </Route>
      <Route path='forgot-password' element={<ForgotPassword />} />
      <Route path='faq' element={<FAQ />} />
      <Route path='contact-us' element={<ContactUs />} />
      <Route path='feeds' element={<Feeds />} />
      <Route
        path='gbfs-validator'
        element={
          <GbfsAuthProvider>
            <GbfsValidator />
          </GbfsAuthProvider>
        }
      />
      <Route
        path='feeds/gtfs'
        element={<Navigate to='/feeds?gtfs=true' replace />}
      />
      <Route
        path='feeds/gtfs_rt'
        element={<Navigate to='/feeds?gtfs_rt=true' replace />}
      />
      <Route path='feeds/:feedId' element={<Feed />} />
      <Route path='feeds/:feedDataType/:feedId' element={<Feed />} />
      <Route path='feeds/:feedId/map' element={<FullMapView />} />
      <Route path='feeds/:feedDataType/:feedId/map' element={<FullMapView />} />
      <Route path='contribute' element={<FeedSubmission />} />
      <Route path='contribute/submitted' element={<FeedSubmitted />} />
      <Route path='contribute-faq' element={<FeedSubmissionFAQ />} />
      <Route path='privacy-policy' element={<PrivacyPolicy />} />
      <Route path='terms-and-conditions' element={<TermsAndConditions />} />
      <Route path='metrics/gtfs'>
        <Route index element={<GTFSFeedAnalytics />} />
        <Route path='feeds/*' element={<GTFSFeedAnalytics />} />
        <Route path='notices/*' element={<GTFSNoticeAnalytics />} />
        <Route path='features/*' element={<GTFSFeatureAnalytics />} />
      </Route>
      <Route path='metrics/gbfs'>
        <Route path='feeds/*' element={<GBFSFeedAnalytics />} />
        <Route path='notices/*' element={<GBFSNoticeAnalytics />} />
        <Route path='versions/*' element={<GBFSVersionAnalytics />} />
      </Route>
    </Routes>
  );
};

export default AppRouter;
