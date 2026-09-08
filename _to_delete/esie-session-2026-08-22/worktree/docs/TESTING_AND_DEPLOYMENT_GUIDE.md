# Testing & Deployment Guide — ReloPass

## Why You're Seeing "Unable to load assignments" on relopass.com

You're viewing **relopass.com** (your live/production site). The code changes we made exist only in your **local project** on your Mac. The live site is still running the **old version** of the app, so it doesn't include the fixes.

---

## Local vs Deployed: Two Different Versions

| Where | What runs |
|-------|-----------|
| **Your Mac** (`/Users/Rom/Documents/GitHub/rolec`) | Latest code with all our fixes |
| **relopass.com** | Previous version deployed earlier |

Until you deploy the new code, relopass.com will keep showing the old behavior and errors.

---

## How to Test Our Changes (Step by Step)

### 1. Run the app locally (on your Mac)

This uses your latest code on your machine.

**Terminal 1 — Backend**
```bash
cd /Users/Rom/Documents/GitHub/rolec
source venv/bin/activate
lsof -ti:8000 | xargs kill -9    # Free port 8000 if needed
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend**
```bash
cd /Users/Rom/Documents/GitHub/rolec
npm run dev
```

**In the browser**

- Open **http://localhost:3000** (or the URL shown in the terminal, e.g. 3001 or 3002)
- Do **not** use relopass.com while testing local changes

### 2. Check that the frontend points to your local backend

In `frontend/.env.development` you should have:
```
VITE_API_URL=http://localhost:8000
```

If the backend uses a different port, update this URL accordingly.

### 3. Test as employee

- Log in as: `demo@relopass.com` / `Passw0rd!`
- Go to **HR Policy**
- You should see your applicable policy (or a message like “No matching policy”) instead of “Unable to load assignments”.

### 4. Test as HR

- Log in as HR (e.g. `hr.demo@relopass.local` / `Passw0rd!`)
- Go to **HR Policy**
- You should see the **"Manage policies →"** button and/or **"Policy Management"** in the nav.

---

## General Logic: From Code Change to Live Site

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Make changes (you or AI edit files in your project)           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Test locally                                                  │
│    • Run backend + frontend on your Mac                          │
│    • Open http://localhost:3000                                  │
│    • Verify the behavior is correct                              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Deploy to production (relopass.com)                           │
│    • How you deploy depends on your hosting (Render, Vercel,     │
│      etc.)                                                       │
│    • Usually: push to Git → CI/CD runs build and deploy          │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Test on relopass.com                                          │
│    • Open https://relopass.com                                   │
│    • Check that the new behavior appears there too               │
└─────────────────────────────────────────────────────────────────┘
```

---

## What You Need to Do Now

### Option A: Test locally (fastest)

1. Start backend and frontend on your Mac (commands above).
2. Open **http://localhost:3000** in the browser.
3. Test as employee and as HR.
4. This will use all our changes without touching relopass.com.

### Option B: See the fixes on relopass.com

You need to **deploy** the new code to wherever relopass.com is hosted.

1. **Commit and push the changes**
   ```bash
   cd /Users/Rom/Documents/GitHub/rolec
   git add .
   git commit -m "HR Policy fixes: employee view, manage policies, policy upload"
   git push origin main
   ```

2. **Deploy**
   - If you use **Render**, **Vercel**, **Netlify**, or similar: they usually deploy automatically when you push to `main` (or your default branch).
   - If deployment is manual: follow your host’s steps to build and deploy the app.

3. **Wait for the deployment** (often 2–5 minutes).

4. **Hard refresh** the browser on relopass.com (`Cmd+Shift+R` on Mac) to avoid cached files.

---

## Checklist: After Any Code Change

- [ ] Changes are saved in your project files
- [ ] Tested locally (backend + frontend running, open localhost)
- [ ] Committed and pushed to Git
- [ ] Deployment completed (if using CI/CD)
- [ ] Tested on the live URL (relopass.com)
- [ ] Hard refresh if you don’t see the updates

---

## Where Is relopass.com Deployed?

This project uses **Render** (see `README_DEPLOY_RENDER.md`). Deployment typically works like this:

1. **Push to GitHub** — When you push your changes to the `main` branch, Render automatically rebuilds and redeploys.
2. **Render Dashboard** — Go to [dashboard.render.com](https://dashboard.render.com) → your ReloPass service → "Manual Deploy" if needed.
3. **Wait** — A new deploy takes a few minutes.

**To deploy our changes:**
```bash
cd /Users/Rom/Documents/GitHub/rolec
git add .
git commit -m "HR Policy: employee view, manage policies, policy upload"
git push origin main
```

Then check the Render dashboard to confirm the new deploy finished.
