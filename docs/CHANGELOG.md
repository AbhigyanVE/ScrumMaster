# 📘 CHANGELOG.md

All notable changes to the **AI Scrum Master** project will be documented in this file.

This project loosely follows the principles of  
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)  
and Semantic Versioning where applicable.

---

## [3.4.2] – Stability Fixes

### Fixed
- Resolved SQL display warnings present in the previous release.

---

## [3.4.1] – Advanced Analytical Queries

### Added
- Advanced query trigger enabling:
  - Detailed project health analysis
  - Enhanced standup summaries
- Support for deeper analytical responses when the `advanced` keyword is used.

### Reference Queries
- `give me advanced health of CRO`
- `show me an advanced standup for AFSP`
- `advanced health report for PROJECT-X`
- `I need an advanced standup summary of CRO`

---

## [3.4] – Smart Query Patterns & Data Model Enhancements

### Added
- Smart query pattern detection, including:
  - Stuck ticket detection (inactive for more than 7 days)
  - Overdue task tracking
- Pattern library with 9 pre-built JIRA query patterns.
- Full support for task description field in analysis.

### Changed
- Expanded LLM output context from 1,000 to 5,000 tokens for richer responses.

### Reference Queries
- `list me all stuck tickets`
- `show me overdue tasks`
- `what tickets in AFSP are stuck`
- `show blocked issues`
- `who is overloaded on the team`
- `list unassigned high priority tickets`

### Limitations
- JIRA API fetch is capped at approximately 100 issues per project.
- LLM context window limitations may impact large datasets and summaries.

---

## [3.3.1] – Deadline Evaluation Improvements

### Added
- Accurate overdue and on-track detection using the current date.
- Senior Scrum Master–style feasibility analysis for future deadlines.

### Changed
- Optimized server-side execution with detailed logging.

### Known Issues
- Deadline feasibility cannot be reliably assessed when:
  - Issue descriptions are missing or invalid
  - Time estimates are set to 0

---

## [3.3] – Description Field Integration

### Added
- Support for JIRA issue descriptions.
- Integrated description field into analysis pipeline.

### Known Issues
- LLM system date and time were outdated and required correction.

---

## [3.2.2] – Production Deployment Improvements

### Added
- `main_for_server.py` to run the full pipeline using PM2.

### Changed
- Switched process management from `nohup` to **PM2**.
- Deployment commands documented in NOTES.

---

## [3.2.1] – Bug Fixes

### Fixed
- JSONs folder deletion logic that was not functioning correctly.

---

## [3.2] – Server Configuration

### Added
- Streamlit configuration file.
- Application configured to run on port **9096** in server environments.

---

## [3.1.3] – Scheduling Adjustment

### Changed
- Data extraction interval updated from 12 hours to 6 hours.

---

## [3.1.2] – Automation & CRON Integration

### Added
- CRON-based automation for periodic JIRA data extraction.
- `main.py` to:
  - Run the complete pipeline continuously
  - Fetch updated JIRA data at scheduled intervals
  - Log events into task-specific logs and a centralized `event.log`

---

## [3.1.1] – Critical Bug Fixes

### Fixed
- JIRA issue due dates were not being extracted correctly.
- Deadline queries previously returned last updated date instead of due date.
- Context clearing now resets both:
  - Stored JSON context
  - LLM internal conversational context
- Context count now updates immediately upon user query submission.

---

## [3.1] – Documentation

### Added
- Initial README documentation.

---

## [3.0] – Frontend Enhancements

### Added
- Application version display on the main interface.
- Branding logo in the sidebar.

### Changed
- Redesigned Quick Stats section with a table-based layout.
- Improved sidebar spacing and overall UI readability.

---

## [2.2] – Conversational Intelligence Improvements

### Added
- Context window storing the last 5 conversations.
- Session creation support.
- Greeting and farewell handling.
- Automatic context reset when the user says “bye”.

### Fixed
- SQL and LLM unnecessarily triggering for greetings or general queries.
- Poor LLM responses when listing projects or team members.

---

## [2.1] – JIRA Issue Count Fix

### Fixed
- JIRA issue count inconsistencies.
- Backend now calculates the actual issue count during data extraction.

---

## [2.0] – Phase 2 Core Capabilities

### Added
- Pydantic models for:
  - Sprint Health Reports
  - Standup Summaries
  - Ticket Summaries
- Agent persona defined as a **Senior Scrum Master and Agile Coach**.
- Task templates for:
  - Sprint Health Analysis
  - Standup Summaries
  - Assignment Logic
  - Generic Queries
- `ValidationHandler` for error handling and fallback responses.

### Known Issues
- Conversational context partially functional; manual reset required.

---

## [1.2] – Database Introduction

### Added
- SQLite database for persistent data storage.

---

## [1.1] – Data Extraction Improvements

### Changed
- JIRA data extraction now generates individual JSON files per project.
- JSON files organized into a dedicated folder.

---

## [1.0] – Initial Release

### Added
- Initial project structure and repository setup.
- JIRA integration.
- Baseline data fetch verification checkpoint.

---

## 📌 Notes
- This changelog is intended for **developers and maintainers**.
- Detailed stakeholder-facing explanations are available in the Release Notes document linked in the README.
