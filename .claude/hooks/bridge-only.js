#!/usr/bin/env node
// Bridge-only statusLine helper.
// Reads statusLine input on stdin, writes /tmp/claude-ctx-{session_id}.json
// for context-monitor.js to consume. Produces NO stdout — pair with
// statusline-wrapper.sh which feeds the same input to claude-hud for rendering.
//
// Extracted from the (now-removed) os2 statusline.js, which itself was
// vendored from gsd-build/get-shit-done@MIT.

const fs = require('fs');
const path = require('path');
const os = require('os');

let input = '';
const stdinTimeout = setTimeout(() => process.exit(0), 3000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  clearTimeout(stdinTimeout);
  try {
    const data = JSON.parse(input);
    const session = data.session_id;
    const remaining = data.context_window?.remaining_percentage;

    if (!session || /[/\\]|\.\./.test(session) || remaining == null) {
      process.exit(0);
    }

    const bridgePath = path.join(os.tmpdir(), `claude-ctx-${session}.json`);
    const rawUsedPct = Math.round(100 - remaining);
    fs.writeFileSync(bridgePath, JSON.stringify({
      session_id: session,
      remaining_percentage: remaining,
      used_pct: rawUsedPct,
      timestamp: Math.floor(Date.now() / 1000)
    }));
  } catch (e) {
    // Silent fail — bridge is best-effort, never break statusLine
  }
});
