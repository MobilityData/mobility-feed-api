import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';

export const ProtectedRoute = (): JSX.Element => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to='/' />;
  }
  return <Outlet />;
};
