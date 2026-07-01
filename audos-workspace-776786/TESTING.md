# Testing Genesis Space

## Clear Customer Session

To reset and see the email gate again, open browser console and run:
```javascript
sessionStorage.clear();
location.reload();
```

## What you should see:

1. **First visit (no session):**
   - Email gate with gradient background
   - Email input field to create session
   - "Get Started" button

2. **After entering email:**
   - Desktop appears with smooth fade-in animation
   - Left dock with configured app icons
   - Agent window opens by default
   - Responsive layout (desktop: side-by-side, mobile: stacked)

3. **Subsequent visits:**
   - Auto-resumes your session
   - Goes directly to desktop (no email prompt)
   - Your customer data is preserved in `/user/{sessionId}/`

## Session Isolation Test

1. Open incognito window
2. Visit `/space/{spaceId}`
3. Enter a different email
4. Create data using apps
5. In regular window, verify you see YOUR data (not incognito data)
6. Each email creates a completely isolated customer session
