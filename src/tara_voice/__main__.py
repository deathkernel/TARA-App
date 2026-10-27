"""One-request JSON-over-stdio adapter for TARA."""
from __future__ import annotations
import json,sys,time
from .service import MODULE_ID,execute
MAX_REQUEST_BYTES=1_000_000
_ALLOWED={"schema_version","request_id","session_id","module","action","inputs","workspace_root","timeout_seconds","approval_token"}
def _reply(rid,status,data,error,duration):
    sys.stdout.write(json.dumps({"schema_version":"1.0","request_id":rid,"status":status,"data":data,"error":error,"duration_ms":duration},ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
def main():
    raw=sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
    if len(raw)>MAX_REQUEST_BYTES: _reply("unknown","invalid_request",{},"request exceeds the size limit",0);return 0
    try: req=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError): _reply("unknown","invalid_request",{},"request must be UTF-8 JSON",0);return 0
    if not isinstance(req,dict) or set(req)-_ALLOWED: _reply("unknown","invalid_request",{},"request shape is invalid",0);return 0
    rid=req.get("request_id")
    if not isinstance(rid,str) or not rid.strip() or len(rid)>128: _reply("unknown","invalid_request",{},"request_id is invalid",0);return 0
    if req.get("schema_version")!="1.0" or req.get("module")!=MODULE_ID: _reply(rid,"invalid_request",{},"module or schema version is invalid",0);return 0
    action,inputs=req.get("action"),req.get("inputs",{})
    if not isinstance(action,str) or not isinstance(inputs,dict): _reply(rid,"invalid_request",{},"action or inputs are invalid",0);return 0
    if action=="health": _reply(rid,"success",{"healthy":True},None,0);return 0
    start=time.monotonic()
    try:
        status,data,error=execute(action,inputs,approval_token=req.get("approval_token"))
        if not isinstance(data,dict): raise ValueError("invalid result data")
    except ValueError as exc: status,data,error="invalid_request",{},str(exc)[:500]
    except Exception: status,data,error="failed",{},"module operation failed"
    _reply(rid,status,data,error,max(0,int((time.monotonic()-start)*1000)));return 0
if __name__=="__main__": raise SystemExit(main())

