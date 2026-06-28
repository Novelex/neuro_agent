# NeuroSentio Copilot Agent — API Route Inventory

This document list all registered API endpoints, their HTTP methods, handler functions, and brief summary descriptions.

> [!NOTE]
> **Transition Route Resolution**: In some early design specifications, a route named `/tasks/{id}/transition` was mentioned. This route has been consolidated into the unified transition script route group `/transitions/generate`. Use `POST /transitions/generate` for all transition script generation.

| Method | Path | Summary / Function | Tag |
|---|---|---|---|
| `GET` | `/calendar/day-summary` | Calculate and return daily summary and scheduling recommendations. | calendar |
| `GET` | `/calendar/events` | Get all events overlapping a range, scoped to current user. | calendar |
| `DELETE` | `/calendar/events/{event_id}` | Delete a specific calendar event, scoped to user. | calendar |
| `DELETE` | `/calendar/events/{event_id}/title` | Individually purge/redact the title of a calendar event, setting it to '[reda... | calendar |
| `POST` | `/calendar/import/mock` | Import events with privacy sanitization and post-import back-to-back analysis. | calendar |
| `GET` | `/copilot/context` | Get raw Copilot context | Copilot |
| `GET` | `/copilot/dashboard` | Get Copilot dashboard | Copilot |
| `POST` | `/copilot/morning-plan` | Generate today's morning plan | MorningPlan |
| `GET` | `/copilot/morning-plan/today` | Get today's morning plan | MorningPlan |
| `GET` | `/copilot/next-action` | Get the best next action for the user | Next Action |
| `POST` | `/copilot/next-action/{prompt_id}/defer` | Defer a next action to a later time | Next Action |
| `POST` | `/copilot/next-action/{prompt_id}/done` | Mark a next action as done | Next Action |
| `POST` | `/copilot/next-action/{prompt_id}/skip` | Skip a next action | Next Action |
| `POST` | `/copilot/next-action/{prompt_id}/snooze` | Snooze a next action | Next Action |
| `POST` | `/copilot/quick-plan` | Generate a quick rule-based daily plan | Copilot |
| `POST` | `/copilot/replan` | Trigger an adaptive replan | Adaptive Replanner |
| `GET` | `/copilot/replan/events` | List recent replan events | Adaptive Replanner |
| `GET` | `/energy/history` | Get energy log history | Energy |
| `GET` | `/energy/latest` | Get latest energy log | Energy |
| `POST` | `/energy/log` | Log current energy state | Energy |
| `GET` | `/energy/patterns` | Get aggregated energy patterns | Energy |
| `GET` | `/health` | Health check | Health |
| `GET` | `/llm/usage` | Get your recent LLM usage logs | LLM Usage |
| `GET` | `/llm/usage/summary` | Get your LLM usage summary | LLM Usage |
| `GET` | `/messages` | List messages for user | Messages |
| `POST` | `/messages/import/mock` | Import mock/manual message metadata | Messages |
| `GET` | `/messages/summary` | Get message urgency summary | Messages |
| `PATCH` | `/messages/{message_id}` | Update message read/reply/draft status | Messages |
| `DELETE` | `/messages/{message_id}` | Delete a message | Messages |
| `POST` | `/messages/{message_id}/draft-reply` | Create a reply draft linked to a message | Messages |
| `DELETE` | `/messages/{message_id}/snippet` | Purge/redact snippet from a message | Messages |
| `POST` | `/micro-actions/{micro_action_id}/make-smaller` | Split a micro-action into smaller actions | MicroActions |
| `PATCH` | `/micro-actions/{micro_action_id}/status` | Update micro-action status | MicroActions |
| `GET` | `/overload/events` | Get all overload events logged for the user in the last N days. | overload |
| `POST` | `/privacy/apply-retention` | Apply data retention policies manually | Privacy |
| `GET` | `/privacy/audit-log` | Get privacy audit logs | Privacy |
| `GET` | `/privacy/preferences` | Get user privacy preferences | Privacy |
| `PATCH` | `/privacy/preferences` | Update user privacy preferences | Privacy |
| `GET` | `/profile` | Get or create user profile | Profile |
| `PUT` | `/profile` | Update user profile | Profile |
| `POST` | `/reply/draft` | Generate reply draft options | ReplyDrafter |
| `GET` | `/reply/drafts` | List reply drafts | ReplyDrafter |
| `GET` | `/reply/drafts/{draft_id}` | Get a single reply draft | ReplyDrafter |
| `PATCH` | `/reply/drafts/{draft_id}` | Update a reply draft | ReplyDrafter |
| `DELETE` | `/reply/drafts/{draft_id}` | Soft delete a reply draft | ReplyDrafter |
| `DELETE` | `/reply/drafts/{draft_id}/original-message` | Purge/redact the original message from a reply draft | ReplyDrafter |
| `GET` | `/tasks` | List tasks | Tasks |
| `POST` | `/tasks` | Create a new task | Tasks |
| `GET` | `/tasks/stuck` | Identify stuck tasks | Tasks |
| `PATCH` | `/tasks/{task_id}` | Update task fields | Tasks |
| `DELETE` | `/tasks/{task_id}` | Delete a task | Tasks |
| `POST` | `/tasks/{task_id}/decompose` | Decompose a task into micro-actions | Decomposition |
| `DELETE` | `/tasks/{task_id}/description` | Purge/redact description from a task | Tasks |
| `GET` | `/tasks/{task_id}/micro-actions` | Get all micro-actions for a task | Decomposition |
| `PATCH` | `/tasks/{task_id}/status` | Update task status | Tasks |
| `GET` | `/transitions` | List all transition scripts for the current user | Transitions |
| `POST` | `/transitions/generate` | Generate a transition script | Transitions |
| `DELETE` | `/transitions/{script_id}` | Delete a transition script | Transitions |
| `PATCH` | `/transitions/{script_id}/rating` | Rate a transition script (1–5) | Transitions |
| `POST` | `/transitions/{script_id}/used` | Mark a transition script as used | Transitions |
| `GET` | `/transitions/{transition_type}/latest` | Get latest script for a transition type | Transitions |
| `DELETE` | `/user/delete-data` | Delete all user data | Privacy |
| `GET` | `/user/export-data` | Export all user data | Privacy |

**Total Registered App Routes**: 63
