import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import { fetchUsers, createUser, updateUser, deleteUser } from "../api";

export default function AdminUsers() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<{ username: string; email: string; password: string; role: "admin" | "operator" | "viewer" }>({ username: "", email: "", password: "", role: "viewer" });

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchUsers,
  });

  const createMut = useMutation({
    mutationFn: () => createUser(formData.username, formData.email, formData.password, formData.role),
    onSuccess: () => {
      setShowForm(false);
      setFormData({ username: "", email: "", password: "", role: "viewer" });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: Record<string, unknown> }) =>
      updateUser(id, updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  if (user?.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">User Management</h1>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
        >
          Add User
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold">Create User</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Username</label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Role</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value as "admin" | "operator" | "viewer" })}
                className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMut.mutate()}
              disabled={!formData.username || !formData.email || !formData.password || createMut.isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
            >
              {createMut.isPending ? "Creating..." : "Create User"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-400 py-12 text-center">Loading users...</div>
      ) : users && users.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/50 text-left text-gray-400">
                <th className="px-4 py-3 font-medium">Username</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-gray-800/50 hover:bg-gray-900/30">
                  <td className="px-4 py-3 font-medium text-gray-100">{u.username}</td>
                  <td className="px-4 py-3 text-gray-300">{u.email}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      onChange={(e) =>
                        updateMut.mutate({ id: u.id, updates: { role: e.target.value } })
                      }
                      className="rounded bg-gray-800 border border-gray-700 px-2 py-1 text-xs text-gray-100 focus:outline-none"
                    >
                      <option value="viewer">Viewer</option>
                      <option value="operator">Operator</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() =>
                        updateMut.mutate({ id: u.id, updates: { is_active: !u.is_active } })
                      }
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        u.is_active
                          ? "bg-green-500/15 text-green-400"
                          : "bg-gray-500/15 text-gray-400"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => {
                        if (confirm(`Delete user ${u.username}?`)) {
                          deleteMut.mutate(u.id);
                        }
                      }}
                      disabled={u.id === user?.id}
                      className="rounded bg-red-500/15 px-2 py-0.5 text-xs text-red-400 hover:bg-red-500/25 transition-colors disabled:opacity-30"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-gray-500 py-12 text-center">No users found.</div>
      )}
    </div>
  );
}
