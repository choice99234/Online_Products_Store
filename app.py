from flask import Flask, render_template, request, redirect, url_for, jsonify, session,flash
from flask_sqlalchemy import SQLAlchemy
import os
import base64

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    image_data = db.Column(db.LargeBinary, nullable=True)  # Store image as binary data
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    
    category = db.relationship('Category', backref='products', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)  # Add quantity field here
    user = db.relationship('User', backref='cart_items', lazy=True)
    product = db.relationship('Product', backref='cart_items', lazy=True)

    def __init__(self, user_id, product_id, quantity=1):
        self.user_id = user_id
        self.product_id = product_id
        self.quantity = quantity

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Add this route to handle admin login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Hardcoded admin credentials
        admin_username = 'ovilera@onlinestore'
        admin_password = 'admin@123456789'
        
        if username == admin_username and password == admin_password:
            session['username'] = username  # Store username in session to indicate that user is logged in
            return redirect(url_for('admin'))
        else:
            flash("Only admin can access this page.")
            return redirect(url_for('index'))  # Redirect non-admin users to index page
    
    return render_template('login.html')



# Routes
from base64 import b64encode

@app.route('/', methods=['GET', 'POST'])
def index():
    query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'name')

    # Fetch products based on search query
    if query:
        products = Product.query.filter(Product.name.ilike(f"%{query}%")).order_by(sort_by).all()
    else:
        products = Product.query.order_by(sort_by).all()

    # Convert product images to base64 if present
    for product in products:
        if product.image_data:
            # Convert the image data to base64 string
            product.image_base64 = b64encode(product.image_data).decode('utf-8')
        else:
            product.image_base64 = None  # No image available, set to None

    # Initialize the dictionary with all categories
    products_by_category = {category['name']: [] for category in CATEGORIES}
    products_by_category['Uncategorized'] = []  # Fallback for uncategorized products

    # Organize products into categories
    for product in products:
        # Fetch category name by ID, fallback to 'Uncategorized'
        category_name = next((cat['name'] for cat in CATEGORIES if cat['id'] == product.category_id), 'Uncategorized')
        products_by_category[category_name].append(product)

    categories = Category.query.all()
    return render_template('index.html',
                           categories=categories,
                           products=products,
                           query=query,
                           sort_by=sort_by,
                           products_by_category=products_by_category)

category_views = {}

@app.route('/product/<int:product_id>')
def product_details(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Check if the product has an image and convert it to base64
    image_url = None
    if product.image_data:
        image_url = 'data:image/jpeg;base64,' + base64.b64encode(product.image_data).decode('utf-8')
    
    return render_template('product_details.html', product=product, image_url=image_url)

@app.route('/category/<int:category_id>')
def category_products(category_id):
    category = Category.query.get_or_404(category_id)
    products = Product.query.filter_by(category_id=category_id).all()
    return render_template('category_products.html', category=category, products=products)

@app.route('/cart')
def cart():
    user_id = session.get('user_id', 1)  # Retrieve the user_id from the session, defaulting to 1
    cart_items = Cart.query.filter_by(user_id=user_id).all()

    # Encode product images to base64 if they exist
    for item in cart_items:
        if item.product.image_data:
            item.product.image_url = 'data:image/jpeg;base64,' + base64.b64encode(item.product.image_data).decode('utf-8')

    # Calculate total quantity and price
    total_quantity = sum(item.quantity for item in cart_items)
    total_price = sum(item.product.price * item.quantity for item in cart_items)

    # Render the cart template with the necessary data
    return render_template('cart.html', cart_items=cart_items, total_quantity=total_quantity, total_price=total_price)
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    user_id = session.get('user_id', 1)  # Example user_id, replace with actual session data
    
    # Ensure product_id is valid
    if not product_id:
        flash('Invalid product ID.')
        return redirect(url_for('index'))  # Redirect to the index page or handle accordingly
    
    # Check if the product exists
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.')
        return redirect(url_for('index'))  # Redirect to the index page or handle accordingly
    
    # Check if the product is already in the user's cart
    existing_cart_item = Cart.query.filter_by(user_id=user_id, product_id=product_id).first()
    
    if existing_cart_item:
        # If the product is already in the cart, increase the quantity
        existing_cart_item.quantity += 1
        db.session.commit()
    else:
        # Add the product to the cart with quantity 1
        new_cart_item = Cart(user_id=user_id, product_id=product_id, quantity=1)
        db.session.add(new_cart_item)
        db.session.commit()
    
    return redirect(url_for('cart'))  # Redirect to the cart page

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
def remove_from_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
    else:
        db.session.delete(cart_item)
    
    db.session.commit()
    return jsonify({"message": "Item removed", "cart_id": cart_id})

@app.route('/checkout')
def checkout():
    user_id = session.get('user_id', 1)  # Example user_id, replace with actual session data
    cart_items = Cart.query.filter_by(user_id=user_id).all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

# Hardcoded Categories
CATEGORIES = [
    {"id": 1, "name": "Electronics"},
    {"id": 2, "name": "Clothing"},
    {"id": 3, "name": "Home Appliances"},
    {"id": 4, "name": "Books"},
    {"id": 5, "name": "Sports"},
    {"id": 6, "name": "Furniture"},
    {"id": 7, "name": "Toys"},
    {"id": 8, "name": "Beauty & Health"},
    {"id": 9, "name": "Automotive"},
    {"id": 10, "name": "Groceries"},
    {"id": 11, "name": "Music"},
    {"id": 12, "name": "Movies & TV"},
    {"id": 13, "name": "Art & Crafts"},
    {"id": 14, "name": "Pet Supplies"},
    {"id": 15, "name": "Garden & Outdoor"},
    {"id": 16, "name": "Office Supplies"},
    {"id": 17, "name": "Kitchen & Dining"},
    {"id": 18, "name": "Books & Stationery"},
    {"id": 19, "name": "Cell Phones & Accessories"},
    {"id": 20, "name": "Video Games"}
]


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # Get the form data
        name = request.form['name']
        price = request.form['price']
        category_id = request.form['category']
        description = request.form['description']
        
        # Handle the image upload (single image)
        image_file = request.files.get('image')
        image_data = None
        if image_file and allowed_file(image_file.filename):
            # Save the image as binary data
            image_data = image_file.read()  # Read the binary data from the uploaded file

        # Create the new product instance
        new_product = Product(
            name=name,
            price=price,
            category_id=category_id,
            description=description,
            image_data=image_data  # Store the binary data directly in the database
        )
        
        # Add to the database and commit
        db.session.add(new_product)
        db.session.commit()
        
        return redirect(url_for('admin'))

    # Fetch all products
    products = Product.query.all()

    # Fetch the cart from session
    cart = session.get('cart')

    # Encode the image data in base64 for each product to display in template
    for product in products:
        if product.image_data:
            # Check if the image_data is in binary format and convert to base64 for display
            if isinstance(product.image_data, bytes):
                image_base64 = base64.b64encode(product.image_data).decode('utf-8')
                product.image_data = f"data:image/png;base64,{image_base64}"

    # Render the admin template with necessary data
    return render_template('admin.html', categories=CATEGORIES, products=products, cart=cart)
    
@app.route('/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    # Fetch the product by ID or return a 404 error
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if not categories:
        flash('No categories found. Please add some categories first.', 'error')

    if request.method == 'POST':
        # Fetch and validate form data
        product.name = request.form['name']
        product.price = float(request.form['price'])
        product.category_id = int(request.form['category'])
        product.description = request.form['description']

        # Handle image upload
        image = request.files.get('image')
        if image and image.filename:
            image_path = f'static/uploads/{image.filename}'
            image.save(image_path)
            product.image_url = image_path  # Update the product's image URL with the new image path

        # Commit changes to the database
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin'))

    return render_template('edit_product.html', product=product, categories=CATEGORIES)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    # Query the product from the database
    product = Product.query.get_or_404(product_id)
    
    # Delete the product
    db.session.delete(product)
    db.session.commit()

    # Redirect back to the admin dashboard
    return redirect(url_for('admin'))




if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True)