# PI Agent - Privacy Guarantee

This document describes exactly what happens to your personal data, based on
a direct audit of the codebase (not a general policy statement).

## Where your data lives

**The only place your raw personal data is stored permanently is your local
`chroma_db/` folder.** That's the memory database - it exists because that's
literally the agent's job (to remember things you've told it). It never
leaves your machine unless you copy it somewhere yourself.

Nothing else in this codebase writes your personal data to disk. Verified:
no logging module usage, no `.to_csv()`/`.to_json()` exports, no file writes
anywhere except `ingest.py` reading your source files into the database.

## What gets sent to Groq (the LLM), and why

Every question you ask sends two things to Groq's API:
1. Your question text
2. The retrieved memory snippets relevant to answering it

This is necessary - the agent can't answer using your data without the LLM
seeing that data. There's no way around this while using a hosted LLM API;
this is inherent to how the whole system works, not an oversight.

**What is redacted before sending:** common structured identifiers in your
*question text* - emails, phone numbers, SSNs, credit card numbers, API
keys - are stripped before the question reaches Groq (see `privacy.py`).

**What is NOT redacted:** the retrieved memory content itself (your journal
entries, habit logs, notes). Redacting that would defeat the purpose of a
personal memory agent - it needs to actually see your data to answer
questions about it.

**A real limitation to know about:** redaction is regex-based, so it only
catches identifiers matching known patterns (emails, phone formats, etc).
It does not detect or redact names, employers, health details, or other
personal information written in free-form prose. Don't treat redaction as a
guarantee that no personal information reaches Groq - only that
structured, easily-automated identifiers are stripped from your question.

## What happens on Groq's side (outside this codebase's control)

Per Groq's current published policy (verified July 2026):
- Inference requests (your questions/answers) are **not retained by default**
- Groq is contractually prohibited from training on your inputs/outputs
  unless you explicitly grant permission
- Temporary logs may be kept up to 30 days *only* for abuse investigation
  or reliability troubleshooting
- You can enable **Zero Data Retention (ZDR)** in Groq Console -> Data
  Controls for a stronger guarantee against even that temporary logging

This part is Groq's commitment, not something this codebase can enforce.
Check console.groq.com yourself for the current state of your account
settings, since provider policies can change.

## What gets logged locally

The audit log (`privacy.build_safe_audit_log()`) records: a timestamp, a
**hash** of your question (not the question itself), which route handled
it, and the confidence tier. It never stores your raw question or answer
text. You cannot reconstruct what you asked from the audit log.

## Summary

| Data | Where it lives | Persisted? |
|---|---|---|
| Your ingested files (notes, habits, etc.) | `chroma_db/`, local | Yes - by design, this is the memory |
| Your question (redacted for known identifiers) | Sent to Groq per-query | Not by this code; per Groq policy, not by default on their side either |
| Retrieved memory content | Sent to Groq per-query | Same as above |
| Audit log | Local, hashed questions only | Yes, but no raw text recoverable from it |