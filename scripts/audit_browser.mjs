import { chromium } from 'playwright';

/**
 * The site follows the system appearance until a visitor chooses one. Audits begin in
 * the night appearance, as they did when night was the fixed default, so every context
 * defaults to a dark colour scheme. A context can still pass its own colorScheme.
 */
export async function launchAuditBrowser(options) {
  const browser = await chromium.launch(options);
  const newContext = browser.newContext.bind(browser);
  const newPage = browser.newPage.bind(browser);
  browser.newContext = (settings = {}) => newContext({ colorScheme: 'dark', ...settings });
  browser.newPage = (settings = {}) => newPage({ colorScheme: 'dark', ...settings });
  return browser;
}
