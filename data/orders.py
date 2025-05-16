from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime, String
from sqlalchemy.orm import relationship
from .db_session import SqlAlchemyBase
from datetime import datetime


class Order(SqlAlchemyBase):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default='pending')
    created_date = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

    def __repr__(self):
        return f"<Order {self.id} - {self.status}>"

    def get_status_display(self):
        """Возвращает читаемый статус заказа"""
        statuses = {
            'pending': 'Ожидает обработки',
            'processing': 'В обработке',
            'shipped': 'Отправлен',
            'delivered': 'Доставлен',
            'cancelled': 'Отменен'
        }
        return statuses.get(self.status, self.status)


class OrderItem(SqlAlchemyBase):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer, nullable=False, default=1)
    price_at_purchase = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return f"<OrderItem {self.product_id} x{self.quantity}>"

    def get_total(self):
        """Возвращает общую стоимость элемента заказа"""
        return self.price_at_purchase * self.quantity