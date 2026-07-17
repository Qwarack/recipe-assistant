"""add automatic meal planning

Revision ID: 5e62a1b90d4f
Revises: 0fc2516c6936
Create Date: 2026-07-17 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e62a1b90d4f"
down_revision: str | Sequence[str] | None = "0fc2516c6936"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("recipes") as batch_op:
        batch_op.add_column(
            sa.Column("tags", sa.JSON(), server_default="[]", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "meal_types",
                sa.JSON(),
                server_default='["dinner"]',
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("preparation_time_minutes", sa.Integer()))
        batch_op.add_column(
            sa.Column(
                "difficulty",
                sa.String(length=50),
                server_default="unknown",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_servings",
                sa.Integer(),
                server_default="2",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("vegetarian", sa.Boolean()))
        batch_op.add_column(sa.Column("vegan", sa.Boolean()))
        batch_op.add_column(sa.Column("last_planned_at", sa.DateTime(timezone=True)))
        batch_op.add_column(
            sa.Column(
                "suitable_for_leftovers",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("leftover_servings", sa.Integer()))
        batch_op.add_column(
            sa.Column(
                "leftover_days",
                sa.Integer(),
                server_default="1",
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_recipes_preparation_time_minutes",
            ["preparation_time_minutes"],
        )
        batch_op.create_index("ix_recipes_difficulty", ["difficulty"])
        batch_op.create_index("ix_recipes_vegetarian", ["vegetarian"])
        batch_op.create_index("ix_recipes_vegan", ["vegan"])
        batch_op.create_index("ix_recipes_last_planned_at", ["last_planned_at"])

    with op.batch_alter_table("meal_plans") as batch_op:
        batch_op.drop_constraint("uq_meal_plans_start_date", type_="unique")
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="active",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("generation_seed", sa.Integer()))
        batch_op.add_column(sa.Column("generated_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("generation_config", sa.JSON()))
        batch_op.add_column(sa.Column("created_by", sa.String(length=64)))
        batch_op.add_column(sa.Column("activated_by", sa.String(length=64)))
        batch_op.add_column(sa.Column("generation_source", sa.String(length=50)))
        batch_op.create_index("ix_meal_plans_status", ["status"])

    op.create_index(
        "uq_active_meal_plan_start_date",
        "meal_plans",
        ["start_date"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )

    with op.batch_alter_table("meal_plan_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=20),
                server_default="manual",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("source_entry_id", sa.Integer()))
        batch_op.create_foreign_key(
            "fk_meal_plan_entries_source_entry_id",
            "meal_plan_entries",
            ["source_entry_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_meal_plan_entries_source", ["source"])


def downgrade() -> None:
    with op.batch_alter_table("meal_plan_entries") as batch_op:
        batch_op.drop_index("ix_meal_plan_entries_source")
        batch_op.drop_constraint(
            "fk_meal_plan_entries_source_entry_id",
            type_="foreignkey",
        )
        batch_op.drop_column("source_entry_id")
        batch_op.drop_column("source")

    op.drop_index("uq_active_meal_plan_start_date", table_name="meal_plans")
    with op.batch_alter_table("meal_plans") as batch_op:
        batch_op.drop_index("ix_meal_plans_status")
        batch_op.drop_column("generation_source")
        batch_op.drop_column("activated_by")
        batch_op.drop_column("created_by")
        batch_op.drop_column("generation_config")
        batch_op.drop_column("generated_at")
        batch_op.drop_column("generation_seed")
        batch_op.drop_column("status")
        batch_op.create_unique_constraint("uq_meal_plans_start_date", ["start_date"])

    with op.batch_alter_table("recipes") as batch_op:
        batch_op.drop_index("ix_recipes_last_planned_at")
        batch_op.drop_index("ix_recipes_vegan")
        batch_op.drop_index("ix_recipes_vegetarian")
        batch_op.drop_index("ix_recipes_difficulty")
        batch_op.drop_index("ix_recipes_preparation_time_minutes")
        batch_op.drop_column("leftover_days")
        batch_op.drop_column("leftover_servings")
        batch_op.drop_column("suitable_for_leftovers")
        batch_op.drop_column("last_planned_at")
        batch_op.drop_column("vegan")
        batch_op.drop_column("vegetarian")
        batch_op.drop_column("default_servings")
        batch_op.drop_column("difficulty")
        batch_op.drop_column("preparation_time_minutes")
        batch_op.drop_column("meal_types")
        batch_op.drop_column("tags")
