import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
vi.mock("../../api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));
import apiClient from "../../api/client";
import AdminAuditLogPage from "./AdminAuditLogPage";

const mockGet = (apiClient as { get: ReturnType<typeof vi.fn> }).get;

describe("AdminAuditLogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading", async () => {
    mockGet.mockResolvedValue({ data: { items: [], limit: 50, offset: 0 } });
    render(<AdminAuditLogPage />);
    expect(screen.getByText("Platform Audit Log")).toBeDefined();
    await waitFor(() => expect(screen.getByText("No audit log entries.")).toBeDefined());
  });

  it("renders audit log entries", async () => {
    mockGet.mockResolvedValue({
      data: {
        items: [
          {
            id: "log-001",
            entity_type: "admin_allowlist",
            entity_id: "eid-1",
            action_type: "update",
            new_value: { event: "admin_added", email: "a@b.com" },
            actor_id: "actor-1",
            created_at: "2026-06-01T10:00:00",
          },
        ],
        limit: 50,
        offset: 0,
      },
    });
    render(<AdminAuditLogPage />);
    await waitFor(() => expect(screen.getByText("admin_added")).toBeDefined());
    expect(screen.getByText("admin_allowlist")).toBeDefined();
  });
});
