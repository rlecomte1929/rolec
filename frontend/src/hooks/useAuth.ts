import { useNavigate } from 'react-router-dom';
import { authAPI } from '../api/client';
import type { LoginRequest, RegisterRequest, UserRole } from '../types';
import { setAuthItem } from '../utils/demo';
import { safeNavigate } from '../navigation/safeNavigate';

export const useAuth = () => {
  const navigate = useNavigate();

  const setSession = (token: string, user: { id: string; role: UserRole; email?: string | null; username?: string | null; name?: string | null }) => {
    setAuthItem('relopass_token', token);
    setAuthItem('relopass_user_id', user.id);
    if (user.email) setAuthItem('relopass_email', user.email);
    if (user.username) setAuthItem('relopass_username', user.username);
    if (user.name) setAuthItem('relopass_name', user.name);
    setAuthItem('relopass_role', user.role);
  };

  const redirectByRole = (role: UserRole) => {
    safeNavigate(navigate, role === 'HR' ? 'hrDashboard' : 'employeeJourney');
  };

  const login = async (payload: LoginRequest) => {
    const response = await authAPI.login(payload);
    setSession(response.token, response.user);
    redirectByRole(response.user.role);
    return response;
  };

  const register = async (payload: RegisterRequest) => {
    const response = await authAPI.register(payload);
    setSession(response.token, response.user);
    redirectByRole(response.user.role);
    return response;
  };

  return { login, register };
};
