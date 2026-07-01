import { useCallback, useEffect, useState } from "react";
import { getMe, getToken, loginUser, registerUser, setToken } from "../api/client.js";
import { AuthContext } from "./authContext.js";

export function AuthProvider({ children }) {
  const [bootToken] = useState(() => getToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(bootToken));

  // On boot: if we have a stored token, validate it; otherwise show the login.
  useEffect(() => {
    if (!bootToken) {
      return;
    }

    getMe()
      .then((data) => setUser(data.user))
      .catch(() => setToken(""))
      .finally(() => setLoading(false));
  }, [bootToken]);

  const login = useCallback(async (email, password) => {
    const data = await loginUser(email, password);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(
    async (email, password, displayName) => {
      await registerUser(email, password, displayName);
      // Auto-login straight after registering.
      return login(email, password);
    },
    [login]
  );

  const logout = useCallback(() => {
    setToken("");
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const data = await getMe();
    setUser(data.user);
    return data.user;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
