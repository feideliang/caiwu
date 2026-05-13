import { post, get } from './request';
import type { LoginRequest, LoginResponse, User } from '@/types/api';

export function login(data: LoginRequest) {
  return post<LoginResponse>('/auth/login', data);
}

export function getMe() {
  return get<User>('/auth/me');
}

export function logout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
}
