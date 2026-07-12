import { useEffect, useState } from "react";
import {
  deleteUser,
  getUsers,
  resetUserPassword,
  setRegistrationOpen,
  setUserRole,
} from "../api/client.js";
import { useAuth } from "../auth/authContext.js";
import { ConfirmDialog } from "../components/ConfirmDialog.jsx";
import { ErrorNote, SectionCard, Spinner, Tag } from "../components/ui.jsx";
import { UserAvatar } from "../components/UserAvatar.jsx";

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [tempReset, setTempReset] = useState(null); // { email, password } shown once
  const [deleteTarget, setDeleteTarget] = useState(null); // user pending delete confirm
  const [regOpen, setRegOpen] = useState(true);
  const [regBusy, setRegBusy] = useState(false);

  useEffect(() => {
    getUsers()
      .then((data) => {
        setUsers(data.users || []);
        if (typeof data.registration_open === "boolean") {
          setRegOpen(data.registration_open);
        }
      })
      .catch((err) => {
        setError(err.message);
        setUsers([]);
      });
  }, []);

  const toggleRegistration = async () => {
    setRegBusy(true);
    setError("");
    try {
      const result = await setRegistrationOpen(!regOpen);
      setRegOpen(Boolean(result.registration_open));
    } catch (err) {
      setError(err.message);
    } finally {
      setRegBusy(false);
    }
  };

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

  const removeUser = async (target) => {
    setBusyId(target.id);
    setError("");
    try {
      await deleteUser(target.id);
      setUsers((list) => list.filter((u) => u.id !== target.id));
      setDeleteTarget(null);
    } catch (err) {
      setError(err.message);
      setDeleteTarget(null);
    } finally {
      setBusyId(null);
    }
  };

  const resetPassword = async (target) => {
    setBusyId(target.id);
    setError("");
    setTempReset(null);
    try {
      const result = await resetUserPassword(target.id);
      setTempReset({ email: target.email, password: result.temp_password });
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
        <h1 className="view-title">User admin</h1>
      </header>

      <ErrorNote message={error} />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        danger
        title="Delete account"
        confirmLabel="Delete permanently"
        busy={busyId === deleteTarget?.id}
        body={`Delete ${deleteTarget?.display_name || deleteTarget?.email}?\n\nTheir account, picks, friendships, and profile picture are removed permanently. This cannot be undone.`}
        onConfirm={() => removeUser(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />

      <SectionCard eyebrow="Access" title="Registration">
        <div className="profile-toggle-row">
          <div>
            <div className="profile-toggle-label">{regOpen ? "Open" : "Paused"}</div>
            <div className="muted">
              {regOpen
                ? "Anyone with the link can create an account. Pause once your crew is in."
                : "Sign-ups are paused — only existing accounts can log in. Unpause any time."}
            </div>
          </div>
          <button
            type="button"
            className={`switch ${regOpen ? "on" : ""}`}
            onClick={toggleRegistration}
            disabled={regBusy}
            role="switch"
            aria-checked={regOpen}
            aria-label="Toggle registration"
          >
            <span className="switch-knob" />
          </button>
        </div>
      </SectionCard>

      {tempReset && (
        <SectionCard eyebrow="One-time reveal" title={`Temp password for ${tempReset.email}`}>
          <p>
            <code className="mono">{tempReset.password}</code>
          </p>
          <p className="muted">
            Send this to them out-of-band — it won't be shown again. They should change it
            from their profile after logging in.
          </p>
          <button type="button" className="chip" onClick={() => setTempReset(null)}>
            Dismiss
          </button>
        </SectionCard>
      )}

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
                <th>Last login</th>
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
                      <UserAvatar userId={u.id} size={22} className="friend-row-avatar" />
                      {u.email}
                      {isMe && <span className="muted"> (you)</span>}
                    </td>
                    <td>
                      <Tag tone={isAdmin ? "gold" : "neutral"}>{u.role}</Tag>
                    </td>
                    <td className="muted">{String(u.created_at || "").slice(0, 10) || "—"}</td>
                    <td className="muted">
                      {u.last_login_at
                        ? String(u.last_login_at).slice(0, 16).replace("T", " ")
                        : "never"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="chip"
                        disabled={busyId === u.id || (isAdmin && isMe)}
                        onClick={() => changeRole(u, isAdmin ? "user" : "admin")}
                        title={isAdmin && isMe ? "You can't demote yourself" : undefined}
                      >
                        {busyId === u.id ? "…" : isAdmin ? "Make user" : "Make admin"}
                      </button>{" "}
                      <button
                        type="button"
                        className="chip"
                        disabled={busyId === u.id}
                        onClick={() => resetPassword(u)}
                        title="Set a one-time temporary password"
                      >
                        Reset password
                      </button>{" "}
                      <button
                        type="button"
                        className="chip chip-danger"
                        disabled={busyId === u.id || isMe}
                        onClick={() => setDeleteTarget(u)}
                        title={isMe ? "You can't delete your own account" : "Delete account + picks permanently"}
                      >
                        Delete
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
