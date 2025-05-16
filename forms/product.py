from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, FloatField, SelectField, IntegerField
from wtforms.validators import DataRequired, NumberRange
from wtforms import BooleanField

class ProductForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание', validators=[DataRequired()])
    price = FloatField('Цена', validators=[DataRequired(), NumberRange(min=0.01)])
    quantity = IntegerField('Количество', validators=[DataRequired(), NumberRange(min=1)], default=1)
    category = SelectField('Категория', choices=[
        ('electronics', 'Электроника'),
        ('clothing', 'Одежда'),
        ('books', 'Книги'),
        ('home', 'Дом и сад'),
        ('other', 'Другое')
    ], validators=[DataRequired()])
    image_url = StringField('URL изображения')
    submit = SubmitField('Добавить товар')
    promo_code = StringField('Промокод (если есть)')
    discount_percent = IntegerField('Скидка (%)', validators=[NumberRange(min=0, max=99)])
    is_discount_active = BooleanField('Активировать скидку')
    reset_promo = SubmitField('Сбросить промокод')
