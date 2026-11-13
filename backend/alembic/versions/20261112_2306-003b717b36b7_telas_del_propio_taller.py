"""telas del propio taller

Revision ID: 003b717b36b7
Revises: 3a17a80c22fb
Create Date: 2026-11-12 23:06:57.694402+00:00

Ep6-Hu7 y Ep6-Hu8: una tela puede ser del catálogo de la tienda (`owner_id`
vacío, como todas las que había) o de un usuario, que la fotografió en su
taller y solo ve él. Las telas existentes quedan en el catálogo sin tocarlas.

La clave ajena lleva nombre: autogenerate la dejaba sin él, y entonces el
`downgrade` no tiene cómo borrarla.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003b717b36b7'
down_revision: Union[str, Sequence[str], None] = '3a17a80c22fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK = 'fk_fabrics_owner_id_users'


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fabrics', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_fabrics_owner_id'), 'fabrics', ['owner_id'], unique=False)
    op.create_foreign_key(FK, 'fabrics', 'users', ['owner_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK, 'fabrics', type_='foreignkey')
    op.drop_index(op.f('ix_fabrics_owner_id'), table_name='fabrics')
    op.drop_column('fabrics', 'owner_id')
