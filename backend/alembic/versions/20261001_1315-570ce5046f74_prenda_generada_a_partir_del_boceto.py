"""prenda generada a partir del boceto

Un boceto deja de vestirse como dibujo. La IA lo convierte en la fotografía de
la prenda y las telas se prueban sobre esa fotografía:

- `status`: solo `ready` se puede probar. Un boceto pasa por `pending` y
  `processing` mientras se genera su prenda.
- `sketch_key`: el dibujo original. `image_key` pasa a ser la prenda generada.
- `error_message`, `similarity`, `provider`, `tokens_used`: lo que deja la
  generación. `similarity` es el parecido de silueta con el dibujo.

LOS BOCETOS QUE YA ESTABAN SUBIDOS
----------------------------------
Tienen el dibujo en `image_key` y ninguna prenda. Se marcan `failed` con un
mensaje que dice qué hacer, y el dibujo se copia a `sketch_key` para poder
generarla. NO se generan aquí: cuesta dinero, y eso lo decide una persona.
Sus pruebas de tela antiguas —la tela pintada sobre el dibujo— no se tocan.

Revision ID: 570ce5046f74
Revises: 32d71eca2214
Create Date: 2026-10-01 13:15:56.334542+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '570ce5046f74'
down_revision: Union[str, Sequence[str], None] = '32d71eca2214'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SIN_PRENDA = (
    "Este boceto se subió cuando la tela se pintaba sobre el dibujo. Ahora la IA "
    "genera primero la prenda: pulsa «Generar la prenda»."
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('garment_uploads', sa.Column('status', sa.Enum('ready', 'pending', 'processing', 'failed', name='garmentstatus', native_enum=False, length=32), server_default='ready', nullable=False))
    op.add_column('garment_uploads', sa.Column('sketch_key', sa.String(length=512), nullable=True))
    op.add_column('garment_uploads', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('garment_uploads', sa.Column('similarity', sa.Float(), nullable=True))
    op.add_column('garment_uploads', sa.Column('provider', sa.String(length=64), nullable=True))
    op.add_column('garment_uploads', sa.Column('tokens_used', sa.Integer(), nullable=True))

    prendas = sa.table(
        'garment_uploads',
        sa.column('kind', sa.String),
        sa.column('status', sa.String),
        sa.column('image_key', sa.String),
        sa.column('sketch_key', sa.String),
        sa.column('error_message', sa.Text),
    )
    op.execute(
        prendas.update()
        .where(prendas.c.kind == 'sketch')
        .values(status='failed', sketch_key=prendas.c.image_key, error_message=SIN_PRENDA)
    )


def downgrade() -> None:
    """Downgrade schema.

    Las prendas ya generadas se quedan en `image_key`: el dibujo de esos
    bocetos deja de estar referenciado, aunque su archivo sigue en el almacén.
    """
    op.drop_column('garment_uploads', 'tokens_used')
    op.drop_column('garment_uploads', 'provider')
    op.drop_column('garment_uploads', 'similarity')
    op.drop_column('garment_uploads', 'error_message')
    op.drop_column('garment_uploads', 'sketch_key')
    op.drop_column('garment_uploads', 'status')
