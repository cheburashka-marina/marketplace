from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship as orm_relationship
from data.db_session import SqlAlchemyBase


class PromoCode(SqlAlchemyBase):
    __tablename__ = 'promo_codes'

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True)
    discount = Column(Integer)  # процент скидки
    is_active = Column(Boolean, default=True)

    # Поле для родительского промокода
    parent_id = Column(Integer, ForeignKey('promo_codes.id'))

    # Связь для дочерних промокодов
    children = orm_relationship("PromoCode", back_populates="parent")

    # Связь для родительского промокода
    parent = orm_relationship("PromoCode", remote_side=[id], back_populates="children")