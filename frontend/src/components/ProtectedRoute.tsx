import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Spinner } from './ui';
export function ProtectedRoute({children}:{children:React.ReactNode}) {
  const {business,loading}=useAuth();
  if(loading)return <div className="screen-center"><Spinner/></div>;
  return business?children:<Navigate to="/login" replace/>;
}
