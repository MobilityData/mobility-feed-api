import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';
import { useEffect } from 'react';
import { app } from '../../firebase';
import { useAppDispatch } from '../hooks';
import { refreshApp, refreshAppSuccess } from '../store/profile-reducer';

/**
 * This component is used to protect routes that require authentication.
 */
export const ProtectedRoute = (): JSX.Element => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  useEffect(() => {
    app.auth();
  });
  const dispatch = useAppDispatch();

  if (!isAuthenticated) {
    return <Navigate to='/' />;
  }

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
