#!/usr/bin/env bash
# Use the pinned Playwright package installed by the caller. Probe the actual
# browser before invoking apt: hosted images usually already provide its libs.
set -euo pipefail

npx --no-install playwright install chromium

probe_browser() {
  node --input-type=module <<'NODE'
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
await browser.close();
NODE
}

if probe_browser; then
  echo "Pinned Chromium launches with the available system libraries."
else
  timeout 300 npx --no-install playwright install-deps chromium
  probe_browser
fi
