"""add_execution_automation_pack

Revision ID: a1b2c3d4e5f6
Revises: f0fae2c4efa4
Create Date: 2026-05-21 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0fae2c4efa4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add message_items, next_action_prompts, replan_events tables."""

    # ── message_items ──────────────────────────────────────────────────
    op.create_table(
        'message_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('external_message_id', sa.String(), nullable=True),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('sender', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('snippet', sa.String(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('needs_reply', sa.Boolean(), nullable=False),
        sa.Column('urgency_score', sa.Integer(), nullable=False),
        sa.Column('detected_intent', sa.String(), nullable=False),
        sa.Column('detected_keywords', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('linked_reply_draft_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('message_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_message_items_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_message_items_user_received', ['user_id', 'received_at'], unique=False)
        batch_op.create_index('ix_message_items_urgency', ['urgency_score'], unique=False)
        batch_op.create_index('ix_message_items_needs_reply', ['needs_reply'], unique=False)
        batch_op.create_index('ix_message_items_detected_intent', ['detected_intent'], unique=False)

    # ── next_action_prompts ────────────────────────────────────────────
    op.create_table(
        'next_action_prompts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=True),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('energy_cost', sa.String(), nullable=True),
        sa.Column('sensory_cost', sa.String(), nullable=True),
        sa.Column('friction_level', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('next_action_prompts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_next_action_prompts_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_nap_status', ['status'], unique=False)
        batch_op.create_index('ix_nap_scheduled_for', ['scheduled_for'], unique=False)
        batch_op.create_index('ix_nap_source_type', ['source_type'], unique=False)
        batch_op.create_index('ix_nap_action_type', ['action_type'], unique=False)

    # ── replan_events ──────────────────────────────────────────────────
    op.create_table(
        'replan_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_details', sa.JSON(), nullable=True),
        sa.Column('previous_plan_id', sa.String(), nullable=True),
        sa.Column('new_plan_id', sa.String(), nullable=True),
        sa.Column('mode_before', sa.String(), nullable=True),
        sa.Column('mode_after', sa.String(), nullable=True),
        sa.Column('actions_preserved_count', sa.Integer(), nullable=False),
        sa.Column('actions_deferred_count', sa.Integer(), nullable=False),
        sa.Column('actions_added_count', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('replan_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_replan_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_replan_events_trigger_type', ['trigger_type'], unique=False)
        batch_op.create_index('ix_replan_events_created_at', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove message_items, next_action_prompts, replan_events tables."""

    with op.batch_alter_table('replan_events', schema=None) as batch_op:
        batch_op.drop_index('ix_replan_events_created_at')
        batch_op.drop_index('ix_replan_events_trigger_type')
        batch_op.drop_index(batch_op.f('ix_replan_events_user_id'))
    op.drop_table('replan_events')

    with op.batch_alter_table('next_action_prompts', schema=None) as batch_op:
        batch_op.drop_index('ix_nap_action_type')
        batch_op.drop_index('ix_nap_source_type')
        batch_op.drop_index('ix_nap_scheduled_for')
        batch_op.drop_index('ix_nap_status')
        batch_op.drop_index(batch_op.f('ix_next_action_prompts_user_id'))
    op.drop_table('next_action_prompts')

    with op.batch_alter_table('message_items', schema=None) as batch_op:
        batch_op.drop_index('ix_message_items_detected_intent')
        batch_op.drop_index('ix_message_items_needs_reply')
        batch_op.drop_index('ix_message_items_urgency')
        batch_op.drop_index('ix_message_items_user_received')
        batch_op.drop_index(batch_op.f('ix_message_items_user_id'))
    op.drop_table('message_items')
