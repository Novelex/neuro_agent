# NeuroSentio Copilot Agent - API Integration Guide

This is the production-ready API integration guide for the Flutter frontend. All endpoints, request bodies, and response bodies are fully documented with **realistic production data**.

> [!IMPORTANT]
> **DO NOT blindly hardcode or expect these exact values in your frontend.** 
> The JSON payloads provided below are purely **examples** to demonstrate the exact *structure, types, and shape* of the data. Use these examples to build your Dart models (e.g., using `freezed` or `json_serializable`), but expect the actual UUIDs, strings, and timestamps to be dynamic in production. Follow the method and structure shown, not the literal placeholder values.

---

## Authentication & Headers

- **Production**:
  ```http
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR...
  ```
- **Development (if ALLOW_DEV_USER_HEADER=true)**:
  ```http
  X-User-ID: 7a834920-8b1e-4512-8706-03d408ebc31a
  ```

---

## 1. System Health
### GET `/health`
Check if the API and database are running.

**Response (200 OK):**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "db_status": "connected",
  "timestamp": "2026-07-07T10:00:00.000Z"
}
```

---

## 2. Micro-Actions & Tasks
### POST `/tasks/{task_id}/decompose`
Breaks a large task into tiny, neurodivergent-friendly micro-actions.

**Request Body:**
```json
{
  "current_energy": 45,
  "sensory_state": "overwhelmed",
  "max_actions": 5,
  "force_regenerate": false
}
```
**Response (200 OK):**
```json
{
  "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
  "mode": "normal",
  "source": "llm",
  "message": "I've broken this down into manageable steps.",
  "micro_actions": [
    {
      "id": "d72b9a4c-53e2-47f6-81aa-1c390a77f342",
      "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
      "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
      "plan_id": null,
      "parent_micro_action_id": null,
      "title": "Open the tax software",
      "description": "Just open the app and log in. You don't have to do anything else yet.",
      "duration_minutes": 5,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "medium",
      "status": "open",
      "sort_order": 0,
      "created_at": "2026-07-07T10:00:00.000Z",
      "updated_at": "2026-07-07T10:00:00.000Z"
    }
  ]
}
```

### GET `/tasks/{task_id}/micro-actions`
Returns all micro-actions for a task.

**Response (200 OK):**
```json
[
  {
    "id": "d72b9a4c-53e2-47f6-81aa-1c390a77f342",
    "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
    "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
    "plan_id": null,
    "parent_micro_action_id": null,
    "title": "Open the tax software",
    "description": "Just open the app and log in.",
    "duration_minutes": 5,
    "energy_cost": "low",
    "sensory_cost": "low",
    "friction_level": "medium",
    "status": "open",
    "sort_order": 0,
    "created_at": "2026-07-07T10:00:00.000Z",
    "updated_at": "2026-07-07T10:00:00.000Z"
  }
]
```

### PATCH `/micro-actions/{id}/status`
Allowed values: `open`, `done`, `snoozed`, `skipped`, `deferred`.

**Request Body:**
```json
{
  "status": "done"
}
```
**Response (200 OK):**
*(Returns the updated MicroAction object, exactly as above but with `"status": "done"`)*

### POST `/micro-actions/{id}/make-smaller`
Splits a micro-action that feels too big.

**Request Body:**
```json
{
  "current_energy": 20,
  "reason": "I feel too overwhelmed to start."
}
```
**Response (200 OK):**
```json
{
  "original_micro_action": {
    "id": "d72b9a4c-53e2-47f6-81aa-1c390a77f342",
    "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
    "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
    "plan_id": null,
    "parent_micro_action_id": null,
    "title": "Write the first paragraph",
    "description": null,
    "duration_minutes": 15,
    "energy_cost": "medium",
    "sensory_cost": "low",
    "friction_level": "high",
    "status": "open",
    "sort_order": 1,
    "created_at": "2026-07-07T10:00:00.000Z",
    "updated_at": "2026-07-07T10:00:00.000Z"
  },
  "smaller_actions": [
    {
      "id": "e4b67a90-33b6-4df7-8b01-8b2c4e51ab11",
      "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
      "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
      "plan_id": null,
      "parent_micro_action_id": "d72b9a4c-53e2-47f6-81aa-1c390a77f342",
      "title": "Write one sentence about the topic",
      "description": "Just one single sentence. Don't worry about flow.",
      "duration_minutes": 2,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "low",
      "status": "open",
      "sort_order": 2,
      "created_at": "2026-07-07T10:05:00.000Z",
      "updated_at": "2026-07-07T10:05:00.000Z"
    }
  ]
}
```

### GET `/micro-actions/next-action`
Returns the single best next step to take right now based on energy.

**Response (200 OK):**
```json
{
  "id": "e4b67a90-33b6-4df7-8b01-8b2c4e51ab11",
  "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
  "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
  "plan_id": null,
  "parent_micro_action_id": null,
  "title": "Write one sentence about the topic",
  "description": null,
  "duration_minutes": 2,
  "energy_cost": "low",
  "sensory_cost": "low",
  "friction_level": "low",
  "status": "open",
  "sort_order": 0,
  "created_at": "2026-07-07T10:05:00.000Z",
  "updated_at": "2026-07-07T10:05:00.000Z"
}
```

---

## 3. Daily Plans & Replanning
### POST `/copilot/morning-plan`
**Request Body:**
```json
{
  "plan_date": "2026-07-07",
  "current_energy": 60,
  "sensory_state": "calm",
  "available_minutes": 120,
  "start_time": "09:00",
  "force_regenerate": false,
  "auto_decompose": true,
  "include_transition_scripts": true
}
```
**Response (200 OK):**
```json
{
  "plan_id": "a892b10f-2b12-4c22-921f-82fa102b3c22",
  "plan_date": "2026-07-07",
  "mode": "normal",
  "summary": "Here is a gentle start to your day.",
  "total_scheduled_minutes": 45,
  "overload_risk_score": 15,
  "selected_micro_actions": [
    {
      "micro_action_id": "d72b9a4c-53e2-47f6-81aa-1c390a77f342",
      "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
      "title": "Review emails for 10 minutes",
      "description": null,
      "scheduled_time": "09:00",
      "duration_minutes": 10,
      "energy_cost": "low",
      "sensory_cost": "low",
      "friction_level": "low",
      "status": "open"
    }
  ],
  "recovery_blocks": [
    {
      "title": "Sensory break",
      "reason": "To prevent midday burnout",
      "suggested_duration_minutes": 15
    }
  ],
  "transition_suggestions": [
    {
      "transition_type": "starting_work",
      "title": "Boot up sequence",
      "script_preview": "Get your favorite drink and sit down."
    }
  ],
  "message": "Plan created successfully.",
  "created_at": "2026-07-07T10:00:00.000Z"
}
```

### GET `/copilot/morning-plan/today`
Returns the same response schema as `POST /copilot/morning-plan`.

### POST `/copilot/replan`
Adjusts the remaining day.

**Request Body:**
```json
{
  "trigger": "low_energy",
  "current_energy": 20,
  "notes": "I need a break"
}
```
**Response (200 OK):**
```json
{
  "plan_id": "a892b10f-2b12-4c22-921f-82fa102b3c22",
  "mode": "recovery",
  "adjustments_made": [
    "Removed high-energy tasks for the rest of the day.",
    "Added a 30-minute recovery block."
  ]
}
```

---

## 4. Communication & Context
### POST `/reply/draft`
**Request Body:**
```json
{
  "original_message": "Hey, can we schedule a call for tomorrow at 9 AM?",
  "message_sender": "Alex",
  "message_subject": "Call tomorrow",
  "message_channel": "slack",
  "user_intent": "delay to next week",
  "preferred_tone": "friendly",
  "context_note": "I have another big deadline.",
  "include_boundary_option": true,
  "max_length": "short",
  "current_energy": 30
}
```
**Response (201 Created):**
```json
{
  "id": "f019bc2a-89a1-432d-9871-3bc876a4df87",
  "user_id": "7a834920-8b1e-4512-8706-03d408ebc31a",
  "source_type": "slack",
  "original_message": "Hey, can we schedule a call for tomorrow at 9 AM?",
  "message_sender": "Alex",
  "message_subject": "Call tomorrow",
  "message_channel": "slack",
  "user_intent": "delay to next week",
  "preferred_tone": "friendly",
  "context_note": "I have another big deadline.",
  "draft_options": [
    {
      "type": "short",
      "text": "I'm swamped tomorrow, can we do next week?"
    },
    {
      "type": "warm",
      "text": "Hey Alex, I'd love to chat, but my schedule is full tomorrow. How does next week look for you?"
    },
    {
      "type": "detailed",
      "text": "Hey Alex, tomorrow is booked solid for me with another deadline. I have time next Tuesday. Let me know what works."
    },
    {
      "type": "boundary",
      "text": "I am currently at capacity and cannot take any calls tomorrow."
    }
  ],
  "selected_option_type": null,
  "edited_reply": null,
  "status": "drafted",
  "source": "llm",
  "created_at": "2026-07-07T10:00:00.000Z",
  "updated_at": "2026-07-07T10:00:00.000Z"
}
```

### POST `/transitions/generate`
**Request Body:**
```json
{
  "transition_type": "starting_work",
  "current_energy": 50,
  "sensory_state": "normal",
  "next_task_title": "Check emails",
  "context_note": "I feel unmotivated.",
  "max_steps": 3
}
```
**Response (200 OK):**
```json
{
  "id": "c18d3a77-9b2a-43cf-8a21-99c56fa7dd11",
  "transition_type": "starting_work",
  "title": "Morning Bootup",
  "script_steps": [
    "Fill up your water bottle.",
    "Put on your noise-canceling headphones.",
    "Open only the single app you need for the first task."
  ],
  "source": "llm",
  "message": "Transition script generated."
}
```

### GET `/context/tasks/analysis`
**Response (200 OK):**
```json
{
  "total_open_tasks": 12,
  "total_stuck_tasks": 2,
  "analysis": {
    "stuck_tasks": [
      {
        "task_id": "b3c66227-6f89-43c2-a4f6-8c13bc54df11",
        "title": "Submit expense report",
        "days_stuck": 14,
        "reason": null
      }
    ],
    "identified_patterns": [
      "You tend to avoid admin tasks that require multiple tabs open."
    ],
    "suggested_actions": [
      "Break admin tasks into 5-minute micro-actions."
    ]
  }
}
```

### GET `/context/energy/trend`
**Response (200 OK):**
```json
{
  "trend": "decreasing",
  "message": "Your energy has been dropping for 3 days.",
  "average_energy_7d": 35.5,
  "suggestions": [
    "Consider activating recovery mode today."
  ]
}
```

### POST `/copilot/detect-overload`
**Request Body:** *(Empty JSON)*
```json
{}
```
**Response (200 OK):**
```json
{
  "overload_detected": true,
  "risk_score": 75,
  "reason": "Multiple missed tasks and consistently low energy.",
  "recommended_action": "Activate recovery mode immediately."
}
```

### POST `/copilot/activate-recovery`
**Request Body:** *(Empty JSON)*
```json
{}
```
**Response (200 OK):**
```json
{
  "success": true,
  "message": "Recovery mode activated. High-energy tasks deferred.",
  "actions_taken": 4
}
```