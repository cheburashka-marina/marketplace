import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .db_session import SqlAlchemyBase
from .associations import favorites_table

class Product(SqlAlchemyBase):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    category = Column(String)
    created_date = Column(DateTime, default=datetime.datetime.now)
    image_url = Column(String)
    promo_code = Column(String(50), ForeignKey('promo_codes.code'), nullable=True)
    discount_percent = Column(Integer, default=0)
    is_discount_active = Column(Boolean, default=False)

    seller_id = Column(Integer, ForeignKey("users.id"))

    # Связи
    seller = relationship("User", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    promo = relationship("PromoCode")

    favorited_by = relationship(
        "User",
        secondary=favorites_table,
        back_populates="favorite_products"
    )