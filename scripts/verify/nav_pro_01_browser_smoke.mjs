#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { launchChromium } from './playwright_runtime.mjs';

const BASE_URL = process.env.FRONTEND_URL || 'http://127.0.0.1:28089';
const DB_NAME = process.env.DB_NAME || 'sc_nav_pro_01';
const PASSWORD = process.env.NAV_PRO_PASSWORD || '';
const MATRIX = 'docs/audit/native/nav_policy_01/product_navigation_exposure_matrix.csv';
const CONTEXT_ROUTES = process.env.NAV_PRO_CONTEXT_ROUTES || '/tmp/nav-pro-01/context-routes.json';
const OUTPUT = process.env.NAV_PRO_BROWSER_REPORT || '/tmp/nav-pro-01/browser-smoke.json';
const TIMEOUT = Number(process.env.NAV_PRO_BROWSER_TIMEOUT || 45000);
const ROLE_CATALOG = ['finance', 'project_member', 'pm', 'owner'];
const ROLES = String(process.env.NAV_PRO_BROWSER_ROLES || ROLE_CATALOG.join(','))
  .split(',')
  .map((role) => role.trim())
  .filter((role) => ROLE_CATALOG.includes(role));
const FAILURE_TEXT = /无权访问|权限不足|访问被拒绝|初始化失败|加载失败|暂无导航数据|页面不存在|Internal Server Error/i;

function check(value, message) {
  if (!value) throw new Error(message);
}

function parseCsv(text) {
  const rows = [];
  let row = [], value = '', quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') { value += '"'; index += 1; }
      else quoted = !quoted;
    } else if (char === ',' && !quoted) { row.push(value); value = ''; }
    else if (char === '\n' && !quoted) { row.push(value.replace(/\r$/, '')); rows.push(row); row = []; value = ''; }
    else value += char;
  }
  if (value || row.length) { row.push(value); rows.push(row); }
  const headers = rows.shift() || [];
  return rows.filter((item) => item.length > 1).map((item) => Object.fromEntries(headers.map((key, index) => [key, item[index] || ''])));
}

function payloadData(payload) {
  return payload?.result?.data || payload?.result || payload?.data || payload;
}

function flattenLeaves(nodes) {
  const found = [];
  for (const node of Array.isArray(nodes) ? nodes : []) {
    const children = Array.isArray(node?.children) ? node.children : [];
    if (children.length) { found.push(...flattenLeaves(children)); continue; }
    const meta = node?.meta && typeof node.meta === 'object' ? node.meta : {};
    const xmlid = String(node?.menu_xmlid || node?.xmlid || meta.menu_xmlid || '').trim();
    if (xmlid) found.push(xmlid);
  }
  return found;
}

function attachCapture(page) {
  const state = {
    navigation: null,
    serverErrors: [],
    pageErrors: [],
    consoleErrors: [],
    consoleWarnings: [],
    requestFailures: [],
    lifecycle: [],
    resourceResponses: [],
    pendingRequests: new Map(),
  };
  page.on('crash', () => state.lifecycle.push('crash'));
  page.on('close', () => state.lifecycle.push('close'));
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) state.lifecycle.push(`navigate:${frame.url()}`);
  });
  page.on('request', (request) => state.pendingRequests.set(request, request.url()));
  page.on('requestfinished', (request) => state.pendingRequests.delete(request));
  page.on('requestfailed', (request) => {
    state.pendingRequests.delete(request);
    state.requestFailures.push({ url: request.url(), error: request.failure()?.errorText || '' });
  });
  page.on('pageerror', (error) => state.pageErrors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error' && !/favicon|ResizeObserver/i.test(message.text())) state.consoleErrors.push(message.text());
    if (message.type() === 'warning' || message.type() === 'warn') state.consoleWarnings.push(message.text());
  });
  page.on('response', async (response) => {
    const resourceType = response.request().resourceType();
    if (resourceType === 'document' || resourceType === 'script') {
      state.resourceResponses.push({ status: response.status(), type: resourceType, url: response.url() });
    }
    if (response.status() >= 500) state.serverErrors.push({ status: response.status(), url: response.url() });
    if (!response.url().includes('/api/v1/intent')) return;
    try {
      const body = JSON.parse(await response.text());
      const data = payloadData(body);
      const nav = data?.delivery_engine_v1?.nav || data?.release_navigation_v1?.nav;
      if (Array.isArray(nav)) state.navigation = nav;
    } catch {}
  });
  return state;
}

async function login(page, role) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  const inputs = page.locator('input');
  await inputs.nth(0).fill(`nav_pro_${role}`);
  await inputs.nth(1).fill(PASSWORD);
  if (await inputs.nth(2).isEnabled().catch(() => false)) await inputs.nth(2).fill(DB_NAME);
  await page.getByRole('button', { name: /^登录$/ }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 45000 });
  await page.locator('.layout-shell').waitFor({ timeout: 45000 });
  await page.waitForFunction(() => !(document.body.innerText || '').includes('正在初始化'), null, { timeout: 45000 });
}

async function main() {
  check(PASSWORD, 'NAV_PRO_PASSWORD is required');
  check(ROLES.length > 0, 'NAV_PRO_BROWSER_ROLES did not select a supported role');
  const matrix = parseCsv(fs.readFileSync(MATRIX, 'utf8'));
  const contextRoutes = JSON.parse(fs.readFileSync(CONTEXT_ROUTES, 'utf8'));
  const browser = await launchChromium({ headless: true });
  const report = { database: DB_NAME, roles: {} };
  try {
    for (const role of ROLES) {
      const expected = new Set(matrix.filter((row) => row.role === role && ['PRIMARY_NAV', 'ROLE_HOME_ACTION'].includes(row.exposure_mode)).map((row) => row.menu_xmlid));
      const contextual = new Set(matrix.filter((row) => row.role === role && row.exposure_mode === 'CONTEXTUAL_ROUTE').map((row) => row.menu_xmlid));
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
      const page = await context.newPage();
      await page.addInitScript(() => {
        window.addEventListener('vite:preloadError', (event) => {
          const payload = event?.payload;
          console.error('[nav-pro-01] vite:preloadError', payload?.message || String(payload || 'unknown'));
        });
      });
      const capture = attachCapture(page);
      await login(page, role);
      check(Array.isArray(capture.navigation), `${role}: authoritative navigation response missing`);
      const actual = new Set(flattenLeaves(capture.navigation));
      check(actual.size === expected.size && [...actual].every((xmlid) => expected.has(xmlid)), `${role}: browser primary navigation differs from policy`);
      check([...actual].every((xmlid) => !contextual.has(xmlid)), `${role}: contextual route leaked into sidebar`);
      const contextRoute = String(contextRoutes[role] || '');
      check(/^\/a\/\d+\?menu_id=\d+$/.test(contextRoute), `${role}: contextual route manifest is invalid`);
      await page.goto(new URL(contextRoute, BASE_URL).toString(), {
        waitUntil: 'domcontentloaded',
        timeout: TIMEOUT,
      });
      await page.waitForURL((url) => url.pathname.startsWith('/a/') || url.pathname === '/access-denied', { timeout: TIMEOUT });
      try {
        await page.locator('.layout-shell').waitFor({ timeout: TIMEOUT });
        await page.locator('[data-product-page-mode="list"]').first().waitFor({ timeout: TIMEOUT });
      } catch (error) {
        const bodyText = await page.locator('body').innerText({ timeout: 1000 }).catch(() => '');
        const bodyHtml = await page.locator('body').innerHTML({ timeout: 1000 }).catch(() => '');
        throw new Error(
          `${role}: contextual shell unavailable path=${new URL(page.url()).pathname} `
          + `pageerrors=${JSON.stringify(capture.pageErrors.slice(0, 3))} `
          + `console=${JSON.stringify(capture.consoleErrors.slice(0, 3))} `
          + `warnings=${JSON.stringify(capture.consoleWarnings.slice(0, 5))} `
          + `http5xx=${JSON.stringify(capture.serverErrors.slice(0, 3))} `
          + `requestfailures=${JSON.stringify(capture.requestFailures.slice(0, 3))} `
          + `pending=${JSON.stringify([...capture.pendingRequests.values()].slice(0, 5))} `
          + `lifecycle=${JSON.stringify(capture.lifecycle.slice(-8))} `
          + `resources=${JSON.stringify(capture.resourceResponses.slice(-8))} `
          + `body=${JSON.stringify(bodyText.slice(0, 500))} `
          + `html=${JSON.stringify(bodyHtml.slice(0, 1000))}; ${error.message}`,
        );
      }
      await page.waitForTimeout(300);
      const bodyText = await page.locator('body').innerText();
      const failureMarker = bodyText.match(FAILURE_TEXT)?.[0] || '';
      check(!failureMarker, `${role}: contextual browser route failed marker=${failureMarker} path=${new URL(page.url()).pathname}`);
      check(capture.serverErrors.length === 0, `${role}: HTTP 5xx observed`);
      check(capture.pageErrors.length === 0, `${role}: browser pageerror observed`);
      report.roles[role] = { primary_count: actual.size, contextual_route: 'PASS', server_errors: 0, page_errors: 0 };
      await context.close();
    }
  } finally {
    await browser.close();
  }
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, `${JSON.stringify(report, null, 2)}\n`);
  console.log('NAV_PRO_01_BROWSER_SMOKE=PASS');
}

main().catch((error) => {
  console.error(`NAV_PRO_01_BROWSER_SMOKE=FAIL ${error.stack || error.message}`);
  process.exitCode = 2;
});
