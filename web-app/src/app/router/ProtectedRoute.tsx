import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectUserProfileStatus } from '../store/selectors';
import { useEffect } from 'react';
import { app } from '../../firebase';
import { useAppDispatch } from '../hooks';
import { refreshApp, refreshAppSuccess } from '../store/profile-reducer';

/**
 * Guards routes based on user profile status. Redirects to a specified route if status doesn't match `targetStatus` (default: 'registered').
 * Redirect route is configurable via the `redirect` prop (default: '/sign-in').
 */
export const ProtectedRoute = ({
  targetStatus = 'registered',
  redirect = '/sign-in',
}: {
  targetStatus?: string;
  redirect?: string;
}): React.ReactElement => {
  const userProfileStatus = useSelector(selectUserProfileStatus);
  useEffect(() => {
    app.auth();
  });
  const dispatch = useAppDispatch();

  if (userProfileStatus !== targetStatus) {
    return <Navigate to={redirect} />;
  }

  // This is triggered when user logs in or out
  // https://firebase.google.com/docs/reference/js/v8/firebase.auth.Auth#onauthstatechanged
  app.auth().onAuthStateChanged((user) => {
    if (user != null) {
      dispatch(refreshAppSuccess());
    }
  });

  if (app.auth().currentUser == null) {
    dispatch(refreshApp());
  }

  return <Outlet />;
};
