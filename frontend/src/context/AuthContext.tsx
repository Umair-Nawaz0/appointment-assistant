import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '../lib/api';
import type { BusinessAccount } from '../types';

type AuthValue = {
  business: BusinessAccount|null; loading: boolean;
  login(email:string,password:string):Promise<void>; logout():Promise<void>; refresh():Promise<void>;
};
const AuthContext = createContext<AuthValue|null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [business, setBusiness] = useState<BusinessAccount|null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = async () => {
    try { const result = await api<{business:BusinessAccount}>('/auth/me'); setBusiness(result.business); }
    catch { setBusiness(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { void refresh(); }, []);
  const value = useMemo<AuthValue>(() => ({
    business, loading, refresh,
    login: async (email,password) => { const result=await api<{business:BusinessAccount}>('/auth/login',{method:'POST',body:JSON.stringify({email,password})}); setBusiness(result.business); },
    logout: async () => { await api('/auth/logout',{method:'POST'}); setBusiness(null); },
  }), [business, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value=useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
