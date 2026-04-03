---
phase: quick
plan: 260403-rzb
type: execute
wave: 1
depends_on: []
files_modified:
  - .env
autonomous: true
requirements: [NOTF-04]

must_haves:
  truths:
    - "VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are populated in .env"
    - "Backend container reads the new keys (no config error on startup)"
    - "A test push notification arrives in the browser"
  artifacts:
    - path: ".env"
      provides: "VAPID key pair"
      contains: "VAPID_PUBLIC_KEY="
  key_links:
    - from: ".env"
      to: "backend app config (settings.vapid_private_key)"
      via: "Docker Compose env_file mount"
      pattern: "VAPID_PRIVATE_KEY"
---

<objective>
Generate a VAPID key pair, write both keys into the real .env file, restart the backend
container so it picks up the new config, then fire a direct test push notification using
the saved push subscription from /data/push_subscription.json.

Purpose: Unblock browser push notifications end-to-end — Phase 07 cannot deliver
notifications until VAPID keys exist in the running environment.
Output: Populated .env (VAPID keys), restarted backend, verified push received in browser.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: Generate VAPID key pair and write to .env</name>
  <files>.env</files>
  <action>
    1. Generate a VAPID key pair by running:

       npx web-push generate-vapid-keys --non-interactive

       This prints two lines: "Public Key: ..." and "Private Key: ...". Capture
       both values.

    2. Read the current .env file.

    3. Update the .env file in-place:
       - Set VAPID_PUBLIC_KEY=<generated-public-key>
       - Set VAPID_PRIVATE_KEY=<generated-private-key>
       - Set VAPID_CONTACT_EMAIL=admin@localhost (leave as-is if already set to
         a real address; only update if it is still the placeholder)
       - Also set VITE_VAPID_PUBLIC_KEY=<same-generated-public-key> (the frontend
         may read it from the API, but populate the env var too for completeness)

    Do NOT touch any other .env values. Do NOT commit .env to git.

    Use the Write tool to write the updated file. Do NOT use shell redirection
    or heredoc to overwrite the file.
  </action>
  <verify>
    Run: grep "VAPID_PUBLIC_KEY" .env
    Expected: a non-empty base64url string (~88 characters) on that line.
  </verify>
  <done>Both VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY in .env are non-empty base64url strings.</done>
</task>

<task type="auto">
  <name>Task 2: Restart backend and fire test push notification</name>
  <files></files>
  <action>
    1. Restart the backend container so it picks up the new env vars:

       docker compose restart backend

       Wait for it to be healthy (check with `docker compose ps` or watch logs
       briefly with `docker compose logs --tail=20 backend`).

    2. Verify the subscription file exists inside the container:

       docker compose exec backend ls /data/push_subscription.json

       If missing: the user must re-grant push permission in the browser first
       (navigate to the app, allow notifications). The subscription is written
       when the frontend calls POST /api/push/subscribe. Stop here and ask the
       user to do this before continuing.

    3. Fire a test push notification using a Python one-liner inside the container.
       This reuses the exact same webpush() call pattern as notifier.py:

       docker compose exec backend python3 -c "
       import json, os
       from pathlib import Path
       from pywebpush import webpush
       sub = json.loads(Path('/data/push_subscription.json').read_text())
       webpush(
           subscription_info=sub,
           data=json.dumps({'title': 'בדיקה', 'body': 'דחיפה עובדת', 'url': 'http://localhost'}, ensure_ascii=False),
           vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],
           vapid_claims={'sub': 'mailto:' + os.environ.get('VAPID_CONTACT_EMAIL', 'admin@localhost')},
       )
       print('push sent')
       "

    4. If the one-liner prints "push sent" with no exception, the end-to-end
       pipeline is working. If it raises a WebPushException, capture the full
       error message and report it.
  </action>
  <verify>
    The Python one-liner exits with "push sent" printed to stdout and exit code 0.
    The browser (which must be open to the app or have background service worker active)
    shows a notification titled "בדיקה".
  </verify>
  <done>
    Test push notification delivered to browser. VAPID key pair is operational.
    Phase 07 notification pipeline is end-to-end verified.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    VAPID keys generated and written to .env, backend restarted with new config,
    test push notification fired via pywebpush inside the container.
  </what-built>
  <how-to-verify>
    1. Check your browser — a notification with title "בדיקה" and body "דחיפה עובדת"
       should have appeared (or be in the notification tray).
    2. If the notification did not appear: confirm the browser has push permission
       for the app and the service worker is registered (DevTools -> Application ->
       Service Workers). The subscription file must exist at /data/push_subscription.json.
    3. If it appeared: the full Phase 07 pipeline is working. New listings scraped
       by APScheduler will now trigger push notifications automatically.
  </how-to-verify>
  <resume-signal>Type "approved" if the notification appeared, or describe what you see.</resume-signal>
</task>

</tasks>

<verification>
- .env has non-empty VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY values
- `docker compose ps` shows backend container running (not restarting)
- Test push one-liner exits 0 with "push sent"
- Browser notification received
</verification>

<success_criteria>
VAPID key pair exists in .env, backend container is running with those keys loaded,
and a manual test push notification was successfully delivered to the browser.
The Phase 07 notification pipeline is fully operational end-to-end.
</success_criteria>

<output>
After completion, create `.planning/quick/260403-rzb-generate-vapid-keys-and-configure-env-th/260403-rzb-SUMMARY.md`
</output>
