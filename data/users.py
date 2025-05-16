import datetime
import sqlalchemy
from sqlalchemy import orm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .db_session import SqlAlchemyBase
from .associations import favorites_table


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    email = sqlalchemy.Column(sqlalchemy.String, index=True, unique=True, nullable=True)
    hashed_password = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    created_date = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)
    address = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    phone = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    is_active = sqlalchemy.Column(sqlalchemy.Boolean, default=True)
    avatar = sqlalchemy.Column(sqlalchemy.String)

    # Связи
    products = orm.relationship("Product", back_populates="seller")
    orders = orm.relationship("Order", back_populates="user")
    reviews = orm.relationship("Review", back_populates="user", cascade="all, delete-orphan")

    favorite_products = orm.relationship(
        "Product",
        secondary=favorites_table,
        back_populates="favorited_by"
    )

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False