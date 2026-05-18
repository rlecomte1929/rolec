/**
 * Personio integration settings section  (AIQ-33-B)
 *
 * Self-contained card for HR admins — connect via client_id + client_secret,
 * manual sync, disconnect, field-mapping editor, and sync log table.
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Badge } from '../../antigravity/Badge'
import { Button } from '../../antigravity/Button'
import { Card } from '../../antigravity/Card'
import { Input } from '../../antigravity/Input'
import {
  connectPersonio,
  disconnectPersonio,
  getPersonioFieldMappings,
  getPersonioStatus,
  getPersonioSyncLog,
  syncPersonio,
  updatePersonioFieldMappings,
  type PersonioStatus,
  type PersonioSyncLogEntry,
} from '../../../api/personio'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadge(status: PersonioStatus['status']) {
  const map: Record<
    PersonioStatus['status'],
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

function syncStatusBadge(status: PersonioSyncLogEntry['status']) {
  const map: Record<
    PersonioSyncLogEntry['status'],
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

export const PersonioSettingsSection: React.FC = () => {
  const [status, setStatus]       = useState<PersonioStatus | null>(null)
  const [log, setLog]             = useState<PersonioSyncLogEntry[]>([])
  const [mappings, setMappings]   = useState<Record<string, string>>({})
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')

  // Connect form
  const [clientId, setClientId]         = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [formError, setFormError]       = useState('')

  // Mapping editor
  const [editedMappings, setEditedMappings] = useState<Record<string, string>>({})
  const [mappingsDirty, setMappingsDirty]   = useState(false)
  const [savingMappings, setSavingMappings] = useState(false)

  // Action states
  const [connecting, setConnecting]       = useState(false)
  const [syncing, setSyncing]             = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, l, m] = await Promise.all([
        getPersonioStatus(),
        getPersonioSyncLog(10),
        getPersonioFieldMappings(),
      ])
      setStatus(s)
      setLog(l.entries)
      setMappings(m.mappings)
      setEditedMappings(m.mappings)
      setMappingsDirty(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load Personio status.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const handleConnect = async () => {
    setFormError('')
    if (!clientId.trim())     return setFormError('Client ID is required.')
    if (!clientSecret.trim()) return setFormError('Client secret is required.')

    setConnecting(true)
    try {
      await connectPersonio(clientId.trim(), clientSecret.trim())
      setClientId('')
      setClientSecret('')
      await load()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Connection failed.')
    } finally {
      setConnecting(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setError('')
    try {
      await syncPersonio()
      setTimeout(() => { void load() }, 2000)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sync failed to start.')
    } finally {
      setSyncing(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Disconnect Personio? Stored credentials will be cleared.')) return
    setDisconnecting(true)
    try {
      await disconnectPersonio()
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Disconnect failed.')
    } finally {
      setDisconnecting(false)
    }
  }

  const handleMappingChange = (key: string, value: string) => {
    const next = { ...editedMappings, [key]: value }
    setEditedMappings(next)
    setMappingsDirty(JSON.stringify(next) !== JSON.stringify(mappings))
  }

  const handleSaveMappings = async () => {
    setSavingMappings(true)
    try {
      await updatePersonioFieldMappings(editedMappings)
      setMappings(editedMappings)
      setMappingsDirty(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save mappings.')
    } finally {
      setSavingMappings(false)
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
            src="https://www.personio.com/favicon.ico"
            alt="Personio"
            className="w-6 h-6"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          <div>
            <h3 className="text-lg font-semibold text-[#0b2b43]">Personio</h3>
            <p className="text-sm text-[#6b7280]">
              Automatically create relocation cases from Personio new hires.
            </p>
          </div>
        </div>
        {status && statusBadge(status.status)}
      </div>

      {error && (
        <div className="rounded-lg bg-[#f4e9e9] border border-[#e8c4c4] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-[#6b7280]">Loading…</p>}

      {!loading && (
        <>
          {/* ── Connected ── */}
          {isConnected && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-[#6b7280]">Last synced</span>
                  <p className="font-medium text-[#0b2b43]">
                    {formatDate(status?.last_sync_at ?? null)}
                  </p>
                </div>
                {status?.last_error && (
                  <div>
                    <span className="text-[#6b7280]">Last error</span>
                    <p className="text-xs text-[#7a2a2a]">{status.last_error}</p>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button variant="primary" size="sm" onClick={handleSync} disabled={syncing}>
                  {syncing ? 'Starting sync…' : 'Sync now'}
                </Button>
                <Button variant="outline" size="sm" onClick={handleDisconnect} disabled={disconnecting}>
                  {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                </Button>
              </div>
            </div>
          )}

          {/* ── Not connected ── */}
          {!isConnected && (
            <div className="space-y-4">
              <p className="text-sm text-[#374151]">
                Enter your Personio API credentials. You can find them in Personio under{' '}
                <strong>Settings → API → API Credentials</strong>.
              </p>
              <div className="space-y-3">
                <Input
                  label="Client ID"
                  value={clientId}
                  onChange={setClientId}
                  placeholder="Your Personio client ID"
                  autoComplete="off"
                  fullWidth
                />
                <Input
                  label="Client Secret"
                  type="password"
                  value={clientSecret}
                  onChange={setClientSecret}
                  placeholder="Your Personio client secret"
                  autoComplete="off"
                  fullWidth
                />
                {formError && <p className="text-sm text-[#7a2a2a]">{formError}</p>}
              </div>
              <Button variant="primary" onClick={handleConnect} disabled={connecting}>
                {connecting ? 'Connecting…' : 'Connect Personio'}
              </Button>
            </div>
          )}

          {/* ── Field mappings (connected only) ── */}
          {isConnected && Object.keys(editedMappings).length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-[#374151]">Field mappings</h4>
                {mappingsDirty && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleSaveMappings}
                    disabled={savingMappings}
                  >
                    {savingMappings ? 'Saving…' : 'Save changes'}
                  </Button>
                )}
              </div>
              <div className="overflow-x-auto rounded-lg border border-[#e5e7eb]">
                <table className="min-w-full text-sm">
                  <thead className="bg-[#f9fafb]">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide w-1/2">
                        Personio field
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide w-1/2">
                        ReloPass field
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e7eb]">
                    {Object.entries(editedMappings).map(([personioField, relopassField]) => (
                      <tr
                        key={personioField}
                        className={`bg-white ${
                          editedMappings[personioField] !== mappings[personioField]
                            ? 'bg-[#fffbeb]'
                            : ''
                        }`}
                      >
                        <td className="px-4 py-2 font-mono text-xs text-[#374151]">
                          {personioField}
                        </td>
                        <td className="px-4 py-2">
                          <input
                            type="text"
                            value={relopassField}
                            onChange={(e) => handleMappingChange(personioField, e.target.value)}
                            className="w-full px-2 py-1 text-xs border border-[#d1d5db] rounded focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Sync log ── */}
          {log.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-[#374151] mb-3">Recent syncs</h4>
              <div className="overflow-x-auto rounded-lg border border-[#e5e7eb]">
                <table className="min-w-full text-sm">
                  <thead className="bg-[#f9fafb]">
                    <tr>
                      {['Started', 'Type', 'Status', 'Found', 'Created', 'Errors'].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide last:text-right"
                        >
                          {h}
                        </th>
                      ))}
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
                        <td className="px-4 py-2">{syncStatusBadge(entry.status)}</td>
                        <td className="px-4 py-2 text-right text-[#374151]">
                          {entry.new_hires_found}
                        </td>
                        <td className="px-4 py-2 text-right text-[#374151]">
                          {entry.cases_created}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {entry.error_count > 0 ? (
                            <span className="text-[#7a2a2a] font-medium">{entry.error_count}</span>
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

export default PersonioSettingsSection
