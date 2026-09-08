/**
 * BambooHR integration settings section  (AIQ-38-A)
 *
 * A self-contained card that HR admins embed in an integrations settings page.
 * Displays connection status, connect / disconnect actions, a live test button,
 * a manual sync trigger, and the last N sync log entries.
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Badge } from '../../antigravity/Badge'
import { Button } from '../../antigravity/Button'
import { Card } from '../../antigravity/Card'
import { Input } from '../../antigravity/Input'
import {
  connectBambooHR,
  disconnectBambooHR,
  getBambooHRStatus,
  getBambooHRSyncLog,
  syncBambooHR,
  testBambooHRConnection,
  type BambooHRStatus,
  type BambooHRSyncLogEntry,
} from '../../../api/bambooHR'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadge(status: BambooHRStatus['status']) {
  const map: Record<
    BambooHRStatus['status'],
    { label: string; variant: 'success' | 'error' | 'neutral' | 'warning' }
  > = {
    connected:      { label: 'Connected',      variant: 'success' },
    disconnected:   { label: 'Disconnected',   variant: 'neutral' },
    not_configured: { label: 'Not configured', variant: 'neutral' },
    error:          { label: 'Error',          variant: 'error'   },
  }
  const { label, variant } = map[status] ?? { label: status, variant: 'neutral' }
  return <Badge variant={variant}>{label}</Badge>
}

function syncStatusBadge(status: BambooHRSyncLogEntry['status']) {
  const map: Record<
    BambooHRSyncLogEntry['status'],
    'success' | 'error' | 'warning' | 'info'
  > = {
    running:   'info',
    completed: 'success',
    partial:   'warning',
    failed:    'error',
  }
  return <Badge variant={map[status] ?? 'neutral'} size="sm">{status}</Badge>
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const BambooHRSettingsSection: React.FC = () => {
  const [status, setStatus]       = useState<BambooHRStatus | null>(null)
  const [log, setLog]             = useState<BambooHRSyncLogEntry[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  // Connect form
  const [apiKey, setApiKey]       = useState('')
  const [subdomain, setSubdomain] = useState('')
  const [formError, setFormError] = useState('')

  // Action states
  const [connecting, setConnecting]     = useState(false)
  const [testing, setTesting]           = useState(false)
  const [syncing, setSyncing]           = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, l] = await Promise.all([
        getBambooHRStatus(),
        getBambooHRSyncLog(10),
      ])
      setStatus(s)
      setLog(l.entries)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load BambooHR status.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleConnect = async () => {
    setFormError('')
    if (!apiKey.trim())      return setFormError('API key is required.')
    if (!subdomain.trim())   return setFormError('Subdomain is required.')

    setConnecting(true)
    try {
      await connectBambooHR(apiKey.trim(), subdomain.trim())
      setApiKey('')
      setSubdomain('')
      await load()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Connection failed.')
    } finally {
      setConnecting(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    setError('')
    try {
      const result = await testBambooHRConnection()
      if (!result.ok) setError('Connection test failed. Check your credentials in BambooHR.')
      else setError('')
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Test failed.')
    } finally {
      setTesting(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setError('')
    try {
      await syncBambooHR()
      // Poll after 2 s to pick up the new log entry
      setTimeout(() => { void load() }, 2000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sync failed to start.')
    } finally {
      setSyncing(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect BambooHR? Stored credentials will be cleared.')) return
    setDisconnecting(true)
    try {
      await disconnectBambooHR()
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Disconnect failed.')
    } finally {
      setDisconnecting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const isConnected = status?.status === 'connected'

  return (
    <Card className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <img
            src="https://www.bamboohr.com/favicon.ico"
            alt="BambooHR"
            className="w-6 h-6"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          <div>
            <h3 className="text-lg font-semibold text-[#0b2b43]">BambooHR</h3>
            <p className="text-sm text-[#6b7280]">
              Automatically create relocation cases from BambooHR new hires.
            </p>
          </div>
        </div>
        {status && statusBadge(status.status)}
      </div>

      {/* Global error */}
      {error && (
        <div className="rounded-lg bg-[#f4e9e9] border border-[#e8c4c4] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      {loading && (
        <p className="text-sm text-[#6b7280]">Loading…</p>
      )}

      {!loading && (
        <>
          {/* ── Connected state ── */}
          {isConnected && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-[#6b7280]">Subdomain</span>
                  <p className="font-medium text-[#0b2b43]">
                    {status?.subdomain || '—'}
                    <span className="text-[#6b7280]">.bamboohr.com</span>
                  </p>
                </div>
                <div>
                  <span className="text-[#6b7280]">Last synced</span>
                  <p className="font-medium text-[#0b2b43]">
                    {formatDate(status?.last_sync_at ?? null)}
                  </p>
                </div>
              </div>

              {status?.last_error && (
                <p className="text-xs text-[#7a2a2a]">
                  Last error: {status.last_error}
                </p>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleTest}
                  disabled={testing}
                >
                  {testing ? 'Testing…' : 'Test connection'}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSync}
                  disabled={syncing}
                >
                  {syncing ? 'Starting sync…' : 'Sync now'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                >
                  {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                </Button>
              </div>
            </div>
          )}

          {/* ── Not connected state ── */}
          {!isConnected && (
            <div className="space-y-4">
              <p className="text-sm text-[#374151]">
                Enter your BambooHR API key and subdomain to connect. You can
                generate an API key in BambooHR under{' '}
                <strong>Account → API Keys</strong>.
              </p>

              <div className="space-y-3">
                <Input
                  label="API Key"
                  type="password"
                  value={apiKey}
                  onChange={setApiKey}
                  placeholder="Your BambooHR API key"
                  autoComplete="off"
                  fullWidth
                />
                <Input
                  label="Subdomain"
                  value={subdomain}
                  onChange={setSubdomain}
                  placeholder="yourcompany"
                  fullWidth
                />
                {subdomain && (
                  <p className="text-xs text-[#6b7280]">
                    Will connect to:{' '}
                    <span className="font-mono">
                      {subdomain}.bamboohr.com
                    </span>
                  </p>
                )}
                {formError && (
                  <p className="text-sm text-[#7a2a2a]">{formError}</p>
                )}
              </div>

              <Button
                variant="primary"
                onClick={handleConnect}
                disabled={connecting}
              >
                {connecting ? 'Connecting…' : 'Connect BambooHR'}
              </Button>
            </div>
          )}

          {/* ── Sync log ── */}
          {log.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-[#374151] mb-3">
                Recent syncs
              </h4>
              <div className="overflow-x-auto rounded-lg border border-[#e5e7eb]">
                <table className="min-w-full text-sm">
                  <thead className="bg-[#f9fafb]">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Started
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Type
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Status
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Found
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Created
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                        Errors
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e7eb]">
                    {log.map((entry) => (
                      <tr key={entry.id} className="bg-white hover:bg-[#f9fafb]">
                        <td className="px-4 py-2 text-[#374151] whitespace-nowrap">
                          {formatDate(entry.started_at)}
                        </td>
                        <td className="px-4 py-2 text-[#374151] capitalize">
                          {entry.sync_type}
                        </td>
                        <td className="px-4 py-2">
                          {syncStatusBadge(entry.status)}
                        </td>
                        <td className="px-4 py-2 text-right text-[#374151]">
                          {entry.new_hires_found}
                        </td>
                        <td className="px-4 py-2 text-right text-[#374151]">
                          {entry.cases_created}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {entry.error_count > 0 ? (
                            <span className="text-[#7a2a2a] font-medium">
                              {entry.error_count}
                            </span>
                          ) : (
                            <span className="text-[#6b7280]">0</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

export default BambooHRSettingsSection
