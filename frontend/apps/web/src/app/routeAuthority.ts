import type { ProjectContextContract, ProjectContextOption } from '@sc/schema';

export type RouteAuthorityKind = 'PRIMARY_NAV' | 'ROLE_HOME_ACTION' | 'CONTEXTUAL_ROUTE' | 'ADMIN_ROUTE' | 'DENIED';

export interface RouteAuthorityProjectContextSnapshot {
  selected: ProjectContextOption | null;
  company_id: number | null;
  company_name: string;
  operation_strategy: string;
  operation_strategy_label: string;
}

export interface RouteAuthorityEntry {
  action_xmlid: string;
  route_kind: RouteAuthorityKind;
  menu_id: number;
  menu_xmlid: string;
  action_id: number;
  name: string;
  model: string;
  view_modes: string[];
  view_id?: number;
  domain: string;
  context: string;
  route: string;
  allowed_operation: string;
  required_capability: string;
  context_requirements: Record<string, unknown>;
  source: string;
}

export interface RouteAuthorityContract {
  contract_version: 'route_authority.v1';
  source: string;
  principal_scope: { user_id: number; company_id: number; role_code: string };
  primary_actions: RouteAuthorityEntry[];
  role_home_actions: RouteAuthorityEntry[];
  contextual_actions: RouteAuthorityEntry[];
  admin_actions: RouteAuthorityEntry[];
  denied_actions: RouteAuthorityEntry[];
  menu_containers: RouteAuthorityEntry[];
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function positiveInteger(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : 0;
}

function normalizeEntry(value: unknown, expectedKind: RouteAuthorityKind, allowContainer = false): RouteAuthorityEntry | null {
  const row = record(value);
  const actionId = positiveInteger(row.action_id);
  const actionXmlid = String(row.action_xmlid || '').trim();
  const menuId = positiveInteger(row.menu_id);
  if ((!actionId || !actionXmlid) && !(allowContainer && menuId > 0)) return null;
  if (String(row.route_kind || '') !== expectedKind) return null;
  return {
    action_xmlid: actionXmlid,
    route_kind: expectedKind,
    menu_id: menuId,
    menu_xmlid: String(row.menu_xmlid || '').trim(),
    action_id: actionId,
    name: String(row.name || '').trim(),
    model: String(row.model || '').trim(),
    view_modes: Array.isArray(row.view_modes) ? row.view_modes.map((item) => String(item || '').trim()).filter(Boolean) : [],
    view_id: positiveInteger(row.view_id) || undefined,
    domain: String(row.domain || '').trim(),
    context: String(row.context || '').trim(),
    route: String(row.route || '').trim(),
    allowed_operation: String(row.allowed_operation || '').trim(),
    required_capability: String(row.required_capability || '').trim(),
    context_requirements: record(row.context_requirements),
    source: String(row.source || '').trim(),
  };
}

export function normalizeRouteAuthorityContract(value: unknown): RouteAuthorityContract | null {
  const row = record(value);
  if (String(row.contract_version || '') !== 'route_authority.v1') return null;
  const scope = record(row.principal_scope);
  const normalizeBucket = (key: string, kind: RouteAuthorityKind) => (
    Array.isArray(row[key]) ? row[key].map((item) => normalizeEntry(item, kind)).filter(Boolean) as RouteAuthorityEntry[] : []
  );
  return {
    contract_version: 'route_authority.v1',
    source: String(row.source || '').trim(),
    principal_scope: {
      user_id: positiveInteger(scope.user_id),
      company_id: positiveInteger(scope.company_id),
      role_code: String(scope.role_code || '').trim(),
    },
    primary_actions: normalizeBucket('primary_actions', 'PRIMARY_NAV'),
    role_home_actions: normalizeBucket('role_home_actions', 'ROLE_HOME_ACTION'),
    contextual_actions: normalizeBucket('contextual_actions', 'CONTEXTUAL_ROUTE'),
    admin_actions: normalizeBucket('admin_actions', 'ADMIN_ROUTE'),
    denied_actions: normalizeBucket('denied_actions', 'DENIED'),
    menu_containers: Array.isArray(row.menu_containers)
      ? row.menu_containers
        .map((item) => {
          const kind = String(record(item).route_kind || '');
          if (!['PRIMARY_NAV', 'ROLE_HOME_ACTION', 'CONTEXTUAL_ROUTE', 'ADMIN_ROUTE'].includes(kind)) return null;
          return normalizeEntry(item, kind as RouteAuthorityKind, true);
        })
        .filter(Boolean) as RouteAuthorityEntry[]
      : [],
  };
}

export function routeAuthorityForPrincipal(
  value: unknown,
  expected: { userId: number; companyId: number; roleCode: string },
): RouteAuthorityContract | null {
  const contract = normalizeRouteAuthorityContract(value);
  const scope = contract?.principal_scope;
  if (
    !contract
    || !scope?.user_id
    || scope.user_id !== expected.userId
    || (expected.roleCode && scope.role_code !== expected.roleCode)
    || (expected.companyId > 0 && scope.company_id !== expected.companyId)
  ) return null;
  return contract;
}

export function nextRouteAuthorityProjectContext(
  current: ProjectContextContract,
  snapshot: RouteAuthorityProjectContextSnapshot,
): ProjectContextContract | null {
  const currentProjectId = positiveInteger(current.selected?.id);
  const nextProjectId = positiveInteger(snapshot.selected?.id);
  const currentCompanyId = positiveInteger(current.company_id || current.selected?.company_id);
  const nextCompanyId = positiveInteger(snapshot.company_id || snapshot.selected?.company_id);
  const currentOperation = String(current.operation_strategy || current.selected?.operation_strategy || '').trim();
  const nextOperation = String(snapshot.operation_strategy || snapshot.selected?.operation_strategy || '').trim();
  if (
    currentProjectId === nextProjectId
    && currentCompanyId === nextCompanyId
    && currentOperation === nextOperation
  ) return null;
  return {
    ...current,
    selected: snapshot.selected ?? null,
    company_id: nextCompanyId || null,
    company_name: String(snapshot.company_name || snapshot.selected?.company_name || '').trim(),
    operation_strategy: nextOperation,
    operation_strategy_label: String(
      snapshot.operation_strategy_label || snapshot.selected?.operation_strategy_label || '',
    ).trim(),
  };
}

export function routeAuthorityEntries(contract: RouteAuthorityContract | null): RouteAuthorityEntry[] {
  if (!contract) return [];
  return [
    ...contract.primary_actions,
    ...contract.role_home_actions,
    ...contract.contextual_actions,
    ...contract.admin_actions,
    ...contract.menu_containers,
  ];
}

function queryValue(query: Record<string, unknown>, key: string): string {
  const raw = query[key];
  return String(Array.isArray(raw) ? raw[0] || '' : raw || '').trim();
}

export function routeAuthorityContextAllowed(
  entry: RouteAuthorityEntry,
  query: Record<string, unknown>,
  currentScope: { companyId?: number | null; projectId?: number | null },
): boolean {
  const requirements = entry.context_requirements || {};
  const required = Array.isArray(requirements.required_query)
    ? requirements.required_query.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  if (required.some((key) => !queryValue(query, key))) return false;
  const companyKey = String(requirements.company_query || '').trim();
  const projectKey = String(requirements.project_query || '').trim();
  const recordKey = String(requirements.record_query || '').trim();
  if (companyKey && currentScope.companyId && positiveInteger(queryValue(query, companyKey)) !== currentScope.companyId) return false;
  if (projectKey && currentScope.projectId && positiveInteger(queryValue(query, projectKey)) !== currentScope.projectId) return false;
  if (recordKey && !positiveInteger(queryValue(query, recordKey))) return false;
  return true;
}

export function findRouteAuthority(
  contract: RouteAuthorityContract | null,
  input: { actionId: number; menuId: number; query: Record<string, unknown>; companyId?: number | null; projectId?: number | null },
): RouteAuthorityEntry | null {
  const entry = routeAuthorityEntries(contract).find((row) => (
    (input.actionId > 0 ? row.action_id === input.actionId : input.menuId > 0 && row.menu_id === input.menuId)
    && (input.menuId <= 0 || row.menu_id === input.menuId)
    && (input.menuId > 0 || input.actionId <= 0 || row.menu_id === 0 || row.route_kind === 'CONTEXTUAL_ROUTE')
  ));
  return entry && routeAuthorityContextAllowed(entry, input.query, input) ? entry : null;
}
