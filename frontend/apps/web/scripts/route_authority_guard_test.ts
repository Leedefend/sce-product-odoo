import assert from 'node:assert/strict';
import {
  findRouteAuthority,
  normalizeRouteAuthorityContract,
  routeAuthorityContextAllowed,
  routeAuthorityForPrincipal,
} from '../src/app/routeAuthority';

const raw = {
  contract_version: 'route_authority.v1',
  source: 'test',
  principal_scope: { user_id: 7, company_id: 3, role_code: 'pm' },
  primary_actions: [],
  role_home_actions: [],
  contextual_actions: [{
    action_xmlid: 'x.contract_execution',
    route_kind: 'CONTEXTUAL_ROUTE',
    menu_id: 0,
    action_id: 41,
    model: 'x.execution',
    allowed_operation: 'read',
    required_capability: 'contract_read',
    context_requirements: {
      required_query: ['company_id', 'project_id', 'contract_id'],
      company_query: 'company_id',
      project_query: 'project_id',
      record_query: 'contract_id',
    },
  }],
  admin_actions: [{
    action_xmlid: 'x.user_management',
    route_kind: 'ADMIN_ROUTE',
    menu_id: 0,
    action_id: 51,
    model: 'res.users',
    allowed_operation: 'read',
    required_capability: 'business_config_admin',
    context_requirements: {},
  }],
  denied_actions: [],
  menu_containers: [],
};

const contract = normalizeRouteAuthorityContract(raw);
assert.ok(contract);
const contextual = contract.contextual_actions[0];
assert.equal(routeAuthorityContextAllowed(contextual, {}, { companyId: 3, projectId: 9 }), false);
assert.equal(routeAuthorityContextAllowed(
  contextual,
  { company_id: '3', project_id: '9', contract_id: '12' },
  { companyId: 3, projectId: 9 },
), true);
assert.equal(routeAuthorityContextAllowed(
  contextual,
  { company_id: '4', project_id: '9', contract_id: '12' },
  { companyId: 3, projectId: 9 },
), false);
assert.equal(findRouteAuthority(contract, {
  actionId: 41,
  menuId: 0,
  query: { company_id: '3', project_id: '9', contract_id: '12' },
  companyId: 3,
  projectId: 9,
})?.action_xmlid, 'x.contract_execution');
assert.equal(findRouteAuthority(contract, {
  actionId: 51,
  menuId: 0,
  query: {},
  companyId: 3,
  projectId: 9,
})?.route_kind, 'ADMIN_ROUTE');
assert.equal(findRouteAuthority(contract, {
  actionId: 999,
  menuId: 0,
  query: {},
}), null);

const shellOnly = {
  ...raw,
  principal_scope: { user_id: 8, company_id: 3, role_code: 'executive' },
  contextual_actions: [],
  admin_actions: [],
};
const shellOnlyContract = routeAuthorityForPrincipal(
  shellOnly,
  { userId: 8, companyId: 3, roleCode: 'executive' },
);
assert.ok(shellOnlyContract);
assert.equal(findRouteAuthority(shellOnlyContract, {
  actionId: 41,
  menuId: 0,
  query: {},
}), null);
assert.equal(routeAuthorityForPrincipal(
  shellOnly,
  { userId: 9, companyId: 3, roleCode: 'executive' },
), null);
assert.equal(routeAuthorityForPrincipal(
  shellOnly,
  { userId: 8, companyId: 4, roleCode: 'executive' },
), null);
assert.equal(routeAuthorityForPrincipal(
  shellOnly,
  { userId: 8, companyId: 3, roleCode: 'pm' },
), null);

console.log('[route-authority-guard] PASS');
