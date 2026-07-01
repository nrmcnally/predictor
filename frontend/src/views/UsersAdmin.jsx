import { useEffect, useState } from "react";
import { getUsers, setUserRole } from "../api/client.js";
import { useAuth } from "../auth/authContext.js";
import { ErrorNote, SectionCard, Spinner, Tag } from "../components/ui.jsx";

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    getUsers()
      .then((data) => setUsers(data.users || []))
      .catch((err) => {
        setError(err.message);
        setUsers([]);
      });
  }, []);

  const changeRole = async (target, role) => {
    setBusyId(target.id);
    setError("");
    try {
      await setUserRole(target.id, role);
      setUsers((list) => list.map((u) => (u.id === target.id ? { ...u, role } : u)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="view">
      <header>
        <p className="eyebrow">Admin</p>
        <h1 className="view-title">Users</h1>
      </header>

      <ErrorNote message={error} />

      <SectionCard
        eyebrow="Accounts"
        title={users ? `${users.length} user${users.length === 1 ? "" : "s"}` : "Loading…"}
        description="Promote a teammate to admin to share data-ops + user management. You can't remove your own admin."
      >
        {!users ? (
          <Spinner />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Joined</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = u.id === me?.id;
                const isAdmin = u.role === "admin";
                return (
                  <tr key={u.id}>
                    <td>
                      {u.email}
                      {isMe && <span className="muted"> (you)</span>}
                    </td>
                    <td>
                      <Tag tone={isAdmin ? "gold" : "neutral"}>{u.role}</Tag>
                    </td>
                    <td className="muted">{String(u.created_at || "").slice(0, 10) || "—"}</td>
                    <td>
                      <button
                        type="button"
                        className="chip"
                        disabled={busyId === u.id || (isAdmin && isMe)}
                        onClick={() => changeRole(u, isAdmin ? "user" : "admin")}
                        title={isAdmin && isMe ? "You can't demote yourself" : undefined}
                      >
                        {busyId === u.id ? "…" : isAdmin ? "Make user" : "Make admin"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </SectionCard>
    </div>
  );
}
