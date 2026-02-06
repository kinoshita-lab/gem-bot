# Plan: Split README.md

## Goal
Separate English and Japanese content in `README.md` into `README.md` (English) and `README.ja.md` (Japanese).

## Steps
1.  **Read `README.md`** to load current content.
2.  **Generate `README.ja.md`**:
    -   Extract Japanese sections:
        -   Header (Lines 5-6)
        -   Features (Lines 25-40)
        -   System Prompts (Lines 256-337)
        -   Git Version Control (Lines 340-466)
        -   Prerequisites (Lines 613-710)
        -   Setup (Lines 713-898)
        -   Commands (Lines 984-1065)
        -   Channel Config (Lines 1087-1104)
        -   System Prompt Summary (Lines 1126-1143)
        -   History (Lines 1159-1169)
        -   Google Integration (Lines 1214-1253)
        -   i18n (Lines 1275-1291)
        -   Config File (Lines 1314-1330)
        -   Project Structure (Header 1366, Tree from EN 1335-1364)
        -   Systemd (Lines 1441-1508)
    -   Assemble with proper formatting.
3.  **Update `README.md`**:
    -   Extract English sections (corresponding to the above).
    -   Add Link: `[日本語ドキュメント (Japanese)](README.ja.md)` at the top.
    -   Assemble with proper formatting.
4.  **Verify**: Ensure no content is lost and structure is preserved.

## Execution
I will use a Python script to perform the split based on line numbers and content analysis to ensure precision.
