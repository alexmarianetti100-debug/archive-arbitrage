from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Get the global db instance from Flask app
from run import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    subscription_tier = db.Column(db.String(20), default='basic')
    subscription_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False)
    source_id = db.Column(db.String(100), nullable=False)
    source_url = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=False)
    brand = db.Column(db.String(100))
    category = db.Column(db.String(100))
    size = db.Column(db.String(50))
    condition = db.Column(db.String(50))
    source_price = db.Column(db.Float, nullable=False)
    source_shipping = db.Column(db.Float, default=0.0)
    market_price = db.Column(db.Float)
    our_price = db.Column(db.Float)
    margin_percent = db.Column(db.Float)
    images = db.Column(db.Text)  # JSON string
    is_auction = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    
    # Authentication columns
    auth_status = db.Column(db.String(20))  # authentic, suspicious, replica
    auth_confidence = db.Column(db.Float)
    auth_reasons = db.Column(db.Text)  # JSON string
    
    def __repr__(self):
        return f'<Item {self.title}>'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    fingerprint_hash = db.Column(db.String(255), unique=True, nullable=False)
    canonical_name = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    sub_brand = db.Column(db.String(100))
    model = db.Column(db.String(100))
    item_type = db.Column(db.String(100))
    material = db.Column(db.String(100))
    first_seen_at = db.Column(db.DateTime)
    last_sale_at = db.Column(db.DateTime)
    total_sales = db.Column(db.Integer, default=0)
    sales_30d = db.Column(db.Integer, default=0)
    sales_90d = db.Column(db.Integer, default=0)
    avg_sell_through_rate = db.Column(db.Float)
    avg_days_to_sell = db.Column(db.Float)
    velocity_trend = db.Column(db.String(20), default='unknown')
    is_high_velocity = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Product {self.canonical_name}>'