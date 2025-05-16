# Импорт необходимых модулей
from flask import Flask, render_template, redirect, request, session, url_for, flash
from sqlalchemy.orm import joinedload
from data import db_session
from data.promocode import PromoCode
from data.users import User
from data.products import Product
from data.orders import Order, OrderItem
from data.reviews import Review
from forms.user import RegisterForm, LoginForm
from forms.product import ProductForm
from datetime import datetime
from flask_session import Session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from logging.handlers import RotatingFileHandler
import os
from werkzeug.utils import secure_filename
from functools import wraps
import logging
from math import ceil

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Настройка логирования SQLAlchemy
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Инициализация Flask приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'

# Конфигурация приложения
app.config.update(
    # Настройки сессии
    SESSION_TYPE='filesystem',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_FILE_THRESHOLD=100,
    SESSION_FILE_DIR='../marketplace_/flask_session',

    # Настройки загрузки файлов
    UPLOAD_FOLDER='static/uploads',
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},

    # Настройки базы данных
    SQLALCHEMY_DATABASE_URI='sqlite:///db/marketplace.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_POOL_SIZE=10,
    SQLALCHEMY_MAX_OVERFLOW=20,
    SQLALCHEMY_POOL_TIMEOUT=30,
    SQLALCHEMY_POOL_RECYCLE=3600
)

# Инициализация расширений
Session(app)  # Для управления сессиями
login_manager = LoginManager()  # Для аутентификации пользователей
login_manager.init_app(app)
login_manager.login_view = 'login'

# Настройка логирования приложения
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)


def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def with_db_session(f):
    """Декоратор для автоматического управления сессиями базы данных"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        db_sess = db_session.create_session()
        try:
            result = f(db_sess, *args, **kwargs)
            db_sess.commit()
            return result
        except Exception as e:
            db_sess.rollback()
            raise e
        finally:
            db_sess.close()

    return wrapper


# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя по ID для системы аутентификации"""
    db_sess = db_session.create_session()
    return db_sess.query(User).get(int(user_id))


# ========================
# Роуты аутентификации
# ========================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя"""
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', form=form, message="Пароли не совпадают")

        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', form=form, message="Такой пользователь уже есть")

        user = User(
            name=form.name.data,
            email=form.email.data,
            address=form.address.data,
            phone=form.phone.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Аутентификация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        try:
            user = db_sess.query(User).filter(User.email == form.email.data).first()

            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Неверный email или пароль', 'danger')
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}", exc_info=True)
            flash("Произошла внутренняя ошибка сервера", "danger")
        finally:
            db_sess.close()

    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
def logout():
    """Выход пользователя из системы"""
    logout_user()
    return redirect(url_for('index'))


# ========================
# Роуты профиля
# ========================

@app.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя"""
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()
    orders = db_sess.query(Order).filter(Order.user_id == current_user.id).all()
    user_products = db_sess.query(Product).filter(Product.seller_id == current_user.id).all()
    db_sess.close()
    return render_template("profile.html", user=user, orders=orders, user_products=user_products)


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Обновление данных профиля"""
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.id).first()

    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('profile'))

    # Обновление основных данных
    user.name = request.form.get('name', user.name)
    user.address = request.form.get('address', user.address)
    user.phone = request.form.get('phone', user.phone)

    # Обработка аватарки
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename != '' and allowed_file(file.filename):
            # Удаление старого аватара
            if user.avatar:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], user.avatar))
                except Exception as e:
                    app.logger.error(f"Error deleting old avatar: {str(e)}")

            # Сохранение нового аватара
            filename = secure_filename(f"user_{user.id}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)
            user.avatar = filename

    try:
        db_sess.commit()
        flash('Профиль успешно обновлен', 'success')
    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error updating profile: {str(e)}")
        flash('Ошибка при обновлении профиля', 'danger')
    finally:
        db_sess.close()

    return redirect(url_for('profile'))


@app.route('/profile/stats')
@login_required
def profile_stats():
    """Статистика профиля пользователя"""
    db_sess = db_session.create_session()
    products_count = db_sess.query(Product).filter(Product.seller_id == current_user.id).count()
    total_views = 0  # Можно добавить счетчик просмотров в модель Product
    orders = db_sess.query(Order).filter(Order.user_id == current_user.id).all()
    total_spent = sum(order.total_amount for order in orders)
    return render_template("profile_stats.html",
                           products_count=products_count,
                           total_views=total_views,
                           total_spent=total_spent)


# ========================
# Роуты товаров
# ========================

@app.route("/")
def index():
    """Главная страница с товарами"""
    db_sess = db_session.create_session()
    products = db_sess.query(Product).limit(8).all()
    return render_template("index.html", products=products)


@app.route('/products')
def products_list():
    """Список всех товаров с пагинацией"""
    page = request.args.get('page', 1, type=int)
    per_page = 8
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    db_sess = db_session.create_session()
    query = db_sess.query(Product)

    # Фильтрация по поиску и категории
    if search:
        query = query.filter(Product.title.ilike(f'%{search}%'))
    if category:
        query = query.filter(Product.category == category)

    total_products = query.count()
    products = query.limit(per_page).offset((page - 1) * per_page).all()

    return render_template("products.html",
                           products=products,
                           page=page,
                           total_pages=ceil(total_products / per_page),
                           search=search,
                           category=category)


@app.route('/product/<int:id>')
def product_detail(id):
    """Страница деталей товара с отзывами"""
    db_sess = db_session.create_session()
    try:
        product = db_sess.query(Product) \
            .options(joinedload(Product.reviews).joinedload(Review.user)) \
            .filter(Product.id == id) \
            .first()

        if not product:
            flash('Товар не найден', 'danger')
            return redirect(url_for('index'))

        return render_template("product_detail.html", product=product)
    except Exception as e:
        app.logger.error(f"Error loading product: {str(e)}")
        flash('Ошибка при загрузке товара', 'danger')
        return redirect(url_for('index'))
    finally:
        db_sess.close()


@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    """Добавление нового товара"""
    form = ProductForm()

    if form.validate_on_submit():
        db_sess = db_session.create_session()
        try:
            # Обработка изображения товара
            image_url = None
            if 'image_file' in request.files:
                file = request.files['image_file']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(filepath)
                    image_url = f"/static/uploads/{unique_filename}"
                else:
                    flash('Недопустимый формат файла', 'danger')
                    return redirect(url_for('add_product'))

            # Создание товара
            product = Product(
                title=form.title.data,
                description=form.description.data,
                price=form.price.data,
                quantity=form.quantity.data,
                category=form.category.data,
                image_url=image_url,
                seller_id=current_user.id
            )

            db_sess.add(product)
            db_sess.commit()
            flash('Товар успешно добавлен!', 'success')
            return redirect(url_for('product_detail', id=product.id))

        except Exception as e:
            db_sess.rollback()
            app.logger.error(f"Error adding product: {str(e)}", exc_info=True)
            flash(f'Ошибка при добавлении товара: {str(e)}', 'danger')
        finally:
            db_sess.close()
    else:
        # Отображение ошибок валидации
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Ошибка в поле {getattr(form, field).label.text}: {error}", 'danger')

    return render_template('add_product.html', form=form)


@app.route('/product/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    """Редактирование существующего товара"""
    db_sess = db_session.create_session()
    try:
        product = db_sess.query(Product).filter(
            Product.id == id,
            Product.seller_id == current_user.id
        ).first()

        if not product:
            flash('Товар не найден или нет прав на редактирование', 'danger')
            return redirect(url_for('profile'))

        form = ProductForm(obj=product)

        if form.validate_on_submit():
            # Обработка сброса промокода
            if 'reset_promo' in request.form:
                product.promo_code = None
                product.discount_percent = 0
                product.is_discount_active = False
                db_sess.commit()
                flash('Промокод сброшен', 'success')
                return redirect(url_for('edit_product', id=id))

            # Обновление данных товара
            form.populate_obj(product)

            # Обработка промокода
            if form.promo_code.data:
                promo = db_sess.query(PromoCode).filter(
                    PromoCode.code == form.promo_code.data
                ).first()

                if not promo:
                    promo = PromoCode(
                        code=form.promo_code.data,
                        discount=form.discount_percent.data,
                        is_active=form.is_discount_active.data
                    )
                    db_sess.add(promo)

                product.promo_code = promo.code
                product.discount_percent = promo.discount
                product.is_discount_active = promo.is_active
            else:
                product.promo_code = None
                product.discount_percent = 0
                product.is_discount_active = False

            # Обработка изображения
            if 'image_file' in request.files:
                file = request.files['image_file']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Удаление старого изображения
                    if product.image_url and product.image_url.startswith('/static/uploads/'):
                        try:
                            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product.image_url.split('/')[-1]))
                        except Exception as e:
                            app.logger.error(f"Error deleting old image: {str(e)}")

                    # Сохранение нового изображения
                    filename = secure_filename(file.filename)
                    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(filepath)
                    product.image_url = f"/static/uploads/{unique_filename}"

            db_sess.commit()
            flash('Товар успешно обновлен', 'success')
            return redirect(url_for('product_detail', id=id))

        return render_template('edit_product.html', form=form, product=product)
    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error editing product: {str(e)}")
        flash('Ошибка при обновлении товара', 'danger')
        return redirect(url_for('profile'))
    finally:
        db_sess.close()


@app.route('/product/delete/<int:id>', methods=['POST'])
@login_required
def delete_product(id):
    """Удаление товара"""
    db_sess = db_session.create_session()
    product = db_sess.query(Product).filter(Product.id == id, Product.seller_id == current_user.id).first()

    if product:
        # Удаление изображения товара
        if product.image_url and product.image_url.startswith('/static/uploads/'):
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], product.image_url.split('/')[-1]))
            except Exception as e:
                app.logger.error(f"Error deleting image: {str(e)}")

        db_sess.delete(product)
        db_sess.commit()
        flash('Товар успешно удален', 'success')
    else:
        flash('Товар не найден или у вас нет прав на его удаление', 'danger')

    db_sess.close()
    return redirect(url_for('profile'))


# ========================
# Роуты корзины
# ========================

@app.route('/add_to_cart/<int:product_id>', methods=['GET', 'POST'])
def add_to_cart(product_id):
    """Добавление товара в корзину"""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    if 'cart' not in session:
        session['cart'] = []

    if request.method == 'POST':
        # Добавление с указанием количества
        quantity = int(request.form.get('quantity', 1))
        session['cart'].extend([product_id] * quantity)
        flash(f'Товар добавлен в корзину (x{quantity})', 'success')
    else:
        # Простое добавление одного товара
        session['cart'].append(product_id)
        flash('Товар добавлен в корзину', 'success')

    session.modified = True
    return redirect(request.referrer or url_for('index'))


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    """Удаление товара из корзины"""
    if 'cart' in session and product_id in session['cart']:
        session['cart'].remove(product_id)
        session.modified = True
        flash('Товар удален из корзины', 'info')
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    """Просмотр корзины"""
    if 'cart' not in session:
        return render_template("cart.html", products=[], total=0, total_before_discount=0, total_discount=0)

    db_sess = db_session.create_session()
    product_ids = session['cart']
    products = db_sess.query(Product).filter(Product.id.in_(product_ids)).all()

    # Подсчет количества каждого товара
    from collections import Counter
    counter = Counter(product_ids)
    quantities = {product.id: counter[product.id] for product in products}

    # Расчет сумм
    total_before_discount = sum(product.price * quantities[product.id] for product in products)
    total_discount = 0
    total = total_before_discount

    # Применение скидок
    for product in products:
        if product.is_discount_active and product.discount_percent > 0:
            discount = product.price * product.discount_percent / 100 * quantities[product.id]
            total_discount += discount
            total -= discount

    return render_template("cart.html",
                         products=products,
                         quantities=quantities,
                         total=total,
                         total_before_discount=total_before_discount,
                         total_discount=total_discount)


@app.route('/checkout')
def checkout():
    """Оформление заказа"""
    if 'user_id' not in session:
        return redirect('/login')

    db_sess = db_session.create_session()
    product_ids = session.get('cart', [])
    products = db_sess.query(Product).filter(Product.id.in_(product_ids)).all()

    if not products:
        return redirect('/cart')

    # Подсчет количества товаров
    from collections import Counter
    counter = Counter(product_ids)
    quantities = {product.id: counter[product.id] for product in products}

    total = sum(product.price * quantities[product.id] for product in products)

    # Создание заказа
    order = Order(
        user_id=session['user_id'],
        total_amount=total,
        status='pending'
    )
    db_sess.add(order)
    db_sess.commit()

    # Добавление товаров в заказ
    for product in products:
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantities[product.id],
            price_at_purchase=product.price
        )
        db_sess.add(order_item)

    db_sess.commit()
    session['cart'] = []  # Очистка корзины
    return redirect('/profile')


# ========================
# Роуты отзывов
# ========================

@app.route('/product/<int:id>/review', methods=['POST'])
@login_required
def add_review(id):
    """Добавление отзыва к товару"""
    text = request.form.get('text')
    rating = request.form.get('rating')

    # Валидация данных
    if not text or not rating:
        flash('Заполните все поля', 'danger')
        return redirect(url_for('product_detail', id=id))

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        flash('Оценка должна быть числом от 1 до 5', 'danger')
        return redirect(url_for('product_detail', id=id))

    db_sess = db_session.create_session()
    try:
        # Проверка на существующий отзыв
        existing_review = db_sess.query(Review).filter(
            Review.user_id == current_user.id,
            Review.product_id == id
        ).first()

        if existing_review:
            flash('Вы уже оставляли отзыв на этот товар', 'warning')
            return redirect(url_for('product_detail', id=id))

        # Создание нового отзыва
        review = Review(
            text=text,
            rating=rating,
            user_id=current_user.id,
            product_id=id
        )
        db_sess.add(review)
        db_sess.commit()
        flash('Отзыв успешно добавлен', 'success')
    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error adding review: {str(e)}")
        flash('Ошибка при добавлении отзыва', 'danger')
    finally:
        db_sess.close()

    return redirect(url_for('product_detail', id=id))


@app.route('/review/delete/<int:id>', methods=['POST'])
@login_required
def delete_review(id):
    """Удаление отзыва"""
    db_sess = db_session.create_session()
    review = db_sess.query(Review).filter(
        Review.id == id,
        Review.user_id == current_user.id
    ).first()

    if review:
        db_sess.delete(review)
        db_sess.commit()
        flash('Отзыв удален', 'success')
    else:
        flash('Отзыв не найден или нет прав на удаление', 'danger')

    return redirect(url_for('product_detail', id=review.product_id))


# ========================
# Роуты избранного
# ========================

@app.route('/favorites')
@login_required
def favorites():
    db_sess = db_session.create_session()
    favorite_products = current_user.favorite_products
    return render_template("favorites.html", products=favorite_products)


@app.route('/favorites/add/<int:product_id>')
@login_required
def add_favorite(product_id):
    db_sess = db_session.create_session()
    try:
        # Получаем текущего пользователя в текущей сессии
        user = db_sess.merge(current_user)
        product = db_sess.get(Product, product_id)

        if not product:
            flash('Товар не найден', 'danger')
            return redirect(request.referrer or url_for('index'))

        if product not in user.favorite_products:
            user.favorite_products.append(product)
            db_sess.commit()
            flash('Товар добавлен в избранное', 'success')
        else:
            flash('Товар уже в избранном', 'info')

    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error adding favorite: {e}")
        flash('Ошибка при добавлении в избранное', 'danger')
    finally:
        db_sess.close()

    return redirect(request.referrer or url_for('index'))


@app.route('/favorites/remove/<int:product_id>')
@login_required
def remove_favorite(product_id):
    db_sess = db_session.create_session()
    try:
        # Получаем текущего пользователя в текущей сессии
        user = db_sess.merge(current_user)
        product = db_sess.get(Product, product_id)

        if not product:
            flash('Товар не найден', 'danger')
            return redirect(request.referrer or url_for('index'))

        if product in user.favorite_products:
            user.favorite_products.remove(product)
            db_sess.commit()
            flash('Товар удален из избранного', 'success')
        else:
            flash('Товара нет в избранном', 'info')

    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error removing favorite: {e}")
        flash('Ошибка при удалении из избранного', 'danger')
    finally:
        db_sess.close()

    return redirect(request.referrer or url_for('index'))


# ========================
# Роуты промокодов
# ========================

@app.route('/promo/create', methods=['POST'])
@login_required
def create_promo():
    code = request.form.get('code')
    discount = request.form.get('discount')

    if not code or not discount:
        flash('Заполните все поля', 'danger')
        return redirect(url_for('profile'))

    try:
        discount = int(discount)
        if discount < 1 or discount > 99:
            raise ValueError
    except ValueError:
        flash('Скидка должна быть числом от 1 до 99', 'danger')
        return redirect(url_for('profile'))

    db_sess = db_session.create_session()
    try:
        # Проверяем, существует ли уже такой промокод
        if db_sess.query(PromoCode).filter(PromoCode.code == code).first():
            flash('Такой промокод уже существует', 'danger')
            return redirect(url_for('profile'))

        promo = PromoCode(
            code=code,
            discount=discount,
            is_active=True
        )
        db_sess.add(promo)
        db_sess.commit()
        flash('Промокод успешно создан!', 'success')
    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error creating promo: {str(e)}")
        flash('Ошибка при создании промокода', 'danger')
    finally:
        db_sess.close()

    return redirect(url_for('profile'))


@app.route('/apply_promo', methods=['POST'])
def apply_promo():
    if 'cart' not in session or not session['cart']:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('cart'))

    promo_code = request.form.get('promo_code')
    if not promo_code:
        flash('Введите промокод', 'warning')
        return redirect(url_for('cart'))

    db_sess = db_session.create_session()
    try:
        promo = db_sess.query(PromoCode).filter(
            PromoCode.code == promo_code,
            PromoCode.is_active == True
        ).first()

        if not promo:
            flash('Неверный или неактивный промокод', 'danger')
            return redirect(url_for('cart'))

        # Применяем промокод к товарам в корзине
        product_ids = session['cart']
        products = db_sess.query(Product).filter(Product.id.in_(product_ids)).all()

        for product in products:
            if not product.promo_code:  # Если у товара нет своего промокода
                product.promo_code = promo.code
                product.discount_percent = promo.discount
                product.is_discount_active = True

        db_sess.commit()
        flash(f'Промокод "{promo.code}" успешно применен! Скидка {promo.discount}%', 'success')
    except Exception as e:
        db_sess.rollback()
        app.logger.error(f"Error applying promo: {str(e)}")
        flash('Ошибка при применении промокода', 'danger')
    finally:
        db_sess.close()

    return redirect(url_for('cart'))


# ========================
# Вспомогательные роуты
# ========================

@app.route('/session_test')
def session_test():
    """Тестовый роут для проверки работы сессий"""
    session['test'] = 'Это тестовое значение сессии'
    return f"Значение сессии: {session.get('test')}"


from sqlalchemy import text  # Добавьте этот импорт


def main():
    db_session.global_init("db/marketplace.db")

    # Проверка соединения с БД
    db_sess = db_session.create_session()
    try:
        # Используем text() для явного указания SQL-выражения
        db_sess.execute(text("SELECT 1"))
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error: {e}")
        return
    finally:
        db_sess.close()

    app.run()


if __name__ == '__main__':
    main()
