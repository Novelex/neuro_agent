-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.users (
  id uuid NOT NULL,
  name text NOT NULL,
  email text NOT NULL,
  phone text,
  emergency_contact text,
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT users_pkey PRIMARY KEY (id),
  CONSTRAINT users_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);
CREATE TABLE public.energy_logs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  user_id uuid NOT NULL,
  level integer NOT NULL CHECK (level >= 0 AND level <= 10),
  timestamp timestamp with time zone NOT NULL,
  CONSTRAINT energy_logs_pkey PRIMARY KEY (id),
  CONSTRAINT energy_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.panic_events (
  user_id uuid NOT NULL,
  timestamp timestamp with time zone NOT NULL,
  safe_mode_end timestamp with time zone,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT panic_events_pkey PRIMARY KEY (id),
  CONSTRAINT panic_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.safety_contacts (
  user_id uuid NOT NULL,
  name text NOT NULL,
  phone text NOT NULL,
  relationship text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  CONSTRAINT safety_contacts_pkey PRIMARY KEY (id),
  CONSTRAINT safety_contacts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.settings (
  panic_message text,
  selected_tags ARRAY,
  user_id uuid NOT NULL UNIQUE,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  theme text DEFAULT 'dark'::text,
  notifications_enabled boolean DEFAULT true,
  location_enabled boolean DEFAULT true,
  haptic_feedback_enabled boolean DEFAULT true,
  updated_at timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  energy_reminders jsonb DEFAULT '[]'::jsonb,
  CONSTRAINT settings_pkey PRIMARY KEY (id),
  CONSTRAINT settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
CREATE TABLE public.planner_tasks (
  id text NOT NULL,
  user_id uuid NOT NULL,
  title text NOT NULL,
  subtitle text NOT NULL DEFAULT ''::text,
  time text NOT NULL DEFAULT ''::text,
  isCompleted boolean NOT NULL DEFAULT false,
  date timestamp with time zone NOT NULL DEFAULT now(),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  dotColorValue bigint NOT NULL DEFAULT 0,
  cardColorValue bigint NOT NULL DEFAULT 0,
  remindMe boolean DEFAULT false,
  notificationId bigint,
  CONSTRAINT planner_tasks_pkey PRIMARY KEY (id),
  CONSTRAINT planner_tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.llm_usage_logs (
  user_id uuid NOT NULL,
  feature text NOT NULL,
  provider text NOT NULL,
  model text,
  latency_ms integer,
  estimated_cost_usd numeric,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'success'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT llm_usage_logs_pkey PRIMARY KEY (id),
  CONSTRAINT llm_usage_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.ai_micro_actions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  duration_minutes integer DEFAULT 5,
  energy_cost text DEFAULT 'low'::text,
  sensory_cost text DEFAULT 'low'::text,
  friction_level text DEFAULT 'low'::text,
  status text NOT NULL DEFAULT 'open'::text,
  sort_order integer DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_id uuid NOT NULL,
  task_id text,
  plan_id uuid,
  parent_id uuid,
  title text NOT NULL,
  description text,
  CONSTRAINT ai_micro_actions_pkey PRIMARY KEY (id),
  CONSTRAINT ai_micro_actions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.ai_morning_plans (
  user_id uuid NOT NULL,
  plan_date date NOT NULL,
  summary text,
  message text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  mode text NOT NULL DEFAULT 'normal'::text,
  total_scheduled_minutes integer DEFAULT 0,
  overload_risk_score integer DEFAULT 0,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT ai_morning_plans_pkey PRIMARY KEY (id),
  CONSTRAINT ai_morning_plans_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.ai_reply_drafts (
  user_id uuid NOT NULL,
  original_message text NOT NULL,
  message_sender text,
  user_intent text,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  draft_options jsonb NOT NULL DEFAULT '[]'::jsonb,
  source text NOT NULL DEFAULT 'llm'::text,
  status text NOT NULL DEFAULT 'active'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT ai_reply_drafts_pkey PRIMARY KEY (id),
  CONSTRAINT ai_reply_drafts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.ai_transition_scripts (
  user_id uuid NOT NULL,
  transition_type text NOT NULL,
  title text NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  script_steps jsonb NOT NULL DEFAULT '[]'::jsonb,
  source text NOT NULL DEFAULT 'llm'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT ai_transition_scripts_pkey PRIMARY KEY (id),
  CONSTRAINT ai_transition_scripts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
