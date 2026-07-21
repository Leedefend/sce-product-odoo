#!/usr/bin/env node
import fs from 'node:fs';
import { launchChromium } from './playwright_runtime.mjs';

const BASE_URL = String(process.env.FRONTEND_URL || 'http://127.0.0.1:38089').replace(/\/$/, '');
const DB_NAME = String(process.env.DB_NAME || 'sc_nav_pro_01');
const PASSWORD = String(process.env.NAV_PRO_PASSWORD || '');
const META = JSON.parse(fs.readFileSync(process.env.NAV_PRO_01R_HTTP_OUT || '/tmp/nav-pro-01/route-authority-http.json', 'utf8'));

function check(value, message) {
  if (!value) throw new Error(message);
}

function capture(page) {
  const state = { http500: [], dataRequests: 0, pageErrors: [] };
  page.on('pageerror', (error) => state.pageErrors.push(error.message));
  page.on('response', async (response) => {
    if (response.status() >= 500) state.http500.push({ status: response.status(), url: response.url() });
    if (!response.url().includes('/api/v1/intent')) return;
    try {
      const body = JSON.parse(await response.text());
      const intent = String(body?.meta?.intent || '');
      if (intent === 'ui.contract.v2' || intent === 'api.data') state.dataRequests += 1;
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
}

async function expectList(page, path, label) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  try {
    await page.locator('[data-product-page-mode="list"]').first().waitFor({ timeout: 45000 });
  } catch (error) {
    const body = await page.locator('body').innerText().catch(() => '');
    throw new Error(`${label}: list unavailable path=${new URL(page.url()).pathname} body=${JSON.stringify(body.slice(0, 800))}; ${error.message}`);
  }
  check(new URL(page.url()).pathname.startsWith('/a/'), `${label}: unexpected path ${page.url()}`);
  const text = await page.locator('body').innerText();
  check(!/无权访问|访问受限|NAVIGATION_AUTHORITY_DENIED/.test(text), `${label}: denied marker`);
}

async function expectDenied(page, path, label) {
  await page.goto(`${BASE_URL}${path}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForURL((url) => url.pathname === '/access-denied', { timeout: 45000 });
  check((await page.locator('body').innerText()).includes('无权访问'), `${label}: denial page missing`);
}

async function main() {
  check(PASSWORD, 'NAV_PRO_PASSWORD is required');
  const browser = await launchChromium({ headless: true });
  const report = {};
  try {
    for (const role of ['config_admin', 'system_admin']) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
      const page = await context.newPage();
      const state = capture(page);
      await login(page, role);
      await expectList(page, `/a/${META.admin_action_id}`, `${role}.user_management`);
      const body = await page.locator('body').innerText();
      check(/用户账号与权限|用户账号/.test(body), `${role}: user management title missing`);
      const firstRow = page.locator('.desktop-record-table tbody tr').first();
      await firstRow.waitFor({ timeout: 45000 });
      await firstRow.click();
      await page.waitForURL((url) => url.pathname.startsWith('/f/') || url.pathname.startsWith('/r/'), { timeout: 45000 });
      await page.locator('[data-field-name="sc_user_role_group_ids"]').waitFor({ timeout: 45000 });
      check(state.http500.length === 0 && state.pageErrors.length === 0, `${role}: browser/runtime errors`);
      report[role] = 'PASS';
      await context.close();
    }

    const adminDeniedContext = await browser.newContext();
    const adminDeniedPage = await adminDeniedContext.newPage();
    const adminDeniedState = capture(adminDeniedPage);
    await login(adminDeniedPage, 'project_member');
    const beforeAdminDenied = adminDeniedState.dataRequests;
    await expectDenied(adminDeniedPage, `/a/${META.admin_action_id}`, 'ordinary.admin');
    check(adminDeniedState.dataRequests === beforeAdminDenied, 'ordinary.admin: unauthorized route triggered data request');
    await adminDeniedContext.close();

    const scope = META.legal_scope;
    const legalQuery = new URLSearchParams({
      company_id: String(scope.company_id),
      project_id: String(scope.project_id),
      contract_id: String(scope.contract_id),
    }).toString();
    const legalPath = `/a/${META.execution_action_id}?${legalQuery}`;
    const pmContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' });
    const pmPage = await pmContext.newPage();
    const pmState = capture(pmPage);
    await login(pmPage, 'pm');
    await expectList(pmPage, legalPath, 'pm.execution.legal');
    await pmPage.reload({ waitUntil: 'domcontentloaded', timeout: 45000 });
    await pmPage.locator('[data-product-page-mode="list"]').first().waitFor({ timeout: 45000 });
    await expectDenied(pmPage, `/a/${META.execution_action_id}`, 'pm.execution.missing_context');
    await expectDenied(pmPage, `/a/${META.execution_action_id}?company_id=${scope.company_id}&project_id=${Number(scope.project_id) + 1000000}&contract_id=${scope.contract_id}`, 'pm.execution.cross_project');
    await expectDenied(pmPage, `/a/${META.execution_action_id}?company_id=${Number(scope.company_id) + 1000000}&project_id=${scope.project_id}&contract_id=${scope.contract_id}`, 'pm.execution.cross_company');
    check(pmState.http500.length === 0 && pmState.pageErrors.length === 0, 'pm.execution: browser/runtime errors');
    report.pm_execution = 'PASS';
    await pmContext.close();

    const ordinaryContext = await browser.newContext();
    const ordinaryPage = await ordinaryContext.newPage();
    const ordinaryState = capture(ordinaryPage);
    await login(ordinaryPage, 'project_member');
    const beforeExecutionDenied = ordinaryState.dataRequests;
    await expectDenied(ordinaryPage, legalPath, 'ordinary.execution');
    check(ordinaryState.dataRequests === beforeExecutionDenied, 'ordinary.execution: unauthorized route triggered data request');
    await ordinaryContext.close();

    console.log('USER_MANAGEMENT_REACHABLE=true');
    console.log('ROLE_MANAGEMENT_REACHABLE=true');
    console.log('OLD_ACTION_EXECUTION_AUTHORIZED_DIRECT_REACHABLE=true');
    console.log('ORDINARY_USER_ADMIN_DENIAL=PASS');
    console.log('CROSS_COMPANY_CONTEXT_DENIAL=PASS');
    console.log('UNAUTHORIZED_ROUTE_DATA_REQUESTS=0');
    console.log('DIRECT_ROUTE_500=0');
    console.log('NAV_PRO_01R_ROUTE_AUTHORITY_BROWSER=PASS');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`NAV_PRO_01R_ROUTE_AUTHORITY_BROWSER=FAIL ${error.stack || error.message}`);
  process.exitCode = 2;
});
