#!/usr/bin/env python3
"""Translate new videos' Hindi title/summary/chapters/headlines into English.

Runs in the scheduled workflow between two build.py passes. It only acts when
the GEMINI_API_KEY repository secret is set, translates videos that have no
entry in data/translations.json yet (max MAX_PER_RUN per run), and never fails
the workflow: an untranslated video simply shows its Hindi text (tagged
lang="hi") until the next run.
"""
import json
import os
import re
import sys
import urllib.request

import build

MODEL = os.environ.get("TRANSLATE_MODEL", "gemini-2.5-flash")
MAX_PER_RUN = 12
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """Translate this Hindi news-video metadata into natural English. Return ONLY a JSON object with exactly
the keys title (string), summary, chapters, bullets, keywords (lists of strings), and each list must have EXACTLY the
same number of items as the input list. Faithful, concise news English (headline style for title/chapters/bullets,
plain prose for summary). Keep numbers, acronyms and Latin-script text unchanged; transliterate Indian names, places
and schemes normally; write dates like '20 September 2026'. For keywords lines (date | weekday date | SEO phrases)
translate the Hindi parts and keep the English phrases. Add no commentary or facts.

INPUT:
"""


def call_api(key, payload):
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": PROMPT + json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }).encode()
    req = urllib.request.Request(API.format(model=MODEL), data=body, headers={
        "x-goog-api-key": key, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"]
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0))


def build_payload(v):
    chapters, paras, bullets, _ = build.parse_desc(v["desc"])
    _, kw = build.seo_parts(v["desc"])
    return {"title": build.clean_title(v["title"]), "summary": paras[:3], "chapters": [n for _, n in chapters],
            "bullets": bullets[:120], "keywords": kw}


def valid(src, out):
    if not isinstance(out, dict) or not isinstance(out.get("title"), str) or not out["title"].strip():
        return False
    for k in ("summary", "chapters", "bullets", "keywords"):
        if not isinstance(out.get(k), list) or len(out[k]) != len(src[k]) or not all(isinstance(x, str) and x.strip() for x in out[k]):
            return False
    return not re.search("[ऀ-ॿ]{3,}", json.dumps(out, ensure_ascii=False))


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY not set: skipping translation")
        return 0
    vids = json.loads(build.DATA.read_text(encoding="utf8"))
    tr = dict(build.TR)
    todo = [v for v in vids if v["id"] not in tr][:MAX_PER_RUN]
    done = 0
    for v in todo:
        src = build_payload(v)
        try:
            out = call_api(key, src)
        except Exception as exc:  # noqa: BLE001 -- never fail the workflow over a translation
            print("translate failed for", v["id"], exc, file=sys.stderr)
            continue
        if valid(src, out):
            tr[v["id"]] = {k: out[k] for k in ("title", "summary", "chapters", "bullets", "keywords")}
            done += 1
        else:
            print("translation rejected (shape/Hindi left) for", v["id"], file=sys.stderr)
    if done:
        build.TR_FILE.write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf8")
    print(f"translated {done} of {len(todo)} pending videos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
