import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
// Mock the api client to avoid supabase import trap
vi.mock("../../api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));
import apiClient from "../../api/client";
import AdminAdminsPage from "./AdminAdminsPage";

const mockApiClient = apiClient as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
};

describe("AdminAdminsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading and add form", async () => {
    mockApiClient.get.mockResolvedValue({ data: { items: [] } });
    render(<AdminAdminsPage />);
    expect(screen.getByText("Admin Accounts")).toBeDefined();
    await waitFor(() => expect(screen.getByText("No admins yet.")).toBeDefined());
  });

  it("lists admins from API", async () => {
    mockApiClient.get.mockResolvedValue({
      data: {
        items: [
          { email: "admin@example.com", enabled: true, added_by_user_id: null, created_at: "2026-06-01T00:00:00" },
        ],
      },
    });
    render(<AdminAdminsPage />);
    await waitFor(() => expect(screen.getByText("admin@example.com")).toBeDefined());
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("shows disabled badge for disabled admin", async () => {
    mockApiClient.get.mockResolvedValue({
      data: {
        items: [
          { email: "off@example.com", enabled: false, added_by_user_id: null, created_at: "2026-06-01T00:00:00" },
        ],
      },
    });
    render(<AdminAdminsPage />);
    await waitFor(() => expect(screen.getByText("Disabled")).toBeDefined());
  });
});
