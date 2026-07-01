# App Integration Manifest

Before building any app feature, check this manifest. Use platform integrations instead of reinventing functionality. Every integration listed here is already deployed and available to your app via simple fetch() calls.

If your runtime exposes `get_integration_docs`, prefer `get_integration_docs({ integrationName: "stripe-payments" })` for full API details and working code examples.
Otherwise, read `integrations/{id}/docs.md` by file path.

---

## Quick Lookup: "I need X, which integration do I use?"

| I need to... | Use this integration |
|---|---|
| Accept payments or subscriptions | `stripe-payments` |
| Make AI phone calls | `ai-phone-calls` |
| Send emails | `task-scheduler` |
| Schedule tasks or recurring jobs | `task-scheduler` |
| Search the web | `web-search` |
| Scrape websites or social media | `web-scraping` |
| Generate text with AI (chatbot, content) | `openai-text-generation` |
| Real-time voice conversation with AI | `openai-realtime` |
| Text-to-speech or music generation | `elevenlabs-audio` |
| Analyze images | `gemini-vision-transform` |
| Analyze or summarize videos | `gemini-video-understanding` |
| Generate images or videos with AI | `google-veo3` |
| Add an animated avatar or interactive Rive animation | `rive-animation` |
| Generate avatar videos with HeyGen | `heygen-video` |
| Generate 3D models from text or images | `meshy-3d` |
| Analyze PDFs or documents | `document-analysis` |
| Transcribe audio/speech to text | `audio-transcription` |
| User authentication and sessions | `session-management` |
| Upload and store files/images | `file-storage` |
| Upload arbitrary binary files (video, PDF, audio) | `file-storage` |
| Extract frames from a video | `video-frames` |
| Trim or clip a video segment | `video-clip` |
| Render a custom video composition (Remotion) | `remotion-rendering` |
| Find royalty-free stock photos | `stock-photos` |
| Social feeds, posts, reactions, presence | `workspace-community` |
| Sell print-on-demand merchandise | `printify-products` |
| Run server-side logic (webhooks, hooks) | `server-functions` |
| Create public standalone pages | `permalink-pages` |
| Receive and process inbound emails | `inbound-email` |
| Automated email drip campaigns | `email-sequences` |
| Request human-in-the-loop tasks | `human-tasks` |
| Tag and segment CRM contacts | `crm-tags` |
| Search B2B leads | `apollo-leads` |
| Post to Slack channels | `slack` |
| Launch or manage Meta (Facebook/Instagram) ad campaigns | `meta-ads` |
| Connect a Meta / Facebook / Instagram account (in-app OAuth, connect-only) | `connect-meta` |
| Connect a Meta ad account in-app (with ads/launch surface) | `meta-ads` |
| Connect LinkedIn or Instagram in-app, then post | `social-publishing` |
| Publish posts to LinkedIn or Instagram | `social-publishing` |
| Track funnel/conversion events (Google Tag Manager, analytics) | `funnel-analytics` |

---

## Integration Reference

### ai-phone-calls
**Category:** Communication / Voice
Make and receive AI-powered phone calls on behalf of workspace customers using Retell AI or ElevenLabs.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/workspaces/:workspaceId/phone/config` | Get Phone Config |
| `POST /api/workspaces/:workspaceId/phone/agents` | Create an Agent |
| `GET /api/workspaces/:workspaceId/phone/agents` | List Agents |
| `GET /api/workspaces/:workspaceId/phone/agents/:agentId` | Get a Specific Agent |
| `PATCH /api/workspaces/:workspaceId/phone/agents/:agentId` | Update an Agent's Prompt |
| `DELETE /api/workspaces/:workspaceId/phone/agents/:agentId` | Delete an Agent |

```
GET /api/workspaces/:workspaceId/phone/config
```

---

### alibaba-suppliers
**Category:** E-commerce / Sourcing
Find products and suppliers on Alibaba for any product idea. Search returns the product listing title, price range, a thumbnail image, and a link out to the Alibaba product page — everything an app needs to surface real sourcing options for a product idea.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/suppliers/search` | API Endpoint |

```
POST /api/suppliers/search
```

---

### apollo-leads
**Category:** General
Search, enrich, and manage leads using Apollo.io's comprehensive B2B contact database. Find potential customers, partners, or media contacts for outreach.

```typescript
const response = await fetch('/api/leads/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'marketing automation',
    personTitles: ['VP Marketing', 'CMO', 'Director of Marketing'],
    personSeniorities: ['director', 'vp', 'c_suite'],
    includeSimilarTitles: true,
    limit: 25
  })
});

const { people, pagination } = await response.json();
// people[] contains name, title, company, email (if available), etc.
```

---

### audio-transcription
**Category:** AI/ML
Record audio and convert speech to text using OpenAI's GPT-4o Transcribe model. Simple POST endpoint for record-then-send transcription workflows.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/generate/transcribe` | API Endpoint |

```
POST /api/generate/transcribe
```

---

### connect-meta
**Category:** Marketing
Form, read, and clear the workspace's Meta (Facebook/Instagram) connection from

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/marketing/connect/init` | Start the OAuth flow |
| `GET /api/workspaces/:workspaceId/marketing/connect/status` | Read connection status |
| `POST /api/workspaces/:workspaceId/marketing/connect/disconnect` | Disconnect |

```tsx
const ws = (window as any).__workspaceDb;
const base = `/api/workspaces/${ws.workspaceId}/marketing`;
const auth = { 'X-Workspace-DB-Token': ws.token };

// 1. Is an account already connected?
const { connected } = await fetch(`${base}/connect/status`, { headers: auth }).then((r) => r.json());

// 2. If not, start the OAuth flow and open the returned URL, then poll status.
if (!connected) {
  const { authUrl } = await fetch(`${base}/connect/init`, {
    method: 'POST',
    headers: { ...auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({}), // all scopes by default
  }).then((r) => r.json());
  window.open(authUrl, '_blank');
}
```

---

### crm-tags
**Category:** CRM
Manage contact and session tags for organizing and triggering automated boosters.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspace-tags/:workspaceId` | Create a Tag |
| `GET /api/workspace-tags/:workspaceId` | List All Tags |
| `POST /api/entity-tags/contacts/:contactId/tags?workspaceId=:workspaceId` | Apply Tag to Contact |
| `POST /api/entity-tags/sessions/:sessionId/tags?workspaceId=:workspaceId` | Apply Tag to Session |
| `GET /api/entity-tags/contacts/:contactId/tags?workspaceId=:workspaceId` | Get Contact Tags |
| `GET /api/entity-tags/sessions/:sessionId/tags?workspaceId=:workspaceId&includeInherited=true` | Get Session Tags |

```
POST /api/workspace-tags/:workspaceId
```

---

### document-analysis
**Category:** AI/ML
Analyze images and PDFs with GPT-4 vision - extract data from invoices, forms, diagrams, and more. Supports native PDF processing (up to 100 pages, 32MB max).

| Endpoint | Purpose |
|----------|--------|
| `POST /api/analyze-document` | API Endpoint |

```
POST /api/analyze-document
```

---

### domain-registration
**Category:** General
Wallet-gated, idempotent purchase of new apex domains through DNSimple,

```json
{
  "domain": "myapp.com",
  "userConfirmed": true,
  "idempotencyKey": "optional-stable-key"
}
```

---

### elevenlabs-audio
**Category:** AI / Audio
Generate natural-sounding speech from text and create AI background music. Powered by ElevenLabs with 30+ premium voices and 8 music presets.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/voices` | List Available Voices |
| `POST /api/workspaces/:workspaceId/demo-video/voiceover` | Generate Speech |
| `POST /api/workspaces/:workspaceId/demo-video/voiceover/segments` | Generate Segmented Speech |
| `GET /music/presets` | List Music Presets |
| `POST /api/workspaces/:workspaceId/demo-video/music/preset` | Generate Music from Preset |
| `POST /api/workspaces/:workspaceId/demo-video/music/custom` | Generate Custom Music |

```
GET /api/voices
```

---

### email-sequences
**Category:** Marketing / Automation
Create multi-step automated email campaigns triggered by events, schedules, or manual actions.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/email-sequences` | Create a Sequence |
| `GET /api/workspaces/:workspaceId/email-sequences` | List Sequences |
| `GET /api/workspaces/:workspaceId/email-sequences/:sequenceId` | Get Sequence Details |
| `PATCH /api/workspaces/:workspaceId/email-sequences/:sequenceId` | Update a Sequence |
| `DELETE /api/workspaces/:workspaceId/email-sequences/:sequenceId` | Delete a Sequence |
| `POST /api/workspaces/:workspaceId/email-sequences/:sequenceId/pause` | Pause / Resume a Sequence |

```
POST /api/workspaces/:workspaceId/email-sequences
```

---

### file-storage
**Category:** Storage
Permanently store images and files in Google Cloud Storage with public URLs.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/upload/image` | Upload Image (base64 JSON) |
| `POST /api/upload/file` | Upload Any File (multipart binary) |

```
POST /api/upload/image
```

---

### funnel-analytics
**Category:** Analytics & Tracking
Fire conversion / funnel events from your Space app into Google Tag Manager (and any tools wired through it) using the always-available `window.trackFunnelEvent` helper.


---

### gemini-video-understanding
**Category:** AI/ML
Analyze videos with Google's Gemini API to extract insights, summarize content, answer questions, and reference specific timestamps.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/generate/video-analysis` | 1. Analyze Video (File Upload for videos >20MB) |
| `POST /api/generate/video-inline` | 2. Analyze Video (Inline for videos <20MB) |
| `POST /api/generate/video-youtube` | 3. Analyze YouTube Video |

```
POST /api/generate/video-analysis
```

---

### gemini-vision-transform
**Category:** General
Analyze images with Gemini Vision and transform them into new styles (line art, stylization, etc.) using AI-powered image-to-image processing.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/generate/vision` | 1. Vision Analysis — Describe or analyze an image |
| `POST /api/generate/image-to-image` | 2. Image-to-Image — Transform an image into a new style |

```
POST /api/generate/vision
```

---

### google-veo3
**Category:** AI/ML
Generate AI-powered videos and images using Google Veo (2 / 3 / 3.1), Gemini 2.5 Flash, or OpenAI DALL-E 3.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/generate/image` | API Endpoints |
| `POST /api/veo/generate/video` |  |
| `POST /api/generate/video` |  |
| `GET /api/veo/status/:operationId` |  |
| `POST /api/veo/generate-long-video` |  |
| `GET /api/veo/status-long-video/:jobId` |  |

```
POST /api/generate/image
```

---

### heygen-video
**Category:** AI / Video
Generate avatar and prompt-driven videos with HeyGen while keeping the workspace's HeyGen API key out of app code and browser bundles.

| Endpoint | Purpose |
|----------|--------|
| `PUT /api/workspaces/:workspaceId/provider-credentials/heygen` |  |
| `POST /api/workspaces/:workspaceId/provider-credentials/heygen/proxy/v3/videos` | Create an Avatar Video |
| `POST /api/workspaces/:workspaceId/provider-credentials/heygen/proxy/v3/video-agents` | Create a Prompt-Driven Video Agent Session |
| `GET /api/workspaces/:workspaceId/provider-credentials/heygen/proxy/v3/video-agents/:sessionId` |  |
| `GET /api/workspaces/:workspaceId/provider-credentials/heygen/proxy/v3/videos/:videoId` | Get Generated Video Status |

```tsx
const workspaceId = (window as any).__WORKSPACE_ID__;

async function heygen(path: string, init?: RequestInit) {
  const res = await fetch(
    `/api/workspaces/${workspaceId}/provider-credentials/heygen/proxy/${path.replace(/^\/+/, "")}`,
    {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    },
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error || data?.message || "HeyGen request failed");
  return data;
}

const created = await heygen("v3/videos", {
  method: "POST",
  body: JSON.stringify({
    type: "avatar",
    avatar_id: "YOUR_AVATAR_ID",
    engine: { type: "avatar_v" },
    script: "Welcome to ReelPilot.",
    voice_id: "YOUR_VOICE_ID",
  }),
});

const videoId = created.data?.id || created.id;
const status = await heygen(`v3/videos/${videoId}`);
```

---

### human-tasks
**Category:** General
Request, approve, track, and complete human tasks with wallet-based budgeting. Tasks go through an approval workflow before being posted to Slack.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/human-tasks?workspaceId={workspaceId}` | List Tasks |
| `GET /api/workspace/{workspaceId}/human-tasks` | List Tasks |
| `POST /api/human-tasks` | Create Task |
| `POST /api/workspace/{workspaceId}/human-tasks` | Create Task |
| `POST /api/human-tasks/{taskId}/approve` | Approve Task |
| `POST /api/workspace/{workspaceId}/human-tasks/{taskId}/approve` | Approve Task |

```
GET /api/human-tasks?workspaceId={workspaceId}
GET /api/workspace/{workspaceId}/human-tasks
```

---

### image-and-video-generation
**Category:** General
Unified reference for the image and video generation endpoints exposed to apps built on the platform. The platform proxies requests to Google Veo, OpenAI Sora, OpenAI DALL-E 3, and Gemini Flash Image so apps don't have to manage provider keys themselves.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/veo/status/:operationId` | Polling |

```json
{
  "success": true,
  "generationId": "gen_abc123",
  "operationId": "operations/...",
  "status": "processing",
  "progress": 10,
  "cost": "0.40",
  "estimatedDuration": "1-3 minutes",
  "message": "Video generation started. Use the operationId to check status."
}
```

---

### inbound-email
**Category:** Communication
Receive, process, and auto-respond to emails on behalf of workspace customers using Mailgun inbound routing and server functions.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/emails/send` | Send an Email |
| `GET /api/workspaces/:workspaceId/emails` | List Email Messages |
| `GET /api/workspaces/:workspaceId/emails/:messageId` | Get a Specific Email |
| `GET /api/workspaces/:workspaceId/emails/thread/:email` | Get Email Thread by Customer Email |
| `POST /api/mailgun/webhooks/inbound` | Inbound Webhook (Platform-Level) |
| `POST /api/workspaces/:workspaceId/hooks` | Optional: Custom Processing via Server Functions Hook |

```
Incoming Email → Mailgun → POST /api/mailgun/webhooks/inbound → Email Processor stores to workspace_email_messages → AI Chat Service auto-responds
```

---

### meshy-3d
**Category:** AI / 3D
Generate 3D models from text prompts or reference images using Meshy AI — the platform proxies requests so apps never manage the Meshy key, polling, or wallet billing.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/generate/3d/text` | `POST /api/generate/3d/text` |
| `POST /api/generate/3d/image` | `POST /api/generate/3d/image` |
| `GET /api/generate/3d/status/:taskId` | `GET /api/generate/3d/status/:taskId` |

```
POST /api/generate/3d/text
```

---

### meta-ads
**Category:** Marketing / Advertising
Read, control, and launch Meta (Facebook/Instagram) ad campaigns through the

| Endpoint | Purpose |
|----------|--------|
| `GET /api/workspaces/:workspaceId/marketing/ads/insights?level=campaign&objectId={metaId}&datePreset=last_30d` | Read Insights |
| `POST /api/workspaces/:workspaceId/marketing/ads/live-status` | Live Delivery Status (batch) |
| `POST /api/workspaces/:workspaceId/marketing/ads/object-status` | Pause / Activate / Archive an Object |
| `GET /api/workspaces/:workspaceId/marketing/ads/campaigns/{metaCampaignId}/adsets` | List Ad Sets in a Campaign |
| `GET /api/workspaces/:workspaceId/marketing/ads/adsets/{metaAdSetId}/ads` | List Ads in an Ad Set |
| `POST /api/workspaces/:workspaceId/marketing/ads/launch` | Launch a Paid Campaign |

```tsx
// Connect a Meta account in-app, then read campaign insights.
const ws = (window as any).__workspaceDb;
const base = `/api/workspaces/${ws.workspaceId}/marketing`;
const auth = { 'X-Workspace-DB-Token': ws.token };

// 1. Is an account already connected?
const { connected } = await fetch(`${base}/connect/status`, { headers: auth }).then((r) => r.json());

// 2. If not, start the OAuth flow and open the returned URL, then poll status.
if (!connected) {
  const { authUrl } = await fetch(`${base}/connect/init`, {
    method: 'POST',
    headers: { ...auth, 'Content-Type': 'application/json' },
    body: JSON.stringify({ scopes: ['ads'] }),
  }).then((r) => r.json());
  window.open(authUrl, '_blank');
}

// 3. Once connected, read performance.
const insights = await fetch(`${base}/ads/insights?level=campaign&objectId=CAMPAIGN_ID`, {
  headers: auth,
}).then((r) => r.json());
```

---

### openai-realtime
**Category:** AI/ML
Real-time voice conversations with AI using OpenAI's Realtime API.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/realtime/token` | API Endpoint |

```
GET /api/realtime/token
```

---

### openai-text-generation
**Category:** AI/ML
Generate text, chatbots, content creation, and AI responses using OpenAI GPT models.

| Endpoint | Purpose |
|----------|--------|
| `POST /proxy/openai/v1/chat/completions` | API Endpoint |

```
POST /proxy/openai/v1/chat/completions
```

---

### permalink-pages
**Category:** Content / Publishing
Generate standalone, publicly accessible pages at unique URLs — static HTML or compiled React/TSX apps.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/permalink-pages` | Create a Permalink Page |
| `GET /api/workspaces/:workspaceId/permalink-pages` | List Permalink Pages |
| `GET /api/workspaces/:workspaceId/permalink-pages/:pageId` | Get a Permalink Page |
| `PATCH /api/workspaces/:workspaceId/permalink-pages/:pageId` | Update a Permalink Page |
| `POST /api/workspaces/:workspaceId/permalink-pages/:pageId/recompile` | Recompile a TSX Page |
| `DELETE /api/workspaces/:workspaceId/permalink-pages/:pageId` | Delete a Permalink Page |

```
POST /api/workspaces/:workspaceId/permalink-pages
```

---

### printify-products
**Category:** E-commerce / Print-on-Demand
Create and sell custom branded merchandise (t-shirts, hoodies, mugs, etc.) using Printify's print-on-demand platform with real-time mockup previews.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/printify/shops` | Get Shops |
| `GET /api/printify/catalog/blueprints` | Get Product Catalog (Blueprints) |
| `GET /api/printify/catalog/blueprints/:blueprintId/providers` | Get Print Providers for Blueprint |
| `GET /api/printify/catalog/blueprints/:blueprintId/providers/:providerId/variants` | Get Variants for Blueprint/Provider |
| `POST /api/printify/uploads` | Upload Design Image |
| `GET /api/proxy/image?url=<encoded-url>` | Proxy External Images (CORS) |

```
GET /api/printify/shops
```

---

### remotion-rendering
**Category:** Media / Video
Render arbitrary Remotion compositions to MP4 server-side. Submit a TSX composition + props, get back a job ID, then poll for the final video URL.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/render/remotion` | Submit Render Job |
| `GET /api/render/remotion/:operationId` | Get Render Status |

```
POST /api/render/remotion
```

---

### rive-animation
**Category:** UI / Animation
Render interactive, state-driven Rive animations (`.riv` files) inside a Space app — perfect for animated avatars whose expression reacts to an AI's emotional response. The Rive React runtime is pre-registered as an allowed library, so a bare `import { useRive } from "@rive-app/react-canvas"` resolves to a pinned CDN build that shares the host React 18 instance.

```tsx
import { RuntimeLoader } from "@rive-app/react-canvas";

// MUST match the @rive-app/canvas version bundled by react-canvas@4.29.1.
RuntimeLoader.setWasmUrl(
  "https://unpkg.com/@rive-app/canvas@2.38.1/rive.wasm"
);
```

---

### server-functions
**Category:** Backend / Server Logic
Define server-side handler functions that receive HTTP requests at unique URLs per workspace.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/workspaces/665201/hooks` |  |
| `GET /api/workspaces/workspace-665201/hooks` |  |
| `GET /api/workspaces/8a8181a4-.../hooks` |  |
| `POST /api/workspaces/:workspaceId/hooks` | Create a Hook |
| `GET /api/workspaces/:workspaceId/hooks` | List Hooks |
| `GET /api/workspaces/:workspaceId/hooks/:hookId` | Get a Hook |

```
GET /api/workspaces/665201/hooks       ✅ works
GET /api/workspaces/workspace-665201/hooks  ✅ works
GET /api/workspaces/8a8181a4-.../hooks ✅ works
```

---

### session-management
**Category:** Authentication
User authentication and session handling with secure state management, including email verification via OTP.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/space/{spaceId}/register` | Basic Session Management |
| `GET /api/session` |  |
| `DELETE /api/session` |  |
| `POST /api/auth/otp/space/check-session` | Check if Email Was Previously Verified |
| `GET /api/auth/otp/space/check-session?workspaceId={workspaceId}&sessionUuid={sessionUuid}` | Check if Current Session is Verified |
| `POST /api/auth/otp/space/send` | Send OTP Code |

```
POST /api/space/{spaceId}/register
```

---

### slack
**Category:** Communication & Collaboration
Post messages, manage channels, and track VA tasks through Slack.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/slack/channels?workspaceId=...` | List Channels |
| `POST /api/slack/messages` | Post Message |
| `POST /api/slack/tasks` | Create VA Task |
| `GET /api/slack/tasks?workspaceId=...&status=pending` | List Tasks |
| `PATCH /api/slack/tasks/:taskId` | Update Task Status |

```
GET /api/slack/channels?workspaceId=...
```

---

### social-publishing
**Category:** Marketing / Social Media
Connect and publish to the workspace's social accounts — LinkedIn organization

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/marketing/posts/linkedin` | Publish to LinkedIn |
| `POST /api/workspaces/:workspaceId/marketing/posts/video` | Publish a Video to Instagram |
| `POST /api/workspaces/:workspaceId/marketing/connect/linkedin/init` | LinkedIn |
| `GET /api/workspaces/:workspaceId/marketing/connect/linkedin/status` |  |
| `GET /api/workspaces/:workspaceId/marketing/connect/linkedin/organizations` |  |
| `POST /api/workspaces/:workspaceId/marketing/connect/linkedin/select-organization` |  |

```tsx
// Publish a text post to the workspace's connected LinkedIn page.
const ws = (window as any).__workspaceDb;
const base = `/api/workspaces/${ws.workspaceId}/marketing`;

const result = await fetch(`${base}/posts/linkedin`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-Workspace-DB-Token': ws.token },
  body: JSON.stringify({ text: 'Hello from our app!' }),
}).then((r) => r.json());
```

---

### stock-photos
**Category:** Media / Images
Search the Unsplash library for royalty-free, attribution-friendly photography. Use the URLs in `<img>` tags, as hero backgrounds, or as starting material for image-edit AI tools.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/stock-photos?query=...&perPage=10&orientation=landscape` | Search Photos |

```
GET /api/stock-photos?query=...&perPage=10&orientation=landscape
```

---

### stripe-payments
**Category:** General
Accept payments and subscriptions in your Space. Payments work out of the box using the platform's Stripe account, with an optional upgrade to your own Stripe Connect account.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/crm/subscribers/:workspaceId` | List Subscribers (Metadata-Based) |
| `GET /api/crm/subscribers/:workspaceId?planTier=companion` | List Subscribers (Metadata-Based) |
| `GET /api/crm/subscribers/:workspaceId?planTier=companion,guide` |  |
| `GET /api/crm/subscribers/:workspaceId?status=active` |  |
| `GET /api/crm/subscribers/:workspaceId?planTier=guide&limit=50` |  |
| `POST /api/crm/subscribers/:workspaceId/backfill` | Backfill Existing Subscribers |

```typescript
// Uses defaults: 7-day trial, $5/mo
const { checkoutUrl } = await fetch('/api/payments/subscribe', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-App-Id': window.__APP_ID__ || window.__SPACE_ID__ },
  body: JSON.stringify({
    customerEmail: 'customer@example.com',
    successUrl: window.location.origin + '/welcome',
    cancelUrl: window.location.href
  })
}).then(r => r.json());

// Redirect to Stripe Checkout
window.location.href = checkoutUrl;
```

---

### task-scheduler
**Category:** Automation
Schedule recurring tasks and one-time automations scoped to a workspace.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/schedules` | Create a Recurring Schedule |
| `POST /api/workspaces/:workspaceId/schedules/email` | Schedule a One-Time Email |
| `GET /api/workspaces/:workspaceId/schedules` | List Schedules |
| `GET /api/workspaces/:workspaceId/schedules/:scheduleId` | Get a Schedule |
| `PATCH /api/workspaces/:workspaceId/schedules/:scheduleId` | Update a Schedule |
| `DELETE /api/workspaces/:workspaceId/schedules/:scheduleId` | Delete a Schedule |

```
POST /api/workspaces/:workspaceId/schedules
```

---

### video-clip
**Category:** Media / Video
Trim a source video to a single `[startSec, endSec]` segment server-side with ffmpeg and get back a permanent public MP4 URL on GCS. Use it to produce clean clips for the Raw-to-Post flow or social sharing without bundling ffmpeg.wasm in the browser or paying for a full Remotion render just to cut a video.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/video/clip` | Trim a Clip |

```
POST /api/video/clip
```

---

### video-frames
**Category:** Media / Video
Pull still PNG frames out of any video URL at the timestamps you specify. Powered by ffmpeg server-side; returns public GCS URLs you can use as thumbnails, scrubber previews, or AI vision inputs.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/video/frames` | Extract Frames |

```
POST /api/video/frames
```

---

### video-stitch
**Category:** Media / Video
Merge an **ordered list of existing video clips** into a single playable MP4 server-side with ffmpeg, and get back one permanent public MP4 URL on GCS. Use this when the user already has multiple clips (uploaded, AI-generated, or trimmed) and wants them concatenated into one continuous video — e.g. a commercial assembled from several scenes, a highlight reel, or a multi-shot social video.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/workspaces/:workspaceId/videos/stitch` | Merge Existing Clips |

```
POST /api/workspaces/:workspaceId/videos/stitch
```

---

### web-scraping
**Category:** Data & Search
Run ANY Apify actor to scrape Instagram, LinkedIn, Amazon, Twitter, YouTube, or any website.

```bash
# Search for actors by keyword (no API key required)
ts-node tools/apify-search-actors.ts "instagram scraper"
ts-node tools/apify-search-actors.ts "linkedin" 10
```

---

### web-search
**Category:** Data & Search
Search Google for real-time web results, news, images, shopping, and academic papers.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/search` | API Endpoint |

```
POST /api/search
```

---

### workspace-community
**Category:** Social
Create shared, social experiences in your mini-apps with feeds, posts, reactions, real-time updates, and user presence (who's online). Perfect for leaderboards, team collaboration, and multiplayer features.

| Endpoint | Purpose |
|----------|--------|
| `POST /api/community/spaces` | API Endpoints |
| `GET /api/community/spaces?workspaceId=workspace-123` |  |
| `POST /api/community/spaces/:spaceId/posts` |  |
| `GET /api/community/spaces/:spaceId/posts?limit=50` |  |
| `POST /api/community/posts/:postId/reactions` |  |
| `POST /api/presence/spaces/:spaceId/join` | Presence API Endpoints |

```
POST /api/community/spaces
```

---

### workspace-db
**Category:** Data Persistence / Database
Store and query structured data in isolated PostgreSQL tables. Every workspace gets its own database schema. The SDK is auto-injected into Space apps — no imports needed.

| Endpoint | Purpose |
|----------|--------|
| `GET /api/workspaces/{workspaceId}/db/tables` | List Tables |
| `GET /api/workspaces/{workspaceId}/db/tables/{tableName}?module={module}` | Describe Table |
| `GET /api/workspaces/{workspaceId}/data/{table}?_limit=50&_offset=0&_sort=created_at&_order=desc&status=eq.active` | Query Rows |
| `POST /api/workspaces/{workspaceId}/data/{table}` | Insert Rows |
| `PATCH /api/workspaces/{workspaceId}/data/{table}/{id}` | Update Row |
| `DELETE /api/workspaces/{workspaceId}/data/{table}/{id}` | Delete Row |

```tsx
function MyComponent() {
  const { data, loading, error, total, refresh } = useWorkspaceDB('orders', {
    filters: [
      { column: 'status', operator: 'eq', value: 'active' }
    ],
    orderBy: { column: 'created_at', direction: 'desc' },
    limit: 50,
    offset: 0,
    shared: false
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return <ul>{data.map(row => <li key={row.id}>{row.name}</li>)}</ul>;
}
```

---

## What Apps CANNOT Do

- **No direct database access** outside the WorkspaceDB SDK (`window.__workspaceDb` / `window.useWorkspaceDB`)
- **No server-side code execution** -- apps are client-side React components. Use `server-functions` for backend logic.
- **No direct access to API keys** -- all secrets are handled server-side via proxy endpoints
- **No file system access** -- use `file-storage` integration for persistent files
- **No direct Stripe/OpenAI/ElevenLabs API calls** -- always use the platform proxy endpoints listed above
- **No WebSocket servers** -- use `workspace-community` for real-time features
