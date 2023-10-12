import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';

/**
 * This component is used to protect routes that require authentication.
 */
export const ProtectedRoute = (): JSX.Element => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to='/' />;
  }
  return <Outlet />;
};
