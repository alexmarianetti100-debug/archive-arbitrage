from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure app
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///data/archive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Import models after db initialization
from models import User, Item, Product

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)