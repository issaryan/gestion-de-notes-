export type UserRole = 'admin' | 'teacher' | 'student';

export interface User {
  id: number;
  username: string;
  role: UserRole;
  nom: string;
  prenom: string;
  email: string;
  class_id?: number;
  class_name?: string;
  last_login?: string;
  status?: 'Actif' | 'Inactif';
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}