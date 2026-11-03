"""Free public weather lookup using Open-Meteo (no API key required)."""
from __future__ import annotations
import json, re, sys, time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

MAX_REQUEST = 64_000
_CITY = re.compile(r"\b(?:weather|forecast|temperature|rain|humidity|wind)\b", re.I)
_HEADERS = {"User-Agent": "TARA-App/0.1 (weather lookup; Open-Meteo attribution)"}

def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers=_HEADERS, method="GET")
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(1_000_001)
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        raise ValueError("Weather service is temporarily unavailable. Try again later.") from exc
    if len(raw) > 1_000_000:
        raise ValueError("Weather service response exceeded the size limit")
    try: data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ValueError("Weather service returned invalid data") from exc
    if not isinstance(data, dict): raise ValueError("Weather service returned an unexpected response")
    return data

def _location(question: str) -> str:
    # Prefer an explicit city preposition, so "weather like in Pune" resolves cleanly.
    stop = r"\b(?:for the next|for next|next \d+ days?|for \d+ days?|today|tomorrow|now|this week|next week|right now|please|currently|forecast|weather)\b"
    match = re.search(r"\b(?:in|at|near)\s+([A-Za-z][A-Za-z .,'-]{1,80})", question, re.I)
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,'-")
        value = re.split(stop, value, flags=re.I)[0].strip(" .,'-")
        if value and value.casefold() not in {"me", "here", "there", "my location", "please", "now", "today", "tomorrow", "the", "next", "week", "day", "days"}: return value
    match = re.search(r"\b(?:weather|forecast|temperature|rain|humidity|wind)\b(?:\s+(?:in|at|near|for))?\s+([A-Za-z][A-Za-z .,'-]{1,80}?)(?:\s+(?:today|tomorrow|now|this week|next week|right now)\b|[?.!,]|$)", question, re.I)
    if match:
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .,'-")
        value = re.split(stop, value, flags=re.I)[0].strip(" .,'-")
        if value and value.casefold() not in {"me", "here", "there", "my location", "please", "now", "today", "tomorrow", "the", "next", "week", "day", "days"}: return value
    raise ValueError("Please include a city, e.g. 'weather in Pune'.")

def handle_request(request: Any) -> dict[str, Any]:
    started=time.monotonic()
    if not isinstance(request,dict) or set(request)-{"schema_version","request_id","session_id","module","action","inputs","workspace_root","timeout_seconds","approval_token"}:
        return {"schema_version":"1.0","request_id":"unknown","status":"invalid_request","data":{},"error":"request shape is invalid","duration_ms":0}
    rid=request.get("request_id")
    def result(status: str,data:dict[str,Any]|None=None,error:str|None=None):
        return {"schema_version":"1.0","request_id":rid if isinstance(rid,str) else "unknown","status":status,"data":data or {},"error":error,"duration_ms":max(0,int((time.monotonic()-started)*1000))}
    if request.get("schema_version")!="1.0" or request.get("module")!="weather" or not isinstance(rid,str) or not rid:
        return result("invalid_request",error="weather request is invalid")
    if request.get("action")=="health": return result("success",{"healthy":True,"provider":"Open-Meteo","remote":True})
    if request.get("action")!="forecast": return result("permission_denied",error="unsupported weather capability")
    inputs=request.get("inputs",{})
    if not isinstance(inputs,dict): return result("invalid_request",error="weather inputs are invalid")
    question=inputs.get("question","")
    if not isinstance(question,str) or len(question)>2000: return result("invalid_request",error="weather question is invalid")
    try:
        city=inputs.get("location")
        if not isinstance(city,str) or not city.strip(): city=_location(question)
        city=city.strip()
        if len(city)>100: raise ValueError("Location is too long")
        geo=_get_json("https://geocoding-api.open-meteo.com/v1/search?"+urlencode({"name":city,"count":1,"language":"en","format":"json"}))
        places=geo.get("results",[])
        if not places: raise ValueError(f"No location found for '{city}'. Try a nearby city or a more specific name.")
        place=places[0]
        lat,lon=place.get("latitude"),place.get("longitude")
        if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)): raise ValueError("Location lookup returned invalid coordinates")
        days=7 if re.search(r"\b(?:week|7 day|seven day)\b",question,re.I) else 3 if re.search(r"\b(?:3 day|three day|next few days)\b",question,re.I) else 1
        params={"latitude":lat,"longitude":lon,"current":"temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m","daily":"weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset","forecast_days":days,"timezone":"auto","temperature_unit":"celsius","wind_speed_unit":"kmh"}
        forecast=_get_json("https://api.open-meteo.com/v1/forecast?"+urlencode(params))
        current=forecast.get("current",{})
        units=forecast.get("current_units",{})
        daily=forecast.get("daily",{})
        codes={"0":"Clear","1":"Mainly clear","2":"Partly cloudy","3":"Overcast","45":"Fog","48":"Rime fog","51":"Light drizzle","53":"Drizzle","55":"Dense drizzle","61":"Slight rain","63":"Rain","65":"Heavy rain","71":"Slight snow","73":"Snow","75":"Heavy snow","80":"Rain showers","81":"Rain showers","82":"Heavy rain showers","95":"Thunderstorm","96":"Thunderstorm with hail","99":"Thunderstorm with hail"}
        code=str(current.get("weather_code",""))
        label=codes.get(code,"Conditions unavailable")
        name=", ".join(str(place.get(k)) for k in ("name","admin1","country") if place.get(k))
        lines=[f"# Weather — {name}","",f"**Now:** {label}",f"- Temperature: {current.get('temperature_2m','—')} {units.get('temperature_2m','°C')}",f"- Feels like: {current.get('apparent_temperature','—')} {units.get('apparent_temperature','°C')}",f"- Humidity: {current.get('relative_humidity_2m','—')}%",f"- Wind: {current.get('wind_speed_10m','—')} {units.get('wind_speed_10m','km/h')}",f"- Precipitation: {current.get('precipitation','—')} mm",""]
        times=daily.get("time",[])
        if isinstance(times,list) and times:
            lines += ["## Forecast"]
            for i,date in enumerate(times[:7]):
                def val(key, default="—"):
                    arr=daily.get(key,[])
                    return arr[i] if isinstance(arr,list) and i<len(arr) else default
                dcode=str(val("weather_code",""))
                lines.append(f"- **{date}:** {codes.get(dcode,'Conditions unavailable')} · {val('temperature_2m_min')}–{val('temperature_2m_max')} °C · rain chance {val('precipitation_probability_max')}%")
        lines += ["","Weather data: [Open-Meteo](https://open-meteo.com/) · Data under CC BY 4.0."]
        return result("success",{"text":"\n".join(lines),"location":name,"provider":"Open-Meteo","source_url":"https://open-meteo.com/"})
    except ValueError as exc: return result("invalid_request",error=str(exc))
    except Exception: return result("failed",error="Weather lookup failed safely. Check your connection and try again.")

def main() -> int:
    raw=sys.stdin.buffer.read(MAX_REQUEST+1)
    if len(raw)>MAX_REQUEST: result={"schema_version":"1.0","request_id":"unknown","status":"invalid_request","data":{},"error":"request exceeds the size limit","duration_ms":0}
    else:
        try: request=json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError,json.JSONDecodeError): result={"schema_version":"1.0","request_id":"unknown","status":"invalid_request","data":{},"error":"request must be UTF-8 JSON","duration_ms":0}
        else: result=handle_request(request)
    sys.stdout.write(json.dumps(result,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
