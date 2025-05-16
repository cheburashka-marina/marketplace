from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from data.db_session import SqlAlchemyBase  # Или ваш базовый класс SQLAlchemy


class Review(SqlAlchemyBase):
    __tablename__ = 'reviews'

    id = Column(Integer, primary_key=True)
    text = Column(Text)
    rating = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    user_id = Column(Integer, ForeignKey('users.id'))
    product_id = Column(Integer, ForeignKey('products.id'))

    user = relationship("User")
    product = relationship("Product")