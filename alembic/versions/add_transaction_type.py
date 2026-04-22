"""Add transaction_type to online_transactions

Revision ID: add_transaction_type
Revises: d2a727cf043d
Create Date: 2026-04-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_transaction_type'
down_revision: Union[str, None] = 'd2a727cf043d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the ENUM type first
    op.execute("CREATE TYPE transactiontype AS ENUM ('FEE', 'SUBSCRIPTION')")
    
    # Add transaction_type column to online_transactions table
    op.add_column(
        'online_transactions',
        sa.Column('transaction_type', sa.Enum('FEE', 'SUBSCRIPTION', name='transactiontype'), nullable=False, server_default='FEE')
    )
    
    # Add index for transaction_type
    op.create_index(
        'ix_online_transactions_transaction_type',
        'online_transactions',
        ['transaction_type'],
        unique=False
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_online_transactions_transaction_type', table_name='online_transactions')
    
    # Drop column
    op.drop_column('online_transactions', 'transaction_type')
    
    # Drop the ENUM type
    op.execute("DROP TYPE transactiontype")
