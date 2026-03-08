# Step-by-Step: Debug "Unable to assign case" (500 Error)

The error occurs when HR clicks **Assign** after creating a new case. Follow these steps to find the root cause.

---

## Step 1: Get the actual error message from the API

The 500 response includes a `detail` field with the real error. Here's how to see it:

1. Open **Chrome DevTools** (F12 or Cmd+Option+I)
2. Go to the **Network** tab
3. Check **"Preserve log"**
4. Filter by **Fetch/XHR**
5. Click **New Case**, enter an employee email, then click **Assign**
6. In the request list, find the failed **assign** request (red, status 500)
7. Click it and open the **Response** or **Preview** tab
8. Look at the JSON – it should contain `"detail": "actual error message here"`

**Copy the `detail` value** – that tells us exactly what's failing (e.g. missing table, FK violation, RLS, etc.).

---

## Step 2: Confirm deployment

The fix (non-blocking `ensure_case_participant`, `insert_case_event`, etc.) must be deployed to `api.relopass.com`.

1. Check if the backend was redeployed after the last git push
2. On Render: Dashboard → Your backend service → check "Last deploy" time
3. If it's older than your last commit, trigger a **Manual Deploy**

---

## Step 3: Run backend locally (optional – full stack trace)

To see the full Python traceback:

1. Open a terminal in the project root
2. Set `DATABASE_URL` to your Supabase connection string (Session mode)
3. Run:
   ```bash
   ./venv/bin/python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Point the frontend at local backend (or use the same URL with `VITE_API_URL=http://localhost:8000`)
5. Reproduce the assign flow
6. Check the terminal – the full error and stack trace will appear there

---

## Step 4: Share the error

Once you have the `detail` from Step 1 (or the traceback from Step 3), share it so we can fix the root cause.
