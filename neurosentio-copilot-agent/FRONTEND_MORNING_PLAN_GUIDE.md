# Frontend Integration Guide: Database-Driven Morning Plan (Simplified Payload)

## Overview
The Morning Plan API has been streamlined to completely eliminate date/time parameters and task payloads from the request:
1. **No Time Calculation**: `start_time` and time-offset scheduling logic have been removed from both frontend requests and backend LLM processing. This saves LLM reasoning time and avoids server vs client timezone discrepancies.
2. **Automatic Database Lookup**: When you call `generateMorningPlan()`, the backend automatically queries PostgreSQL for incomplete tasks assigned to today's date (`date::date = CURRENT_DATE`).

---

## 1. How to Call `generateMorningPlan` in Flutter

In your screen or state controller (e.g. `ai_morning_plan_screen.dart`), call `generateMorningPlan` with `forceRegenerate: true`:

```dart
import 'package:neurosentio_app/services/copilot_api_service.dart';
import 'package:neurosentio_app/models/copilot_api_models.dart';

final _copilotService = CopilotApiService();

Future<void> generateTodayPlan() async {
  try {
    // Calling without `startTime` or `tasks` allows the backend 
    // to automatically fetch today's tasks from PostgreSQL and generate actionable steps.
    final MorningPlan plan = await _copilotService.generateMorningPlan(
      forceRegenerate: true,  // Force LLM regeneration for today's plan
    );

    print('Generated plan with ${plan.selectedMicroActions.length} actions');
    print('Summary: ${plan.summary}');
  } catch (e) {
    print('Error generating plan: $e');
  }
}
```

---

## 2. How to Fetch Today's Existing Plan (Without Regenerating)

If a plan has already been generated for today and you want to retrieve it on screen load without calling the LLM again:

```dart
Future<void> fetchTodayExistingPlan() async {
  try {
    final MorningPlan? existingPlan = await _copilotService.getTodayMorningPlan();

    if (existingPlan != null) {
      print('Retrieved existing plan: ${existingPlan.summary}');
    } else {
      print('No plan exists for today yet. Call generateTodayPlan() first.');
    }
  } catch (e) {
    print('Error fetching existing plan: $e');
  }
}
```

---

## 3. Request Payload & Backend Processing

When the HTTP POST request is sent to `https://neuroagent-production-a167.up.railway.app/copilot/morning-plan`:

1. **Payload Sent by Frontend**:
   ```json
   {
     "force_regenerate": true
   }
   ```
2. **Backend Execution**:
   - Executes SQL query:
     ```sql
     SELECT id, title, subtitle, date 
     FROM public.planner_tasks 
     WHERE user_id = 'user-uuid' 
       AND "isCompleted" = false 
       AND (date::date = CURRENT_DATE OR date IS NULL);
     ```
   - Sends tasks to OpenRouter LLM without any time constraints or timezone logic.
   - Saves generated micro-actions into PostgreSQL and returns the structured `MorningPlan` object to Flutter.
