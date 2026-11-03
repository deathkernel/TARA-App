"""Bounded, offline study utilities using only supplied source material."""
from __future__ import annotations
import base64, binascii, io, json, re, sys, time
from collections.abc import Mapping
from typing import Any

MAX_REQUEST_BYTES = 16_000_000
MAX_SOURCE_CHARS = 200_000
_ALLOWED = {"schema_version", "request_id", "session_id", "module", "action", "inputs", "workspace_root", "timeout_seconds", "approval_token"}
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")

def _result(rid: str, status: str, data: dict[str, Any] | None = None, error: str | None = None, started: float | None = None) -> dict[str, Any]:
    return {"schema_version":"1.0","request_id":rid,"status":status,"data":data or {},"error":error,"duration_ms":max(0,int((time.monotonic()-started)*1000)) if started else 0}

def _source(inputs: Mapping[str, Any]) -> str:
    chunks = []
    direct = inputs.get("source_text", "")
    if direct and not isinstance(direct, str): raise ValueError("source_text must be a string")
    if direct: chunks.append(direct)
    attachments = inputs.get("attachments", [])
    if not isinstance(attachments, list) or len(attachments) > 4: raise ValueError("attachments must be a list of at most four files")
    for item in attachments:
        if not isinstance(item, Mapping): raise ValueError("attachment metadata is invalid")
        name, media, encoded = item.get("name", ""), item.get("media_type", ""), item.get("content_base64")
        if not isinstance(name, str) or len(name) > 255 or not isinstance(media, str): raise ValueError("attachment metadata is invalid")
        if not isinstance(encoded, str): continue
        if len(encoded) > 14_000_000: raise ValueError("attachment exceeds the study input limit")
        try: raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc: raise ValueError("attachment content is invalid base64") from exc
        if name.casefold().endswith(".pdf") or media.casefold() == "application/pdf":
            try: from pypdf import PdfReader
            except ImportError as exc: raise ValueError("PDF support requires: pip install tara-app-core[study]") from exc
            try:
                reader = PdfReader(io.BytesIO(raw), strict=True)
                if len(reader.pages) > 200: raise ValueError("PDF exceeds the 200-page study limit")
                page_text = []
                extracted_chars = 0
                for page in reader.pages:
                    extracted = page.extract_text() or ""
                    extracted_chars += len(extracted)
                    if extracted_chars > MAX_SOURCE_CHARS:
                        raise ValueError("extracted PDF text exceeds 200,000 characters")
                    page_text.append(extracted)
                chunks.append("\n".join(page_text))
            except ValueError: raise
            except Exception as exc: raise ValueError("PDF could not be read; scanned PDFs need OCR first") from exc
        elif name.casefold().endswith((".txt",".md",".markdown",".rst",".csv")) or media.casefold().startswith("text/"):
            try: chunks.append(raw.decode("utf-8-sig"))
            except UnicodeDecodeError as exc: raise ValueError("text attachments must use UTF-8") from exc
        else: raise ValueError("Study Mode supports text, Markdown and text-based PDF files")
    text = "\n\n".join(part for part in chunks if part.strip()).strip()
    if len(text) > MAX_SOURCE_CHARS: raise ValueError("combined study source exceeds 200,000 characters")
    return text

def _sentences(source: str) -> list[tuple[int,str]]:
    found = []
    for line_no, line in enumerate(source.splitlines(), 1):
        for sentence in _SENTENCE.split(line.strip()):
            clean = re.sub(r"\s+", " ", sentence).strip(" -*#\t")
            if len(clean) >= 24: found.append((line_no, clean[:700]))
    return found[:200]

def _notes(source: str) -> str:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines: raise ValueError("No readable text found in the study source")
    topics = [line.lstrip("# ").strip() for line in lines if line.startswith("#")]
    sentences = _sentences(source)
    output = ["# Study Notes", "", "**Source-grounded:** extracted from your supplied material; not independently verified.", ""]
    if topics: output += ["## Topics"] + [f"- {topic[:160]}" for topic in topics[:20]] + [""]
    output += ["## Key points"] + [f"- {sentence}" for _,sentence in sentences[:30]]
    if not sentences: output += [f"- {line[:700]}" for line in lines[:30]]
    return "\n".join(output)

def _cards(source: str, count: int) -> list[dict[str, Any]]:
    sentences = _sentences(source)
    if not sentences: raise ValueError("Add source text with at least one complete sentence")
    result = []
    for index,(line_no,sentence) in enumerate(sentences[:count],1):
        terms = re.findall(r"\b[A-Za-z][A-Za-z-]{4,}\b", sentence)
        term = max(terms,key=len) if terms else sentence.split()[0]
        prompt = re.sub(rf"\b{re.escape(term)}\b","_____",sentence,count=1,flags=re.I)
        result.append({"id":index,"front":f"Complete the statement: {prompt}","back":sentence,"source_line":line_no})
    return result

def _plan(question: str, days: int) -> str:
    subject = re.sub(r"\b\d{1,2}\s*days?\b"," ",question,flags=re.I)
    subject = re.sub(r"\b(make|create|give|build|a|an|the|study|revision|plan|for|in)\b"," ",subject,flags=re.I)
    subject = re.sub(r"\s+"," ",subject).strip(" .,:-") or "your subject"
    sessions = [("Map the syllabus","List topics and mark unfamiliar areas."),("Learn core concepts","Study one small topic and write notes in your own words."),("Active recall","Answer without looking at notes; mark weak topics."),("Practice","Solve textbook questions and explain each answer."),("Review mistakes","Revisit incorrect answers and make flashcards."),("Mixed revision","Mix old and new topics in a timed practice set."),("Self-test","Take a closed-book test and schedule the next review.")]
    out=[f"# {days}-Day Study Plan: {subject}","","Adjust the workload to your syllabus and available time.",""]
    for day in range(1,days+1):
        title,task=sessions[(day-1)%len(sessions)]
        out += [f"## Day {day} — {title}",f"- {task}","- Finish with a 5-minute recall check."]
    return "\n".join(out)

def handle_request(request: Any) -> dict[str, Any]:
    started=time.monotonic()
    if not isinstance(request,Mapping) or set(request)-_ALLOWED: return _result("unknown","invalid_request",error="request shape is invalid",started=started)
    rid=request.get("request_id")
    if not isinstance(rid,str) or not rid.strip() or len(rid)>128: return _result("unknown","invalid_request",error="request_id is invalid",started=started)
    if request.get("schema_version")!="1.0" or request.get("module")!="study": return _result(rid,"invalid_request",error="module or schema version is invalid",started=started)
    action,inputs=request.get("action"),request.get("inputs",{})
    if action=="health": return _result(rid,"success",{"healthy":True,"offline":True},started=started)
    if action!="create" or not isinstance(inputs,Mapping): return _result(rid,"permission_denied",error="unsupported TARA-Study capability",started=started)
    question=inputs.get("question","")
    if not isinstance(question,str) or len(question)>20_000: return _result(rid,"invalid_request",error="question is invalid",started=started)
    try:
        count=inputs.get("count",10)
        if not isinstance(count,int) or isinstance(count,bool) or not 1<=count<=50: raise ValueError("count must be between 1 and 50")
        match=re.search(r"\b(\d{1,2})\s*days?\b",question,re.I)
        if "plan" in question.casefold() and ("study" in question.casefold() or "revision" in question.casefold()):
            days=int(match.group(1)) if match else 7
            if not 1<=days<=30: raise ValueError("study plans support 1 to 30 days")
            data={"kind":"study_plan","text":_plan(question,days),"source_grounded":False}
        else:
            source=_source(inputs)
            if not source: raise ValueError("Attach a text/Markdown file or text-based PDF, or provide source_text, for source-grounded notes, quizzes and flashcards")
            lowered=question.casefold()
            if re.search(r"\bflash.?cards?\b",lowered):
                cards=_cards(source,count)
                text="# Flashcards\n\n"+"\n\n".join(f"**Q{c['id']}.** {c['front']}\n\n**Answer:** {c['back']} *(source line {c['source_line']})*" for c in cards)
                data={"kind":"flashcards","items":cards,"text":text,"source_grounded":True}
            elif re.search(r"\b(quiz|mcq|practice questions?)\b",lowered):
                cards=_cards(source,count)
                items=[{"id":c["id"],"question":c["front"].replace("Complete the statement: ",""),"answer":c["back"],"source_line":c["source_line"],"type":"short_answer"} for c in cards]
                text="# Practice Quiz\n\n"+"\n\n".join(f"**Q{q['id']}.** {q['question']}\n\nAnswer: {q['answer']} *(source line {q['source_line']})*" for q in items)
                data={"kind":"quiz","items":items,"text":text,"source_grounded":True}
            else: data={"kind":"notes","text":_notes(source),"source_grounded":True}
    except ValueError as exc: return _result(rid,"invalid_request",error=str(exc),started=started)
    return _result(rid,"success",data,started=started)

def main() -> int:
    raw=sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
    if len(raw)>MAX_REQUEST_BYTES: result=_result("unknown","invalid_request",error="request exceeds the size limit")
    else:
        try: request=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): result=_result("unknown","invalid_request",error="request must be UTF-8 JSON")
        else: result=handle_request(request)
    sys.stdout.write(json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
    return 0

if __name__=="__main__": raise SystemExit(main())
