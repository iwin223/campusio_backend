"""Add complete hostel module

Revision ID: c1d2e3f4a5b6
Revises: add_online_payments_001
Create Date: 2026-04-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'add_online_payments_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Hostel module tables already created in initial migration - this is a pass-through migration"""
    pass


def downgrade() -> None:
    """No-op downgrade for pass-through migration"""
    pass
