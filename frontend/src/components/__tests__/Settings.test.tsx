import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../../context/AuthContext";
import Settings from "../Settings";

const mockFetch = vi.fn();
const store: Record<string, string> = {};
const mockStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, val: string) => { store[key] = val; }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
  clear: vi.fn(() => { for (const k in store) delete store[k]; }),
  get length() { return Object.keys(store).length; },
  key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
};

const meResponse = { id: 1, username: "testuser", email: "test@example.com", role: "operator" };

function renderSettings() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>
          <Settings />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("localStorage", mockStorage);
  store["cronbox_token"] = "test-token";
});

afterEach(() => {
  vi.restoreAllMocks();
  delete store["cronbox_token"];
});

describe("Settings", () => {
  it("renders user profile", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(meResponse) });
      }
      if (url === "/api/keys") {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      return Promise.resolve({ ok: false, status: 404, statusText: "Not Found" });
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("testuser")).toBeDefined();
      expect(screen.getByText("test@example.com")).toBeDefined();
      expect(screen.getByText("operator")).toBeDefined();
    });
  });

  it("renders API key list", async () => {
    const keys = [
      {
        id: 1,
        key_prefix: "cb_abc",
        name: "CI key",
        expires_at: "2026-03-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
        last_used_at: null,
        is_active: true,
      },
    ];

    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(meResponse) });
      }
      if (url === "/api/keys") {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(keys) });
      }
      return Promise.resolve({ ok: false, status: 404, statusText: "Not Found" });
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("CI key")).toBeDefined();
      expect(screen.getByText("cb_abc...")).toBeDefined();
    });
  });

  it("shows new key with copy button on create", async () => {
    let keysCreated = false;

    mockFetch.mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/auth/me") {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(meResponse) });
      }
      if (url === "/api/keys" && (!init || init.method !== "POST")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      if (url === "/api/keys" && init?.method === "POST") {
        keysCreated = true;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              id: 2,
              key: "cb_full_secret_key_here",
              key_prefix: "cb_full",
              name: "My Key",
              expires_at: "2026-03-01T00:00:00Z",
              created_at: "2026-02-01T00:00:00Z",
              last_used_at: null,
              is_active: true,
            }),
        });
      }
      return Promise.resolve({ ok: false, status: 404, statusText: "Not Found" });
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText("Generate New Key")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Generate New Key"));

    const nameInput = screen.getByPlaceholderText("e.g. CI pipeline");
    fireEvent.change(nameInput, { target: { value: "My Key" } });
    fireEvent.click(screen.getByText("Create"));

    await waitFor(() => {
      expect(keysCreated).toBe(true);
      expect(screen.getByText("cb_full_secret_key_here")).toBeDefined();
      expect(screen.getByText("Copy")).toBeDefined();
      expect(screen.getByText("This key will only be shown once.")).toBeDefined();
    });
  });
});
