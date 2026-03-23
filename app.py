from flask import Flask, render_template, request, redirect, url_for, session, jsonify
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
    image_url = db.Column(db.String(500))
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

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    product = db.relationship('Product')
    user = db.relationship('User')

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
    search = request.args.get('search', '')
    if search:
        all_products = Product.query.filter(
            Product.name.ilike(f'%{search}%') |
            Product.category.ilike(f'%{search}%') |
            Product.description.ilike(f'%{search}%')
        ).order_by(Product.available.desc()).all()
    else:
        all_products = Product.query.order_by(Product.available.desc()).all()
    reviews = Review.query.all()
    wishlist_ids = [w.product_id for w in Wishlist.query.filter_by(user_id=session['user_id']).all()]
    return render_template('products.html', products=all_products, mode=mode,
                         reviews=reviews, wishlist_ids=wishlist_ids, search=search)

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
        review = Review(user_id=session['user_id'], product_id=product_id,
                       rating=rating, comment=comment)
        db.session.add(review)
        db.session.commit()
    return redirect(url_for('products', mode=request.form.get('mode', 'buy')))

@app.route('/toggle_wishlist/<int:product_id>')
def toggle_wishlist(product_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    mode = request.args.get('mode', 'buy')
    existing = Wishlist.query.filter_by(
        user_id=session['user_id'], product_id=product_id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
    else:
        wishlist = Wishlist(user_id=session['user_id'], product_id=product_id)
        db.session.add(wishlist)
        db.session.commit()
    return redirect(url_for('products', mode=mode))

@app.route('/wishlist')
def wishlist():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    items = Wishlist.query.filter_by(user_id=session['user_id']).all()
    return render_template('wishlist.html', items=items)

@app.route('/remove_wishlist/<int:item_id>')
def remove_wishlist(item_id):
    item = Wishlist.query.get(item_id)
    if item and item.user_id == session.get('user_id'):
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('wishlist'))

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
        Wishlist.query.filter_by(product_id=product_id).delete()
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
            Product(name="Navratri Saree - Red & Gold",
                    category="saree",
                    description="A stunning red and gold saree crafted specially for the Navratri festival. Made from premium quality fabric with rich golden border and intricate embroidery work. Perfect for Garba and Dandiya nights — you will shine in the crowd wearing this beautiful traditional piece.",
                    buy_price=500, rent_price=100,
                    image_url="https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcTu3lD26ADLWvUaYuPW2v5yMAiWSGV5arxFW-ZswQxKhQhv6TwTg4UkOAfABv9CK6SRr5CeBIc795gG9E5a4ebPuD5la1PNLcdV5dK7Tzmi6XYB310KGo6fNg"),

            Product(name="Navratri Saree - Green & Silver",
                    category="saree",
                    description="An elegant green saree with a beautiful silver border — perfect for Navratri celebrations. The soft fabric drapes gracefully and the silver threadwork adds a royal touch to your look. Ideal for women who love to blend tradition with elegance during festive occasions.",
                    buy_price=600, rent_price=120,
                    image_url="https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcTYKjEPVcz52JY-jar9xyed8Eo48qdqQFz8Opgu2jj2UK3mfITSNAVkhkKNqTBjMm_nwZ5O5VUlL8z5eCfB92t7hTLseWms0B9JPDi7V39F5hSbMu_5-vMc"),

            # ── KIDS ──
            Product(name="Kids Fairy Princess Costume",
                    category="kids",
                    description="A magical fairy princess costume that will make your little one the star of any fancy dress competition. Complete with beautiful wings, a sparkly crown and a flowing pink dress that every little girl dreams of. Made from soft comfortable fabric — perfect for school events, birthday parties and fancy dress shows.",
                    buy_price=350, rent_price=80,
                    image_url="https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcQIzFdam0V0LU6wiJJS3_cVERAsUDmGHj03QKdFzbmMqabKQ3AlKZzNFTUsEEglNiZjGmpRhvvSrikyFLCnpJv-s-sYzTQPBuf6NqLsrA9tSU24OID__JEioQ"),

            Product(name="Kids Superhero Costume",
                    category="kids",
                    description="Let your child unleash their inner superhero with this amazing costume perfect for fancy dress events. Complete with a cape, mask and superhero suit — your child will feel powerful and confident. Made from durable and comfortable material that allows free movement during performances.",
                    buy_price=400, rent_price=90,
                    image_url="https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcSDSDep7AX6Y09CXv5urbL0ZQXij-wXodNMm6IakASUpgazzdbFLeucppG0vrYnwscBW6gewb5mbj1m5PhX8gklE1OAhxiCPQ"),

            Product(name="Kids Doctor Costume",
                    category="kids",
                    description="A complete doctor costume for your little one to shine at school fancy dress competitions. Comes with a white doctor coat, stethoscope, and doctor accessories that look very realistic. Perfect for teaching kids about professions while making them look absolutely adorable and confident.",
                    buy_price=300, rent_price=70,
                    image_url="https://encrypted-tbn1.gstatic.com/shopping?q=tbn:ANd9GcQw6yoqNDux-41Xsf10qWHV8pb5_512IXm6U9QTv7sPl8hopcTkrbddLsobB1cBTrzKAqM3Hd-DX8lX91zvC_iKVIsrJ2BBHiufzGf3_q9hT4AeZeXWqr4alQ"),

            # ── LEHENGAS ──
            Product(name="Rajasthani Lehenga - Pink",
                    category="lehenga",
                    description="A breathtaking pink Rajasthani lehenga with heavy traditional embroidery and mirror work that reflects the rich culture of Rajasthan. The vibrant pink colour and detailed craftsmanship make it perfect for festivals, weddings and cultural events. Every stitch tells a story of tradition and elegance.",
                    buy_price=1200, rent_price=200,
                    image_url="https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcRwIvBixc5gBj5ErWhDFCtk5cVL1_D74do-dLGXM8yOqo30ohCU-LkbQD7KEzq0kDTDG_ys5jRjVBej1e800WiVcio8D4DVVuITWqYDS1U"),

            Product(name="Bridal Lehenga - Red",
                    category="lehenga",
                    description="A stunning red bridal lehenga adorned with heavy golden embroidery and intricate zari work — fit for a queen. This magnificent piece is crafted with premium fabric and detailed handwork that makes every bride look absolutely radiant on her special day. The rich red colour symbolises love, prosperity and new beginnings.",
                    buy_price=2500, rent_price=400,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcTm3xneht0e2xU4AR5tRskZo41GkeGU-kPKg_t8aBdO4CpjVDfT3Do705tcZzdG-RDnEyf-fByaXcMMsl-C6Xw3HBfbnzspMPDpQuzXXzrM5-YHoU7x6_CpGg"),

            Product(name="Lehenga - Blue & Silver",
                    category="lehenga",
                    description="A gorgeous blue lehenga with delicate silver threadwork and sequin embellishments that catch the light beautifully. The royal blue colour paired with silver gives a sophisticated and elegant look perfect for weddings, sangeet ceremonies and festive functions. Light and comfortable to wear for long hours of celebration.",
                    buy_price=1800, rent_price=300,
                    image_url="https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcRElkvw6arxSQnIpIlI4bqpf2GVQj-8kjd8FcY0PrDTMz66bDsZBHCuEZjy2FuAZr0zrflufAA2bhfXjNEsAjZa5eJXCaAfQqaiO0BEpnWSMyKX4B8LBDTHOA"),

            # ── MASKS ──
            Product(name="Butterfly Mask - Gold",
                    category="mask",
                    description="A beautiful golden butterfly mask crafted with glitter and fine detailing — perfect for masquerade parties, fancy dress events and themed celebrations. The lightweight design ensures comfort while the stunning golden finish makes you stand out in any crowd. One size fits most adults and children.",
                    buy_price=150, rent_price=30,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcRcJnAzlOkkcl-PgZX-104Oan70afgNIEFHr_W44ADvgWYnkLBd6j-wMamvgigT2KqMNAEfSPWD4IljSvPM1tkAu6D5IjS3wM0R6VWr4_-WWf2f1J3_bfF3iA"),

            Product(name="Venetian Mask - Red & Black",
                    category="mask",
                    description="An elegant Venetian style mask in rich red and black — inspired by the grand masquerade balls of Venice, Italy. Decorated with intricate patterns, feathers and sequins that give a dramatic and mysterious look. Perfect for costume parties, theatre performances and Halloween events.",
                    buy_price=200, rent_price=40,
                    image_url="https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcS9toJm68lNIWH7M2hf6QokMLqS6u10ZCIpAfq7vBqTRC9jXrSD41HXaNf0expJQJwjF01Zb_pyjDZ3vj-uYciwycm4znj7"),

            Product(name="Superhero Mask - Black",
                    category="mask",
                    description="A cool black superhero mask made from premium quality material that fits comfortably on the face. Perfect for kids and adults who want to complete their superhero look for fancy dress competitions, birthday parties and themed events. The sleek black design gives a powerful and heroic appearance.",
                    buy_price=120, rent_price=25,
                    image_url="https://encrypted-tbn3.gstatic.com/shopping?q=tbn:ANd9GcRKTKPHjLJUksFMBpicHOHa-K0uIXlOQut04R4-lYyD1RuWqQ5EbRToSVes93fUF4ibdkVbFC0PNAlxw7fr6GuoDu0nEYCBbg"),

            # ── FANCY DRESSES ──
            Product(name="Princess Fancy Dress - Pink",
                    category="fancydress",
                    description="A dreamy pink princess fancy dress that will make your little girl feel like royalty. Complete with a beautiful flared skirt, sparkly crown and elegant design inspired by fairy tale princesses. Made from soft breathable fabric that keeps children comfortable during long events and performances.",
                    buy_price=600, rent_price=120,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcQMrK3XtM0KAg1RAMG44PISpMASdpvHGuFw9ghmCTbVmZkg8oEmS8qqAY4cdenCvTiEoxMmvutSxvyne_kfBbYpuWWSMHX4mg"),

            Product(name="Pirate Fancy Dress",
                    category="fancydress",
                    description="A complete and exciting pirate costume that will transport your child to the high seas of adventure. Includes a pirate hat, striped shirt, belt and eye patch — everything needed to create an authentic pirate look. Perfect for fancy dress competitions, Halloween parties and themed birthday celebrations.",
                    buy_price=550, rent_price=110,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcTfRW675-mRFXi-UN3JQOEKP_Z9aA7tBIWn1pdIrV2Ghy2SKkjU1-c86fmGxh-4uhP87KEzHjWuziueqHsC5iECDl1HFxB02keX6t7D2CPMMeiT8cgJR5y8"),

            Product(name="Witch Fancy Dress",
                    category="fancydress",
                    description="A spooky and stylish witch costume perfect for Halloween parties, fancy dress competitions and themed events. Complete with a dramatic black dress, pointed witch hat and accessories that create a hauntingly beautiful look. Available for both kids and adults — guaranteed to make a memorable impression at any event.",
                    buy_price=500, rent_price=100,
                    image_url="https://encrypted-tbn2.gstatic.com/shopping?q=tbn:ANd9GcQhuXW1n4S8F9atL30NTW6UasknJvI68eskhdwBc6yTjLfYbzuz-OkJjDmXp1iMLAr4QWgpF_5mZJZfth0Vi-3GeYOpi5fvHquVPd1IZZf6KY5bJNDReQ_gOA"),

            # ── BRACELETS ──
            Product(name="Traditional Gold Bracelet",
                    category="bracelet",
                    description="A beautifully crafted traditional gold bracelet that adds an ethnic and elegant touch to any outfit. Made with high quality gold plated metal with intricate traditional patterns and designs. Perfect for Navratri, weddings, festivals and any ethnic occasion where you want to look your absolute best.",
                    buy_price=300, rent_price=50,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcQD7Cx_PXeeUOjrEZ2CDfy4ZAWnpeQeVe33H-ykErDSUyByGTA8IX_hUpMGtTXUzYvOAHbjzciKuhACRm2LlD5xk3JXn8eCyg"),

            Product(name="Pearl Bracelet Set",
                    category="bracelet",
                    description="An elegant set of pearl bracelets that add a delicate and sophisticated charm to your look. The lustrous pearls are carefully strung together in a design that complements both traditional and modern outfits. Perfect for brides, bridesmaids and women who love timeless jewellery at weddings and special occasions.",
                    buy_price=250, rent_price=40,
                    image_url="https://encrypted-tbn0.gstatic.com/shopping?q=tbn:ANd9GcRJ-CtnJPvKDRkXegrBqTw4hBu6SXKQ48_xGqxmua6ChFD_y0yHsD0Mzk8fWQ002K8spxJRFRU1I7sZysT_CeTseaRp98Js74-fMTv2w5hL0tJM4G-TalxLJw"),

            Product(name="Kundan Bangles Set",
                    category="bracelet",
                    description="A stunning set of Kundan bangles crafted with beautiful gemstone work and traditional Kundan setting that reflects the rich jewellery heritage of India. The vibrant colours and intricate designs make them perfect for Navratri, Diwali, weddings and all festive occasions. Stack them together for a bold traditional look.",
                    buy_price=350, rent_price=60,
                    image_url="https://encrypted-tbn1.gstatic.com/shopping?q=tbn:ANd9GcTiIW2UnisywpzDeX-lrYFd19sFQj-30MeQYDInpsZ2-l5P20skbhPkgvh6vXyWnZIMWm1VAPw9Z1eReuOTXmOMG7JkA-lvS1hBTU1liAPHZsKw-FbO4ffnVw"),
        ]
        for p in products:
            db.session.add(p)
        db.session.commit()
        print("✅ All products added!")

with app.app_context():
    setup_database()

if __name__ == '__main__':
    app.run(debug=True)

    

