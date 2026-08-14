/**
 * AIQ-1743 — HR can see and copy the supplier magic link after dispatching.
 *
 * Before this, the link surfaced ONLY in the employee's inbox thread: dispatch posts it to
 * `quote_messages` under the employee's auth id, read by `list_quote_threads_for_employee`.
 * HR — who dispatches — had no surface for it (verified in prod on RFQ-20260727-29700a5f:
 * all 12 messages on the thread came from the employee, no HR participant).
 *
 * The backend already returned the link on every dispatch; `DispatchRfqTargetResult` simply
 * omitted the field, so HR's own client received it and discarded it. These tests pin:
 *   1. the links render and copy after a dispatch,
 *   2. nothing leaks BEFORE a dispatch (they are not fetched or persisted),
 *   3. a recipient whose mint failed shows no copy affordance,
 *   4. the email path surfaces links too (a skipped send still needs a relayable link),
 *   5. links are joined to nothing — a supplier-name collision cannot cross-wire credentials.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProviderCoordinationPanel } from '../ProviderCoordinationPanel'
import * as api from '../../api/hrCoordination'

vi.mock('../../api/hrCoordination', async () => {
  const actual = await vi.importActual<typeof api>('../../api/hrCoordination')
  return {
    ...actual,
    getCaseProviders: vi.fn(),
    getCaseRfqs: vi.fn(),
    dispatchCaseRfq: vi.fn(),
  }
})

const CASE_ID = 'c7f5f1e4-edfe-4f82-bc7c-5d92f3cbc662'
const RFQ_ID = '29700a5f-6cdd-456f-a770-2ff5e3104933'
const LINK_A = 'https://relopass.com/supplier/quote?token=tokA'
const LINK_B = 'https://relopass.com/supplier/quote?token=tokB'

const RFQ: api.CaseRfq = {
  id: RFQ_ID,
  rfq_ref: 'RFQ-20260727-29700a5f',
  case_id: CASE_ID,
  status: 'open',
  created_at: '2026-07-27T12:59:40Z',
  service_keys: ['movers'],
  recipients: [
    { supplier_id: 's-o1', supplier_name: 'Nordic Movers AS', status: 'sent', last_activity_at: null },
    { supplier_id: 's-o2', supplier_name: 'Oslo Relocation', status: 'sent', last_activity_at: null },
  ],
}

const writeText = vi.fn().mockResolvedValue(undefined)

/**
 * userEvent.setup() installs its OWN navigator.clipboard stub, so our spy has to be defined
 * after it or the copy assertions see zero calls. jsdom also exposes clipboard as getter-only,
 * hence defineProperty rather than Object.assign.
 */
function setupUser() {
  const user = userEvent.setup()
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
    writable: true,
  })
  return user
}

function renderPanel() {
  return render(
    <MemoryRouter>
      <ProviderCoordinationPanel caseId={CASE_ID} />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getCaseProviders).mockResolvedValue([])
  vi.mocked(api.getCaseRfqs).mockResolvedValue([RFQ])
})

describe('AIQ-1743 · HR-visible supplier magic links', () => {
  it('shows no link before a dispatch — they are never fetched or stored', async () => {
    renderPanel()
    await screen.findByText('Nordic Movers AS')

    expect(screen.queryByText('Supplier links from this dispatch')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /copy link/i })).not.toBeInTheDocument()
    // getCaseRfqs is the only read on mount, and it cannot carry a link (server stores a hash).
    expect(api.dispatchCaseRfq).not.toHaveBeenCalled()
  })

  it('renders a copy button per recipient after dispatch and copies the exact link', async () => {
    vi.mocked(api.dispatchCaseRfq).mockResolvedValue({
      ok: true,
      rfq_id: RFQ_ID,
      dispatched: 2,
      results: [
        { recipient_id: 'r1', supplier_name: 'Nordic Movers AS', ok: true, sent: false, link: LINK_A },
        { recipient_id: 'r2', supplier_name: 'Oslo Relocation', ok: true, sent: false, link: LINK_B },
      ],
    })

    const user = setupUser()
    renderPanel()
    await user.click(await screen.findByRole('button', { name: /dispatch to suppliers/i }))

    await screen.findByText('Supplier links from this dispatch')
    const buttons = await screen.findAllByRole('button', { name: /copy link/i })
    expect(buttons).toHaveLength(2)

    await user.click(buttons[0])
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(LINK_A))
    // the second row must carry the OTHER supplier's link, never a repeat of the first
    await user.click(buttons[1])
    await waitFor(() => expect(writeText).toHaveBeenLastCalledWith(LINK_B))
  })

  it('omits the copy affordance for a recipient whose link could not be minted', async () => {
    vi.mocked(api.dispatchCaseRfq).mockResolvedValue({
      ok: true,
      rfq_id: RFQ_ID,
      dispatched: 2,
      results: [
        { recipient_id: 'r1', supplier_name: 'Nordic Movers AS', ok: true, sent: false, link: LINK_A },
        {
          recipient_id: 'r2',
          supplier_name: 'Oslo Relocation',
          ok: false,
          sent: false,
          error: 'could not create the link',
        },
      ],
    })

    const user = setupUser()
    renderPanel()
    await user.click(await screen.findByRole('button', { name: /dispatch to suppliers/i }))

    await screen.findByText('Supplier links from this dispatch')
    expect(await screen.findAllByRole('button', { name: /copy link/i })).toHaveLength(1)
  })

  it('surfaces links from the email path too — a skipped send still needs a relayable link', async () => {
    vi.mocked(api.dispatchCaseRfq).mockResolvedValue({
      ok: true,
      rfq_id: RFQ_ID,
      dispatched: 2,
      results: [
        { recipient_id: 'r1', supplier_name: 'Nordic Movers AS', ok: true, sent: false, error: 'no verified address', link: LINK_A },
        { recipient_id: 'r2', supplier_name: 'Oslo Relocation', ok: true, sent: true, link: LINK_B },
      ],
    })

    const user = setupUser()
    renderPanel()
    await user.click(await screen.findByRole('button', { name: /^email suppliers$/i }))
    await user.click(await screen.findByRole('button', { name: /confirm: email/i }))

    await screen.findByText('Supplier links from this dispatch')
    expect(await screen.findAllByRole('button', { name: /copy link/i })).toHaveLength(2)
  })

  it('does not cross-wire credentials when two suppliers share a display name', async () => {
    // The regression this guards: dispatch results key on recipient_id while rfq.recipients
    // key on supplier_id, so the only shared field is the name. Joining on it would hand
    // supplier A's bearer token to supplier B. The links render from the dispatch's own list.
    vi.mocked(api.dispatchCaseRfq).mockResolvedValue({
      ok: true,
      rfq_id: RFQ_ID,
      dispatched: 2,
      results: [
        { recipient_id: 'r1', supplier_name: 'Movers AS', ok: true, sent: false, link: LINK_A },
        { recipient_id: 'r2', supplier_name: 'Movers AS', ok: true, sent: false, link: LINK_B },
      ],
    })

    const user = setupUser()
    renderPanel()
    await user.click(await screen.findByRole('button', { name: /dispatch to suppliers/i }))

    const buttons = await screen.findAllByRole('button', { name: /copy link/i })
    expect(buttons).toHaveLength(2)
    await user.click(buttons[0])
    await waitFor(() => expect(writeText).toHaveBeenLastCalledWith(LINK_A))
    await user.click(buttons[1])
    await waitFor(() => expect(writeText).toHaveBeenLastCalledWith(LINK_B))
  })
})
