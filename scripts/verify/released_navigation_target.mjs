const SYSTEM_INIT_INTENT = 'system.init';

function navigationFromPayload(payload) {
  const data = payload?.result || payload?.data || payload || {};
  const release = data?.release_navigation_v1?.nav;
  const delivery = data?.delivery_engine_v1?.nav;
  if (Array.isArray(release)) return release;
  if (Array.isArray(delivery)) return delivery;
  return Array.isArray(data?.nav) ? data.nav : [];
}

export function findReleasedNavigationTarget(nav, actionXmlid) {
  const pending = Array.isArray(nav) ? [...nav] : [];
  while (pending.length) {
    const node = pending.shift();
    if (!node || typeof node !== 'object') continue;
    const meta = node.meta && typeof node.meta === 'object' ? node.meta : {};
    const candidate = String(node.action_xmlid || meta.action_xmlid || '');
    if (candidate === actionXmlid) {
      const actionId = Number(node.action_id || meta.action_id || 0);
      const menuId = Number(node.menu_id || meta.menu_id || 0);
      if (actionId > 0 && menuId > 0) return { action_id: actionId, menu_id: menuId };
    }
    if (Array.isArray(node.children)) pending.push(...node.children);
  }
  return null;
}

export function findReleasedNavigationTargetById(nav, actionId, menuId) {
  const expectedActionId = Number(actionId || 0);
  const expectedMenuId = Number(menuId || 0);
  if (expectedActionId <= 0 || expectedMenuId <= 0) return null;
  const pending = Array.isArray(nav) ? [...nav] : [];
  while (pending.length) {
    const node = pending.shift();
    if (!node || typeof node !== 'object') continue;
    const meta = node.meta && typeof node.meta === 'object' ? node.meta : {};
    const candidateActionId = Number(node.action_id || node.actionId || node.action || meta.action_id || meta.actionId || 0);
    const candidateMenuId = Number(node.menu_id || node.menuId || meta.menu_id || meta.menuId || 0);
    if (candidateActionId === expectedActionId && candidateMenuId === expectedMenuId) {
      return { action_id: candidateActionId, menu_id: candidateMenuId };
    }
    if (Array.isArray(node.children)) pending.push(...node.children);
  }
  return null;
}

export function findReleasedNavigationTargetByMenuXmlid(nav, menuXmlid) {
  const expectedMenuXmlid = String(menuXmlid || '');
  if (!expectedMenuXmlid) return null;
  const pending = Array.isArray(nav) ? [...nav] : [];
  while (pending.length) {
    const node = pending.shift();
    if (!node || typeof node !== 'object') continue;
    const meta = node.meta && typeof node.meta === 'object' ? node.meta : {};
    const candidateMenuXmlid = String(node.menu_xmlid || node.xmlid || meta.menu_xmlid || '');
    if (candidateMenuXmlid === expectedMenuXmlid) {
      const actionId = Number(node.action_id || node.actionId || node.action || meta.action_id || meta.actionId || 0);
      const menuId = Number(node.menu_id || node.menuId || meta.menu_id || meta.menuId || 0);
      if (actionId > 0 && menuId > 0) return { action_id: actionId, menu_id: menuId };
    }
    if (Array.isArray(node.children)) pending.push(...node.children);
  }
  return null;
}

export function captureReleasedNavigation(page) {
  let current = [];
  page.on('response', async (response) => {
    if (!response.url().includes('/api/v1/intent')) return;
    try {
      const request = JSON.parse(response.request().postData() || '{}');
      if (request?.intent !== SYSTEM_INIT_INTENT || response.status() >= 400) return;
      const nav = navigationFromPayload(await response.json());
      if (nav.length) current = nav;
    } catch {}
  });
  return {
    nav: () => current,
    async target(actionXmlid, timeoutMs = 45000) {
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        const target = findReleasedNavigationTarget(current, actionXmlid);
        if (target) return target;
        await page.waitForTimeout(50);
      }
      throw new Error(`released navigation target missing: ${actionXmlid}`);
    },
    async targetByMenuXmlid(menuXmlid, timeoutMs = 45000) {
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        const target = findReleasedNavigationTargetByMenuXmlid(current, menuXmlid);
        if (target) return target;
        await page.waitForTimeout(50);
      }
      throw new Error(`released navigation menu target missing: ${menuXmlid}`);
    },
  };
}

export function applyReleasedNavigationTarget(targets, keys, released) {
  for (const key of keys) {
    if (!targets[key]) continue;
    targets[key].action_id = released.action_id;
    targets[key].menu_id = released.menu_id;
  }
}
