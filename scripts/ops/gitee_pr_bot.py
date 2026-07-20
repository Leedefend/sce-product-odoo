#!/usr/bin/env python3
"""Fail-closed PR automation for one approved governance commit."""
from __future__ import annotations
import argparse, json, os, stat, urllib.error, urllib.request
from pathlib import Path

API="https://gitee.com/api/v5"; OWNER="leegege"; REPO="sce-product-odoo"
SOURCE="fix/gitee-github-mirror-governance"; TARGET="main"
HEAD="e2c6aebca5a702ab273081e9fe2c154391155da7"; BOT="sce-ci-bot"

def request(token, method, path, payload=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(f"{API}{path}",data=data,method=method,
        headers={"Authorization":f"token {token}","Content-Type":"application/json","Accept":"application/json","User-Agent":"sce-pr-bot/1"})
    try:
        with urllib.request.urlopen(req,timeout=30) as res: raw=res.read(); status=res.status
    except urllib.error.HTTPError as exc: raw=exc.read(); status=exc.code
    body=json.loads(raw) if raw else {}
    if status not in {200,201,204}:
        message=body.get("message") if isinstance(body,dict) else ""
        raise RuntimeError(f"api_failed method={method} status={status} message={message}")
    return body

def branch_sha(token, branch):
    row=request(token,"GET",f"/repos/{OWNER}/{REPO}/branches/{urllib.parse.quote(branch,safe='')}")
    return (row.get("commit") or {}).get("sha")

def head_data(pr):
    head=pr.get("head") or {}
    return head.get("sha") or (head.get("commit") or {}).get("sha"), head.get("ref") or head.get("label"), head

def matching(pr):
    sha,ref,_=head_data(pr); base=pr.get("base") or {}
    return (ref==SOURCE or str(ref).endswith(":"+SOURCE)) and base.get("ref")==TARGET and sha==HEAD

def matching_pulls(token, state="all"):
    pulls=request(token,"GET",f"/repos/{OWNER}/{REPO}/pulls?state={state}&per_page=100")
    return [p for p in pulls if matching(p)]

def find_or_create(token):
    if request(token,"GET","/user").get("login") != BOT: raise RuntimeError("bot_identity_mismatch")
    if branch_sha(token,SOURCE)!=HEAD: raise RuntimeError("source_head_changed")
    candidates=matching_pulls(token)
    if len(candidates)>1: raise RuntimeError("duplicate_pr_for_fixed_head")
    if candidates: return candidates[0],"existing"
    pr=request(token,"POST",f"/repos/{OWNER}/{REPO}/pulls",{
      "title":"ci: enforce Gitee-authoritative GitHub mirroring", "head":SOURCE,"base":TARGET,
      "body":"Machine-governance-only PR. Fixed HEAD: `"+HEAD+"`.\n\nArchitecture Impact: P4 operations governance\nLayer Target: Gitee authoritative mirroring\nAffected Modules: scripts/ci, scripts/ops, deploy/gitee-mirror, Make governance"})
    if not matching(pr): raise RuntimeError("created_pr_identity_mismatch")
    return pr,"created"

def status(token):
    if request(token,"GET","/user").get("login") != BOT: raise RuntimeError("bot_identity_mismatch")
    candidates=matching_pulls(token)
    if len(candidates)!=1: raise RuntimeError("fixed_head_pr_not_unique")
    return candidates[0]

def merge(token, number, evidence):
    required={"HEAD":HEAD,"PUBLIC_GUARD":"PASS","PROFESSIONAL_QUALITY_GATE":"PASS","RELEASE_SCAN":"12/12","SENSITIVE_LOG_MARKERS":"0","WORKSPACE_CLEAN":"true"}
    if any(str(evidence.get(k))!=v for k,v in required.items()): raise RuntimeError("evidence_not_accepted")
    pr=request(token,"GET",f"/repos/{OWNER}/{REPO}/pulls/{number}")
    if not matching(pr): raise RuntimeError("pr_head_or_target_changed")
    _,_,head=head_data(pr)
    repo=(head.get("repo") or head.get("repository") or {})
    if repo and repo.get("full_name") not in {f"{OWNER}/{REPO}",None}: raise RuntimeError("fork_pr_denied")
    if pr.get("mergeable") is False: raise RuntimeError("pr_not_mergeable")
    request(token,"PUT",f"/repos/{OWNER}/{REPO}/pulls/{number}/merge",{"merge_method":"squash","prune_source_branch":False,"title":pr.get("title")})

def main():
    p=argparse.ArgumentParser(); p.add_argument("action",choices=("create","status","merge")); p.add_argument("--token-file",type=Path,required=True); p.add_argument("--number",type=int); p.add_argument("--evidence",type=Path)
    a=p.parse_args()
    token_stat=a.token_file.stat()
    if not stat.S_ISREG(token_stat.st_mode) or token_stat.st_uid != os.getuid() or token_stat.st_mode & 0o077:
        raise SystemExit("token file must be an owner-only regular file")
    token=a.token_file.read_text().strip()
    if not token: raise SystemExit("token file is empty")
    if a.action == "create":
        pr,mode=find_or_create(token); print(f"[gitee_pr_bot] PASS action=create mode={mode} number={pr.get('number')} state={pr.get('state')} head={HEAD}")
    elif a.action == "status":
        pr=status(token); print(f"[gitee_pr_bot] PASS action=status number={pr.get('number')} state={pr.get('state')} head={HEAD}")
    else:
        if not a.number or not a.evidence: raise SystemExit("merge requires number and evidence")
        merge(token,a.number,json.loads(a.evidence.read_text())); print(f"[gitee_pr_bot] PASS action=merge number={a.number} head={HEAD}")
if __name__=="__main__": main()
