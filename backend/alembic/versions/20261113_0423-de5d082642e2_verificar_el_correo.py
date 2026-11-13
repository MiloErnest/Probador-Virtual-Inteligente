"""verificar el correo

Revision ID: de5d082642e2
Revises: 003b717b36b7
Create Date: 2026-11-13 04:23 UTC (12/11/2026 en Colombia)

Ep5-Hu7: `users.email_verified_at`. Vacío = correo sin verificar, y sin poder
generar prendas con IA.

LAS CUENTAS QUE YA EXISTÍAN QUEDAN VERIFICADAS. Se crearon cuando la regla no
existía, y dejarlas sin verificar bloquearía de golpe los bocetos de quien ya
los usaba, sin un correo con el que desbloquearlos si no hay SMTP configurado.
Se marcan con la fecha de la migración, que dice cuándo se decidió, no cuándo
se comprobó el buzón.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de5d082642e2'
down_revision: Union[str, Sequence[str], None] = '003b717b36b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'email_verified_at')
