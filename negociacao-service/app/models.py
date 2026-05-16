from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, MetaData, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Schema é configurável via env, mas as tabelas usam o nome canônico do projeto.
METADATA = MetaData(schema="portal_b2b")


class Base(DeclarativeBase):
    metadata = METADATA


class ProcessoNegociacao(Base):
    __tablename__ = "processo_negociacao"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    produto_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    modo: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ABERTO")
    data_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valor_reserva: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    lances: Mapped[list["Lance"]] = relationship(
        back_populates="processo",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Lance(Base):
    __tablename__ = "lance"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    processo_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("portal_b2b.processo_negociacao.id"),
        nullable=False,
    )
    empresa_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    data_lance: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    processo: Mapped[ProcessoNegociacao] = relationship(back_populates="lances")
