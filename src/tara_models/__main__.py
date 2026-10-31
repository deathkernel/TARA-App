"""Free-first model catalogue and optional Gemini inference adapter."""
from __future__ import annotations
import json, os, re, sys, time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

MAX_REQUEST = 64_000
# Only text-capable models documented with free-tier token pricing are eligible.
# Refresh this list against Google's pricing docs during maintenance; API model discovery
# is dynamic but is not itself proof of free-tier eligibility.
GEMINI_FREE_TEXT_MODELS = (
    "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite",
)
OPENAI_OPEN_WEIGHT_MODELS = (
    {"id":"gpt-oss:20b","provider":"ollama","label":"OpenAI gpt-oss 20B","free":"Open weights; local compute required","minimum_memory_gb":16},
    {"id":"gpt-oss:120b","provider":"ollama","label":"OpenAI gpt-oss 120B","free":"Open weights; high-memory GPU/server required","minimum_memory_gb":80},
)
_HEADERS={"User-Agent":"TARA-App/0.1","Content-Type":"application/json"}

def _http_json(url: str, *, method: str="GET", headers:dict[str,str]|None=None, body:dict[str,Any]|None=None, timeout:int=12)->dict[str,Any]:
    raw_body=json.dumps(body).encode("utf-8") if body is not None else None
    request=Request(url,data=raw_body,headers={**_HEADERS,**(headers or {})},method=method)
    try:
        with urlopen(request,timeout=timeout) as response: raw=response.read(1_000_001)
    except HTTPError as exc:
        if exc.code in {400,401,403,404,429}: raise ValueError("Gemini rejected this request. Check the API key, free-tier model availability, and rate limits.") from exc
        raise ValueError("Model provider is temporarily unavailable.") from exc
    except (URLError,TimeoutError,OSError) as exc: raise ValueError("Model provider is unreachable. Check the network connection.") from exc
    if len(raw)>1_000_000: raise ValueError("Model provider response exceeded the size limit")
    try: data=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise ValueError("Model provider returned invalid JSON") from exc
    if not isinstance(data,dict): raise ValueError("Model provider returned an unexpected response")
    return data

def _gemini_key()->str:
    key=os.environ.get("GEMINI_API_KEY","").strip()
    if not key: raise ValueError("Gemini is optional. Set GEMINI_API_KEY in your local environment; TARA never stores or prints the key.")
    if len(key)>512 or any(ord(c)<32 for c in key): raise ValueError("GEMINI_API_KEY is invalid")
    return key

def _gemini_catalog(key:str)->list[dict[str,Any]]:
    data=_http_json("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",headers={"x-goog-api-key":key,"Content-Type":"application/json"})
    live={item.get("name","").removeprefix("models/"):item for item in data.get("models",[]) if isinstance(item,dict)}
    result=[]
    for model in GEMINI_FREE_TEXT_MODELS:
        item=live.get(model)
        if item and "generateContent" in item.get("supportedGenerationMethods",[]):
            result.append({"id":model,"provider":"gemini","label":item.get("displayName",model),"free":"Free-tier eligible where enabled for your project; quotas apply","context_window":item.get("inputTokenLimit"),"output_limit":item.get("outputTokenLimit")})
    return result

def _ollama_catalog()->list[dict[str,Any]]:
    try:
        data=_http_json("http://127.0.0.1:11434/api/tags",timeout=3)
        return [{"id":item.get("name"),"provider":"ollama","label":item.get("name"),"free":"Local model; hardware and disk required"} for item in data.get("models",[]) if isinstance(item,dict) and isinstance(item.get("name"),str)]
    except ValueError: return []

def _generate_gemini(question:str,model:str)->str:
    if model not in GEMINI_FREE_TEXT_MODELS: raise ValueError("That model is not on TARA's free-tier text allowlist.")
    key=_gemini_key()
    available={item["id"] for item in _gemini_catalog(key)}
    if model not in available: raise ValueError("This model is not currently available to this Gemini API project on the free-tier catalogue.")
    prompt=("You are TARA, a helpful assistant. Answer clearly and directly. Start with a one-sentence answer, then use short headings and bullets. Avoid repeated conclusions, raw metadata, and unnecessary filler. State uncertainty and never invent sources.\n\nUser request:\n"+question)
    data=_http_json("https://generativelanguage.googleapis.com/v1beta/models/"+model+":generateContent",method="POST",headers={"x-goog-api-key":key},body={"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.4,"maxOutputTokens":4096}},timeout=45)
    candidates=data.get("candidates",[])
    if not candidates: raise ValueError("Gemini returned no answer; the free-tier quota may be exhausted.")
    parts=candidates[0].get("content",{}).get("parts",[])
    text="\n".join(part.get("text","") for part in parts if isinstance(part,dict) and isinstance(part.get("text"),str)).strip()
    if not text: raise ValueError("Gemini returned an empty text response.")
    return text

def handle_request(request:Any)->dict[str,Any]:
    started=time.monotonic()
    def result(rid:str,status:str,data:dict[str,Any]|None=None,error:str|None=None):
        return {"schema_version":"1.0","request_id":rid,"status":status,"data":data or {},"error":error,"duration_ms":max(0,int((time.monotonic()-started)*1000))}
    if not isinstance(request,dict) or set(request)-{"schema_version","request_id","session_id","module","action","inputs","workspace_root","timeout_seconds","approval_token"}: return result("unknown","invalid_request",error="request shape is invalid")
    rid=request.get("request_id")
    if not isinstance(rid,str) or not rid.strip() or len(rid)>128: return result("unknown","invalid_request",error="request_id is invalid")
    if request.get("schema_version")!="1.0" or request.get("module")!="models": return result(rid,"invalid_request",error="module or schema version is invalid")
    inputs=request.get("inputs",{})
    if not isinstance(inputs,dict): return result(rid,"invalid_request",error="model inputs are invalid")
    action=request.get("action")
    if action=="health": return result(rid,"success",{"healthy":True,"provider":"free-first model hub","gemini_configured":bool(os.environ.get("GEMINI_API_KEY","").strip()),"local_models_supported":True})
    try:
        if action=="catalog":
            local=_ollama_catalog()
            free_models=[]
            key=os.environ.get("GEMINI_API_KEY","").strip()
            if key:
                try: free_models=_gemini_catalog(_gemini_key())
                except ValueError: free_models=[]
            catalog_models=free_models or [
                {"id":model,"provider":"gemini","label":model,"free":"Documented free-tier text candidate; set GEMINI_API_KEY to verify live project availability"}
                for model in GEMINI_FREE_TEXT_MODELS
            ]
            gemini_lines="\\n".join("- "+item["id"]+" — "+item["free"] for item in catalog_models)
            sections=[
                "# Free Model Hub",
                "## OpenAI open-weight models (local)",
                "- gpt-oss:20b — Apache 2.0 weights; approx. 16 GB memory minimum",
                "- gpt-oss:120b — Apache 2.0 weights; approx. 80 GB memory recommended",
                "## Gemini API free-tier text models",
                gemini_lines,
                "## BharatCode hosted model (explicit opt-in)",
                "- qwen-3.8-27b — BharatCode Qwen 3.8 27B; requires BHARATCODE_API_KEY and verified account access",
                "## Existing OpenAI-origin local capability",
                "- Whisper transcription is available through TARA-Voice's optional faster-whisper backend; it runs locally after model setup.",
                "## Installed local Ollama models",
                "\\n".join("- "+item["id"] for item in local) if local else "- Ollama is not running or no local models are installed.",
                "Free limits change; Gemini quotas and availability depend on your project. No paid OpenAI API is called."
            ]
            return result(rid,"success",{"text":"\\n\\n".join(sections),"models":catalog_models+[{"id":"qwen-3.8-27b","provider":"bharatcode","label":"BharatCode Qwen 3.8 27B","free":"Student access requires verified eligibility; paid plans also available"}]+list(OPENAI_OPEN_WEIGHT_MODELS)+local,"provider":"TARA Model Hub"})
        if action!="generate": return result(rid,"permission_denied",error="unsupported model capability")
        question=inputs.get("question")
        if not isinstance(question,str) or not question.strip() or len(question)>20000: return result(rid,"invalid_request",error="question is invalid")
        model=inputs.get("model")
        if not isinstance(model,str) or not model:
            selection=re.match(r"\s*(?:please\s+)?(?:use|switch to|try|ask|run with)\s+(?:(?:the|openai)\s+)?(gemini-[a-z0-9.-]+|gpt-oss(?::[a-z0-9.-]+)?|qwen-3\\.8-27b|gemini)\s*[:,-]?\s*",question,re.I)
            model=selection.group(1).lower() if selection else "gemini-3.5-flash-lite"
            if selection: question=question[selection.end():].strip() or question
            if model=="gemini": model="gemini-3.5-flash-lite"
            if model=="gpt-oss": model="gpt-oss:20b"
        if not isinstance(model,str) or len(model)>100: return result(rid,"invalid_request",error="model name is invalid")
        if model == "qwen-3.8-27b":
            from tara_app.providers.bharatcode import BharatCodeProvider
            provider = BharatCodeProvider.from_env()
            text = provider.complete(question, system="You are TARA, a helpful assistant. Answer clearly and directly.", max_completion_tokens=4096, temperature=0.4)
            return result(rid,"success",{"text":text,"provider":"BharatCode","model":provider.model,"remote_data_transfer":True})
        if model.startswith("gemini-"):
            text=_generate_gemini(question,model)
            return result(rid,"success",{"text":text,"provider":"Gemini API","model":model,"free_tier_only":True,"remote_data_transfer":True})
        if model.startswith("gpt-oss:"):
            catalog={item["id"] for item in _ollama_catalog()}
            if model not in catalog: raise ValueError(f"{model} is not installed. After checking your RAM/VRAM, install it with 'ollama pull {model}'. Large model downloads are never started automatically.")
            data=_http_json("http://127.0.0.1:11434/api/chat",method="POST",body={"model":model,"stream":False,"messages":[{"role":"system","content":"You are TARA. Answer clearly and directly, with a one-sentence answer followed by short headings or bullets. Avoid repeated conclusions, raw metadata, and unnecessary filler."},{"role":"user","content":question}],"options":{"temperature":0.4}},timeout=120)
            text=data.get("message",{}).get("content","").strip()
            if not text: raise ValueError("Local model returned an empty response.")
            return result(rid,"success",{"text":text,"provider":"Ollama (local)","model":model,"remote_data_transfer":False})
        raise ValueError("Select a supported free Gemini text model or installed local gpt-oss model.")
    except ValueError as exc: return result(rid,"unavailable",error=str(exc))
    except Exception: return result(rid,"failed",error="Model request failed safely. Check provider availability and local logs without exposing API keys.")

def main()->int:
    raw=sys.stdin.buffer.read(MAX_REQUEST+1)
    if len(raw)>MAX_REQUEST: output={"schema_version":"1.0","request_id":"unknown","status":"invalid_request","data":{},"error":"request exceeds the size limit","duration_ms":0}
    else:
        try: request=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): output={"schema_version":"1.0","request_id":"unknown","status":"invalid_request","data":{},"error":"request must be UTF-8 JSON","duration_ms":0}
        else: output=handle_request(request)
    sys.stdout.write(json.dumps(output,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
