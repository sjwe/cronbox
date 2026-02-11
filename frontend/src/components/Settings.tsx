import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../context/AuthContext";
import { fetchAPIKeys, createAPIKey, revokeAPIKey } from "../api";
import type { APIKeyCreated } from "../types";

export default function Settings() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [expiresIn, setExpiresIn] = useState("30");
  const [newKey, setNewKey] = useState<APIKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: keys, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: fetchAPIKeys,
  });

  const createMut = useMutation({
    mutationFn: ({ name, days }: { name: string; days: number | null }) =>
      createAPIKey(name, days),
    onSuccess: (data) => {
      setNewKey(data);
      setShowForm(false);
      setKeyName("");
      setExpiresIn("30");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const revokeMut = useMutation({
    mutationFn: revokeAPIKey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  function handleCreate() {
    const days = expiresIn === "never" ? null : parseInt(expiresIn);
    createMut.mutate({ name: keyName, days });
  }

  async function handleCopy(key: string) {
    await navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Profile */}
      <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-lg font-semibold mb-4">Profile</h2>
        <div className="space-y-3 text-sm">
          <div className="flex gap-3">
            <span className="text-gray-400 w-24">Username</span>
            <span className="text-gray-100">{user?.username}</span>
          </div>
          <div className="flex gap-3">
            <span className="text-gray-400 w-24">Email</span>
            <span className="text-gray-100">{user?.email}</span>
          </div>
          <div className="flex gap-3">
            <span className="text-gray-400 w-24">Role</span>
            <span className="text-gray-100 capitalize">{user?.role}</span>
          </div>
        </div>
      </section>

      {/* API Keys */}
      <section className="rounded-lg border border-gray-800 bg-gray-900 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">API Keys</h2>
          <button
            onClick={() => { setShowForm(true); setNewKey(null); }}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition-colors"
          >
            Generate New Key
          </button>
        </div>

        {newKey && (
          <div className="mb-4 rounded-lg bg-gray-800 border border-gray-700 p-4">
            <p className="text-sm text-yellow-400 mb-2">This key will only be shown once.</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-sm text-gray-100 break-all">{newKey.key}</code>
              <button
                onClick={() => handleCopy(newKey.key)}
                className="rounded bg-gray-700 px-3 py-1 text-xs text-gray-300 hover:bg-gray-600 transition-colors"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>
        )}

        {showForm && (
          <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Key Name</label>
              <input
                type="text"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="e.g. CI pipeline"
                className="w-full rounded-md bg-gray-900 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Expires In</label>
              <select
                value={expiresIn}
                onChange={(e) => setExpiresIn(e.target.value)}
                className="w-full rounded-md bg-gray-900 border border-gray-700 px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="7">7 days</option>
                <option value="30">30 days</option>
                <option value="60">60 days</option>
                <option value="90">90 days</option>
                <option value="never">Never</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={!keyName || createMut.isPending}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
              >
                {createMut.isPending ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="rounded-md bg-gray-700 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {isLoading ? (
          <p className="text-gray-400 text-sm">Loading keys...</p>
        ) : keys && keys.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50 text-left text-gray-400">
                  <th className="px-4 py-2.5 font-medium">Prefix</th>
                  <th className="px-4 py-2.5 font-medium">Name</th>
                  <th className="px-4 py-2.5 font-medium">Expires</th>
                  <th className="px-4 py-2.5 font-medium">Last Used</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className="border-b border-gray-800/50">
                    <td className="px-4 py-2.5 font-mono text-gray-300">{k.key_prefix}...</td>
                    <td className="px-4 py-2.5 text-gray-300">{k.name}</td>
                    <td className="px-4 py-2.5 text-gray-400">
                      {k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-4 py-2.5 text-gray-400">
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={k.is_active ? "text-green-400" : "text-gray-500"}>
                        {k.is_active ? "Active" : "Revoked"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {k.is_active && (
                        <button
                          onClick={() => revokeMut.mutate(k.id)}
                          disabled={revokeMut.isPending}
                          className="rounded bg-red-500/15 px-2 py-0.5 text-xs text-red-400 hover:bg-red-500/25 transition-colors disabled:opacity-50"
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">No API keys yet.</p>
        )}
      </section>
    </div>
  );
}
