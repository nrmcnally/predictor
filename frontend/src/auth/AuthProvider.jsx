import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getMe, getToken, loginUser, registerUser, setToken } from "../api/client.js";

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On boot: if we have a stored token, validate it; otherwise show the login.
  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }

    getMe()
      .then((data) => setUser(data.user))
      .catch(() => setToken(""))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await loginUser(username, password);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(
    async (username, password) => {
      await registerUser(username, password);
      // Auto-login straight after registering.
      return login(username, password);
    },
    [login]
  );

  const logout = useCallback(() => {
    setToken("");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
