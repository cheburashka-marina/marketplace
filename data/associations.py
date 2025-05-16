from sqlalchemy import Table, Column, Integer, ForeignKey
from .db_session import SqlAlchemyBase

favorites_table = Table(
    'favorites',
    SqlAlchemyBase.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('product_id', Integer, ForeignKey('products.id'), primary_key=True),
    extend_existing=True
)