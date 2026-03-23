from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime as dt

app = Flask(__name__)
app.secret_key = 'happycreations_secret_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///happy_creations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

@app.context_processor
def inject_admin():
    return dict(is_admin=session.get('is_admin', False))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=dt.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    buy_price = db.Column(db.Float)
    rent_price = db.Column(db.Float)
    image_url = db.Column(db.String(300))
    available = db.Column(db.Boolean, default=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    user = db.relationship('User')
    product = db.relationship('Product')

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    mode = db.Column(db.String(10))
    days = db.Column(db.Integer, default=1)
    size = db.Column(db.String(20), default='Free Size')
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    mode = db.Column(db.String(10))
    days = db.Column(db.Integer, default=1)
    size = db.Column(db.String(20), default='Free Size')
    total_price = db.Column(db.Float)
    status = db.Column(db.String(50), default='pending')
    ordered_at = db.Column(db.DateTime, default=dt.utcnow)
    user = db.relationship('User')
    product = db.relationship('Product')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return render_template('auth.html', error="Email already registered. Please log in.")
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(name=name, email=email, password=hashed_pw, is_admin=False)
    db.session.add(new_user)
    db.session.commit()
    session['user_id'] = new_user.id
    session['user_name'] = new_user.name
    session['is_admin'] = False
    return redirect(url_for('welcome'))

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['is_admin'] = user.is_admin
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('welcome'))
    return render_template('auth.html', error="Invalid email or password.")

@app.route('/welcome')
def welcome():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('welcome.html', name=session['user_name'])

@app.route('/choose')
def choose():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('choose.html', now=dt.now())

@app.route('/products/<mode>')
def products(mode):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    if mode not in ['buy', 'rent']:
        return redirect(url_for('choose'))
    all_products = Product.query.order_by(Product.available.desc()).all()
    reviews = Review.query.all()
    return render_template('products.html', products=all_products, mode=mode, reviews=reviews)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    product_id = request.form.get('product_id')
    mode = request.form.get('mode')
    days = int(request.form.get('days', 1))
    size = request.form.get('size', 'Free Size')
    existing = CartItem.query.filter_by(
        user_id=session['user_id'], product_id=product_id, mode=mode, size=size
    ).first()
    if not existing:
        item = CartItem(user_id=session['user_id'], product_id=product_id,
                       mode=mode, days=days, size=size)
        db.session.add(item)
        db.session.commit()
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total = 0
    for item in items:
        if item.mode == 'buy':
            total += item.product.buy_price
        else:
            total += item.product.rent_price * item.days
    return render_template('cart.html', items=items, total=total)

@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    item = CartItem.query.get(item_id)
    if item and item.user_id == session.get('user_id'):
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('cart'))

@app.route('/payment')
def payment():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total = 0
    for item in items:
        if item.mode == 'buy':
            total += item.product.buy_price
        else:
            total += item.product.rent_price * item.days
    return render_template('payment.html', items=items, total=total)

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    items = CartItem.query.filter_by(user_id=session['user_id']).all()
    for item in items:
        price = item.product.buy_price if item.mode == 'buy' else item.product.rent_price * item.days
        order = Order(user_id=session['user_id'], product_id=item.product_id,
                     mode=item.mode, days=item.days, size=item.size,
                     total_price=price, status='confirmed')
        db.session.add(order)
        db.session.delete(item)
    db.session.commit()
    return render_template('order_success.html', name=session['user_name'])

@app.route('/add_review/<int:product_id>', methods=['POST'])
def add_review(product_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    rating = int(request.form.get('rating'))
    comment = request.form.get('comment')
    existing = Review.query.filter_by(
        user_id=session['user_id'], product_id=product_id
    ).first()
    if not existing:
        review = Review(
            user_id=session['user_id'],
            product_id=product_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
    return redirect(url_for('products', mode=request.form.get('mode', 'buy')))

@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.ordered_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    products = Product.query.all()
    orders = Order.query.order_by(Order.ordered_at.desc()).all()
    customers = User.query.filter_by(is_admin=False).all()
    total_revenue = sum(o.total_price for o in orders)
    return render_template('admin.html',
        products=products, orders=orders, customers=customers,
        total_revenue=total_revenue, total_orders=len(orders),
        total_customers=len(customers), total_products=len(products),
        name=session['user_name'])

@app.route('/switch_to_customer')
def switch_to_customer():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    session['viewing_as'] = 'customer'
    return redirect(url_for('choose'))

@app.route('/switch_to_admin')
def switch_to_admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    session['viewing_as'] = 'admin'
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_stock/<int:product_id>')
def toggle_stock(product_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    product = Product.query.get(product_id)
    if product:
        product.available = not product.available
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    new_product = Product(
        name=request.form.get('name'),
        category=request.form.get('category'),
        description=request.form.get('description'),
        buy_price=float(request.form.get('buy_price')),
        rent_price=float(request.form.get('rent_price')),
        image_url=request.form.get('image_url'),
        available=True
    )
    db.session.add(new_product)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_product/<int:product_id>')
def delete_product(product_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    product = Product.query.get(product_id)
    if product:
        CartItem.query.filter_by(product_id=product_id).delete()
        Review.query.filter_by(product_id=product_id).delete()
        db.session.delete(product)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_product/<int:product_id>', methods=['POST'])
def edit_product(product_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    product = Product.query.get(product_id)
    if product:
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.description = request.form.get('description')
        product.buy_price = float(request.form.get('buy_price'))
        product.rent_price = float(request.form.get('rent_price'))
        product.image_url = request.form.get('image_url')
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth'))
    order = Order.query.get(order_id)
    if order:
        order.status = request.form.get('status')
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

def setup_database():
    db.create_all()

    if not User.query.filter_by(email='hridayneema@gmail.com').first():
        hashed_pw = bcrypt.generate_password_hash('Hriday_1234').decode('utf-8')
        admin = User(name='Hriday Neema', email='hridayneema@gmail.com',
                    password=hashed_pw, is_admin=True)
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin 1 created!")

    if not User.query.filter_by(email='nehaneema18@gmail.com').first():
        hashed_pw = bcrypt.generate_password_hash('Neha_1234').decode('utf-8')
        admin2 = User(name='Neha Neema', email='nehaneema18@gmail.com',
                    password=hashed_pw, is_admin=True)
        db.session.add(admin2)
        db.session.commit()
        print("✅ Admin 2 created!")

    if not User.query.filter_by(email='pneema@gmail.com').first():
        hashed_pw = bcrypt.generate_password_hash('Pneema_1234').decode('utf-8')
        admin3 = User(name='P Neema', email='pneema@gmail.com',
                    password=hashed_pw, is_admin=True)
        db.session.add(admin3)
        db.session.commit()
        print("✅ Admin 3 created!")

    if Product.query.count() == 0:
        products = [

            # ── SAREES ──
            Product(name="Navratri Saree - Red & Gold", category="saree",
                    description="Beautiful traditional Gujarati saree perfect for Navratri",
                    buy_price=500, rent_price=100,
                    image_url="https://img.freepik.com/free-photo/indian-woman-wearing-traditional-saree_23-2149426422.jpg?w=400"),
            Product(name="Navratri Saree - Green & Silver", category="saree",
                    description="Elegant green saree with silver border for Navratri",
                    buy_price=600, rent_price=120,
                    image_url="https://img.freepik.com/free-photo/beautiful-indian-woman-traditional-green-saree_23-2149426418.jpg?w=400"),

            # ── KIDS ──
            Product(name="Kids Fairy Princess Costume", category="kids",
                    description="Magical fairy costume with wings for fancy dress",
                    buy_price=350, rent_price=80,
                    image_url="https://img.freepik.com/free-photo/cute-little-girl-princess-costume_23-2149408087.jpg?w=400"),
            Product(name="Kids Superhero Costume", category="kids",
                    description="Superhero costume for school fancy dress events",
                    buy_price=400, rent_price=90,
                    image_url="https://img.freepik.com/free-photo/little-boy-superhero-costume_23-2149408091.jpg?w=400"),
            Product(name="Kids Doctor Costume", category="kids",
                    description="Doctor costume with stethoscope for fancy dress",
                    buy_price=300, rent_price=70,
                    image_url="https://img.freepik.com/free-photo/little-girl-doctor-costume_23-2149408095.jpg?w=400"),

            # ── LEHENGAS ──
            Product(name="Rajasthani Lehenga - Pink", category="lehenga",
                    description="Traditional Rajasthani lehenga with heavy embroidery",
                    buy_price=1200, rent_price=200,
                    image_url="https://img.freepik.com/free-photo/beautiful-indian-woman-pink-lehenga_23-2149426415.jpg?w=400"),
            Product(name="Bridal Lehenga - Red", category="lehenga",
                    description="Stunning red bridal lehenga with golden embroidery work",
                    buy_price=2500, rent_price=400,
                    image_url="https://img.freepik.com/free-photo/indian-bride-red-lehenga_23-2149426419.jpg?w=400"),
            Product(name="Lehenga - Blue & Silver", category="lehenga",
                    description="Gorgeous blue lehenga with silver threadwork for functions",
                    buy_price=1800, rent_price=300,
                    image_url="https://img.freepik.com/free-photo/beautiful-woman-blue-lehenga_23-2149426420.jpg?w=400"),

            # ── MASKS ──
            Product(name="Butterfly Mask - Gold", category="mask",
                    description="Beautiful golden butterfly mask for parties and fancy dress",
                    buy_price=150, rent_price=30,
                    image_url="https://img.freepik.com/free-photo/golden-butterfly-mask-carnival_23-2148825095.jpg?w=400"),
            Product(name="Venetian Mask - Red & Black", category="mask",
                    description="Elegant venetian mask perfect for costume parties",
                    buy_price=200, rent_price=40,
                    image_url="https://img.freepik.com/free-photo/venetian-carnival-mask_23-2148825093.jpg?w=400"),
            Product(name="Superhero Mask - Black", category="mask",
                    description="Cool superhero mask for kids and adults fancy dress",
                    buy_price=120, rent_price=25,
                    image_url="https://img.freepik.com/free-photo/superhero-mask-black_23-2148825097.jpg?w=400"),

            # ── FANCY DRESSES ──
            Product(name="Princess Fancy Dress - Pink", category="fancydress",
                    description="Beautiful pink princess fancy dress with crown for kids",
                    buy_price=600, rent_price=120,
                    image_url="https://img.freepik.com/free-photo/little-girl-princess-pink-dress_23-2149408089.jpg?w=400"),
            Product(name="Pirate Fancy Dress", category="fancydress",
                    description="Complete pirate costume with hat and accessories",
                    buy_price=550, rent_price=110,
                    image_url="https://img.freepik.com/free-photo/boy-pirate-costume_23-2149408093.jpg?w=400"),
            Product(name="Witch Fancy Dress", category="fancydress",
                    description="Spooky witch costume with hat for Halloween and events",
                    buy_price=500, rent_price=100,
                    image_url="https://img.freepik.com/free-photo/witch-costume-halloween_23-2149408097.jpg?w=400"),

            # ── BRACELETS ──
            Product(name="Traditional Gold Bracelet", category="bracelet",
                    description="Beautiful traditional gold bracelet for ethnic occasions",
                    buy_price=300, rent_price=50,
                    image_url="https://img.freepik.com/free-photo/gold-bangles-indian-traditional_23-2148825099.jpg?w=400"),
            Product(name="Pearl Bracelet Set", category="bracelet",
                    description="Elegant pearl bracelet set for weddings and festivals",
                    buy_price=250, rent_price=40,
                    image_url="https://img.freepik.com/free-photo/pearl-bracelet-jewelry_23-2148825101.jpg?w=400"),
            Product(name="Kundan Bangles Set", category="bracelet",
                    description="Beautiful kundan bangles set for Navratri and festivals",
                    buy_price=350, rent_price=60,
                    image_url="https://img.freepik.com/free-photo/kundan-bangles-indian-jewelry_23-2148825103.jpg?w=400"),
        ]
        for p in products:
            db.session.add(p)
        db.session.commit()
        print("✅ All products added!")

with app.app_context():
    setup_database()

if __name__ == '__main__':
    app.run(debug=True)

    