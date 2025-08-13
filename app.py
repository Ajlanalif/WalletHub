from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import secrets
from itsdangerous import URLSafeTimedSerializer
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from flask_migrate import Migrate
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
import os


load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/wh'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size


app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', '587'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')
app.config['MAIL_ASCII_ATTACHMENTS'] = False


# Initialize Flask-Mail
mail = Mail(app)
mail.init_app(app)
# Initialize serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
def create_upload_folder():
    """Create upload folder if it doesn't exist"""
    uploads_dir = os.path.join('static', 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        print(f"Created uploads directory: {uploads_dir}")
create_upload_folder()

def generate_reset_token(user_email):
    """Generate a password reset token for the user"""
    return serializer.dumps(user_email, salt='password-reset-salt')

def verify_reset_token(token, expiration=1800):  # 30 minutes = 1800 seconds
    """Verify the reset token and return email if valid"""
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
        return email
    except:
        return None
    


db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)

class UserDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    photo = db.Column(db.String(250), nullable=True)  # Column for user photo
    user = db.relationship('User', backref=db.backref('details', uselist=False))

class BankBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bank_name = db.Column(db.String(150), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    balance = db.Column(db.Double, nullable=False)
    user = db.relationship('User', backref=db.backref('bank_balance', uselist=False))

class MFSBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mfs_name = db.Column(db.String(150), nullable=False)
    account_no = db.Column(db.String(50), nullable=False)
    balance = db.Column(db.Double, nullable=False)  # Changed from Float to Double
    user = db.relationship('User', backref=db.backref('mfs_accounts', lazy=True))

class WalletBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Double, nullable=False)  # Changed from Float to Double
    user = db.relationship('User', backref=db.backref('wallet_balance', uselist=False))

# Add after your existing models and before the routes
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  
    amount = db.Column(db.Double, nullable=False)  # Changed from Float to Double
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    
    # Source account details
    source_type = db.Column(db.String(10), nullable=False)  # 'wallet', 'bank', or 'mfs'
    source_bank_name = db.Column(db.String(150), nullable=True)
    source_account_number = db.Column(db.String(50), nullable=True)
    source_mfs_name = db.Column(db.String(150), nullable=True)
    source_mfs_number = db.Column(db.String(50), nullable=True)
    
    # Destination account details (for transfers)
    destination_type = db.Column(db.String(10), nullable=True)  # 'wallet', 'bank', or 'mfs'
    destination_bank_name = db.Column(db.String(150), nullable=True)
    destination_account_number = db.Column(db.String(50), nullable=True)
    destination_mfs_name = db.Column(db.String(150), nullable=True)
    destination_mfs_number = db.Column(db.String(50), nullable=True)

    # Relationships
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

    def __init__(self, **kwargs):
        super(Transaction, self).__init__(**kwargs)
        if not self.timestamp:
            self.timestamp = db.func.current_timestamp()

    @property
    def formatted_timestamp(self):
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'amount': self.amount,
            'description': self.description,
            'timestamp': self.formatted_timestamp,
            'source_type': self.source_type,
            'source_details': self.get_source_details(),
            'destination_details': self.get_destination_details() if self.transaction_type == 'transfer' else None
        }

    def get_source_details(self):
        if self.source_type == 'bank':
            return {
                'bank_name': self.source_bank_name,
                'account_number': self.source_account_number
            }
        elif self.source_type == 'mfs':
            return {
                'mfs_name': self.source_mfs_name,
                'account_number': self.source_mfs_number
            }
        else:
            return {'type': 'wallet'}

    def get_destination_details(self):
        if self.destination_type == 'bank':
            return {
                'bank_name': self.destination_bank_name,
                'account_number': self.destination_account_number
            }
        elif self.destination_type == 'mfs':
            return {
                'mfs_name': self.destination_mfs_name,
                'account_number': self.destination_mfs_number
            }
        else:
            return {'type': 'wallet'}
        

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lender_name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Double, nullable=False)
    remaining_amount = db.Column(db.Double, nullable=False)
    date_taken = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    return_date = db.Column(db.Date, nullable=False)
    is_repaid = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('loans', lazy=True))
    
    # Related expense transaction
    expense_transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)
    expense_transaction = db.relationship('Transaction', foreign_keys=[expense_transaction_id])
    
    # Related repayment transactions
    repayments = db.relationship('LoanRepayment', backref='loan', lazy=True)

class LoanRepayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    amount = db.Column(db.Double, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    notes = db.Column(db.Text, nullable=True)

class Receivable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    debtor_name = db.Column(db.String(150), nullable=False)  # Person who owes you money
    amount = db.Column(db.Double, nullable=False)  # Original amount lent
    remaining_amount = db.Column(db.Double, nullable=False)  # Amount still owed
    date_lent = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    expected_return_date = db.Column(db.Date, nullable=True)  # When you expect to get it back
    is_received = db.Column(db.Boolean, default=False)  # Whether fully received
    notes = db.Column(db.Text, nullable=True)
    interest_rate = db.Column(db.Double, nullable=True, default=0.0)  # Optional interest rate
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('receivables', lazy=True))
    
    # Related expense transaction (when you lent the money)
    expense_transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)
    expense_transaction = db.relationship('Transaction', foreign_keys=[expense_transaction_id])
    
    # Related received payments
    payments = db.relationship('ReceivablePayment', backref='receivable', lazy=True)

class ReceivablePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receivable_id = db.Column(db.Integer, db.ForeignKey('receivable.id'), nullable=False)
    amount = db.Column(db.Double, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    notes = db.Column(db.Text, nullable=True)
    
    # Which account received the payment
    received_to_type = db.Column(db.String(10), nullable=False)  # 'wallet', 'bank', or 'mfs'
    received_to_bank_name = db.Column(db.String(150), nullable=True)
    received_to_account_number = db.Column(db.String(50), nullable=True)
    received_to_mfs_name = db.Column(db.String(150), nullable=True)
    received_to_mfs_number = db.Column(db.String(50), nullable=True)

# Add this model after your existing models in app.py
class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref=db.backref('budgets', lazy=True))
    
    # Ensure unique budget per user per month-year
    __table_args__ = (db.UniqueConstraint('user_id', 'month', 'year', name='unique_user_month_budget'),)

@app.context_processor
def inject_user_details():
    """Make user_details available to all templates."""
    if current_user.is_authenticated:
        user_details = UserDetails.query.filter_by(user_id=current_user.id).first()
        return dict(user_details=user_details)
    return dict(user_details=None)

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        user_by_email = User.query.filter_by(email=email).first()
        user_by_username = User.query.filter_by(username=username).first()
        if user_by_email:
            flash('Email address already exists', 'error')
            return redirect(url_for('signup'))
        
        if user_by_username:
            flash('Username already exists', 'error')
            return redirect(url_for('signup'))
        
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup'))
        
        if (len(password) < 8 or not any(char.islower() for char in password) or
            not any(char.isupper() for char in password) or not any(char.isdigit() for char in password) or
            not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/' for char in password)):
            flash('Password must be at least 8 characters long and contain at least one lowercase letter, one uppercase letter, one number, and one special character', 'error')
            return redirect(url_for('signup'))
        
        new_user = User(username=username, email=email, password=generate_password_hash(password, method='sha256'))
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        flash('User created and logged in successfully', 'success')
        return redirect(url_for('initial_user_setup'))
    return render_template('signup.html')

@app.route('/initial_user_setup', methods=['GET', 'POST'])
@login_required
def initial_user_setup():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        address = request.form.get('address')
        phone_number = request.form.get('phone_number')
        photo = request.files.get('photo')

        if photo and allowed_file(photo.filename):
            uploads_dir = app.config['UPLOAD_FOLDER']
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
            file_ext = photo.filename.rsplit('.', 1)[1].lower()
            filename = f"{current_user.username}.{file_ext}"
            photo.save(os.path.join(uploads_dir, filename))
            photo_path = 'uploads/' + filename
        else:
            photo_path = None

        user_details = UserDetails(
            user_id=current_user.id,
            first_name=first_name,
            last_name=last_name,
            address=address,
            phone_number=phone_number,
            photo=photo_path
        )
        db.session.add(user_details)
        db.session.commit()

        flash('User details updated successfully', 'success')
        return redirect(url_for('initial_balance_setup'))

    return render_template('initial_user_setup.html')

@app.route('/initial_balance_setup', methods=['GET', 'POST'])
@login_required
def initial_balance_setup():
    if request.method == 'POST':
        bank_names = request.form.getlist('bank_name[]')
        bank_acc_nos = request.form.getlist('bank_acc_no[]')
        bank_balances = request.form.getlist('bank_balance[]')

        mfs_names = request.form.getlist('mfs_name[]')
        mfs_acc_nos = request.form.getlist('mfs_acc_no[]')
        mfs_balances = request.form.getlist('mfs_balance[]')

        wallet_balance = request.form.get('wallet_balance')

        # Save bank accounts
        for bank_name, bank_acc_no, bank_balance in zip(bank_names, bank_acc_nos, bank_balances):
            if bank_name and bank_acc_no and bank_balance:
                bank_account = BankBalance(
                    user_id=current_user.id,
                    bank_name=bank_name,
                    account_number=bank_acc_no,
                    balance=float(bank_balance)
                )
                db.session.add(bank_account)

        # Save MFS accounts
        for mfs_name, mfs_acc_no, mfs_balance in zip(mfs_names, mfs_acc_nos, mfs_balances):
            if mfs_name and mfs_acc_no and mfs_balance:
                mfs_account = MFSBalance(
                    user_id=current_user.id,
                    mfs_name=mfs_name,
                    account_no=mfs_acc_no,
                    balance=float(mfs_balance)
                )
                db.session.add(mfs_account)

        # Save wallet balance
        if wallet_balance:
            wallet_balance_entry = WalletBalance(
                user_id=current_user.id,
                balance=float(wallet_balance)
            )
            db.session.add(wallet_balance_entry)

        db.session.commit()

        flash('Initial balance setup completed successfully', 'success')
        return redirect(url_for('dashboard'))

    return render_template('initial_balance_setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first() or User.query.filter_by(username=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                flash('Admin logged in successfully', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Logged in successfully', 'success')
                return redirect(url_for('dashboard'))
        else:
            if not user:
                flash('Invalid email', 'error')
            elif not check_password_hash(user.password, password):
                flash('Wrong Password', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(current_user.id)
    user_details = UserDetails.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        # Determine which form was submitted
        if 'update_details' in request.form:
            # Update user details
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            address = request.form.get('address')
            phone_number = request.form.get('phone_number')
            
            user_details.first_name = first_name
            user_details.last_name = last_name
            user_details.address = address
            user_details.phone_number = phone_number
            
            db.session.commit()
            flash('Profile details updated successfully', 'success')
            
        elif 'update_photo' in request.form:
            # Update profile photo
            photo = request.files.get('photo')
            
            if photo and allowed_file(photo.filename):
                # Delete old photo if exists
                if user_details.photo and os.path.exists(user_details.photo):
                    try:
                        os.remove(user_details.photo)
                    except:
                        pass
                
                file_ext = photo.filename.rsplit('.', 1)[1].lower()
                filename = f"{current_user.username}.{file_ext}"
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                photo.save(photo_path)
                user_details.photo =  'static/uploads/' + filename
                
                db.session.commit()
                flash('Profile photo updated successfully', 'success')
            else:
                flash('Invalid file type. Only images are allowed.', 'error')
                
        elif 'change_password' in request.form:
            # Change password
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not check_password_hash(user.password, current_password):
                flash('Current password is incorrect', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match', 'error')
            elif len(new_password) < 8:
                flash('Password must be at least 8 characters long', 'error')
            else:
                user.password = generate_password_hash(new_password, method='sha256')
                db.session.commit()
                flash('Password changed successfully', 'success')
        
        return redirect(url_for('profile'))
    
    # Get summary of financial accounts
    bank_accounts = BankBalance.query.filter_by(user_id=current_user.id).all()
    mfs_accounts = MFSBalance.query.filter_by(user_id=current_user.id).all()
    wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
    
    bank_count = len(bank_accounts)
    mfs_count = len(mfs_accounts)
    wallet_exists = wallet is not None
    
    # Get activity summary
    transactions_count = Transaction.query.filter_by(user_id=current_user.id).count()
    loans_count = Loan.query.filter_by(user_id=current_user.id).count()
    
    return render_template('profile.html', 
                          user=user, 
                          user_details=user_details,
                          bank_count=bank_count,
                          mfs_count=mfs_count,
                          wallet_exists=wallet_exists,
                          transactions_count=transactions_count,
                          loans_count=loans_count)

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    delete_confirmation = request.form.get('delete_confirmation')
    password = request.form.get('password')
    
    if delete_confirmation != 'DELETE':
        flash('Incorrect confirmation text. Account was not deleted.', 'error')
        return redirect(url_for('profile'))
    
    # Verify password
    if not check_password_hash(current_user.password, password):
        flash('Incorrect password. Account was not deleted.', 'error')
        return redirect(url_for('profile'))
    
    try:
        # Get user ID before logout (to use for deletion)
        user_id = current_user.id
        
        # Step 1: Get all loan IDs for this user
        loan_ids = [loan.id for loan in Loan.query.filter_by(user_id=user_id).all()]
        
        # Step 2: Delete loan repayments for those loans
        if loan_ids:
            LoanRepayment.query.filter(LoanRepayment.loan_id.in_(loan_ids)).delete(synchronize_session=False)
        
        # Step 3: Delete loans
        Loan.query.filter_by(user_id=user_id).delete()
        
        # Delete transactions
        Transaction.query.filter_by(user_id=user_id).delete()
        
        # Delete account balances
        BankBalance.query.filter_by(user_id=user_id).delete()
        MFSBalance.query.filter_by(user_id=user_id).delete()
        WalletBalance.query.filter_by(user_id=user_id).delete()
        
        # Delete user details
        UserDetails.query.filter_by(user_id=user_id).delete()
        
        # Delete the user record
        User.query.filter_by(id=user_id).delete()
        
        # Commit the changes
        db.session.commit()
        
        # Log out the user
        logout_user()
        
        flash('Your account and all associated data have been permanently deleted.', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting account: {str(e)}")
        flash('An error occurred while deleting your account. Please try again.', 'error')
        return redirect(url_for('profile'))
    
@app.route('/dashboard')
@login_required
def dashboard():
    user_details = UserDetails.query.filter_by(user_id=current_user.id).first()
    if not user_details:
        flash('Please complete your user details setup', 'error')
        return redirect(url_for('initial_user_setup'))

    # Get all balances from database
    bank_balances = BankBalance.query.filter_by(user_id=current_user.id).all()
    mfs_balances = MFSBalance.query.filter_by(user_id=current_user.id).all()
    wallet_balance = WalletBalance.query.filter_by(user_id=current_user.id).first()

    # Calculate total balances with two decimal precision
    bank_balance = round(sum(bank.balance for bank in bank_balances), 2)
    mfs_balance = round(sum(mfs.balance for mfs in mfs_balances), 2)
    wallet_balance_amount = round(wallet_balance.balance, 2) if wallet_balance else 0.00
    
    total_balance = round(bank_balance + mfs_balance + wallet_balance_amount, 2)
    
    # Get active loans information
    active_loans = Loan.query.filter_by(user_id=current_user.id, is_repaid=False).all()
    active_loans_amount = round(sum(loan.remaining_amount for loan in active_loans), 2)
    
    # Get loans due soon (next 7 days)
    today = date.today()
    due_soon_loans = [loan for loan in active_loans if (loan.return_date - today).days <= 7]

    # Get active receivables information
    active_receivables = Receivable.query.filter_by(user_id=current_user.id, is_received=False).all()
    active_receivables_amount = round(sum(receivable.remaining_amount for receivable in active_receivables), 2)
    
    # Get receivables due soon (next 7 days)
    due_soon_receivables = [receivable for receivable in active_receivables 
                           if receivable.expected_return_date and (receivable.expected_return_date - today).days <= 7]
    # Get current date
    current_date = date.today()
    current_month = current_date.month
    current_year = current_date.year
    
    # Check if budget exists for current month
    current_budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month,
        year=current_year
    ).first()
    
    # If no budget exists, set budget to None to trigger the modal
    budget_amount = current_budget.amount if current_budget else None

    # Calculate current month's total expenses for budget comparison
    start_date = date(current_year, current_month, 1)
    if current_month == 12:
        end_date = date(current_year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(current_year, current_month + 1, 1) - timedelta(days=1)
    
    # Get all expense transactions for the current month
    monthly_expenses = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type == 'expense',
        func.date(Transaction.timestamp) >= start_date,
        func.date(Transaction.timestamp) <= end_date
    ).all()
    
    # Calculate total monthly expenses
    total_monthly_expenses = round(sum(expense.amount for expense in monthly_expenses), 2)


    return render_template('dashboard.html', 
                         user_details=user_details,
                         total_balance=total_balance,
                         total_monthly_expenses=total_monthly_expenses,
                         bank_balance=bank_balance, 
                         mfs_balance=mfs_balance, 
                         wallet_balance=wallet_balance_amount,
                         bank_accounts=bank_balances,
                         mfs_accounts=mfs_balances,
                         today_date=date.today().strftime('%Y-%m-%d'),
                         active_loans=active_loans,
                         active_loans_amount=active_loans_amount,
                         due_soon_loans=due_soon_loans,
                         active_receivables=active_receivables,
                         active_receivables_amount=active_receivables_amount,
                         due_soon_receivables=due_soon_receivables,
                         budget=budget_amount,
                         current_month=current_month,
                         current_year=current_year,
                         month_name=current_date.strftime('%B'))

@app.route('/bank_transactions')
@login_required
def bank_transactions():
    # Get all bank accounts and total balance
    bank_accounts = BankBalance.query.filter_by(user_id=current_user.id).all()
    bank_balance = sum(bank.balance for bank in bank_accounts)
    
    # Build the query for transactions - INCLUDE RECEIVED TRANSFERS
    query = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        db.or_(
            Transaction.source_type == 'bank',
            db.and_(
                Transaction.transaction_type == 'transfer',
                Transaction.destination_type == 'bank'
            )
        )
    )
    
    # Filter by specific bank account if requested
    account_id = request.args.get('account')
    if account_id and account_id != 'all':
        bank_account = BankBalance.query.get(int(account_id))
        if bank_account:
            query = query.filter(
                db.or_(
                    db.and_(
                        Transaction.source_bank_name == bank_account.bank_name,
                        Transaction.source_account_number == bank_account.account_number
                    ),
                    db.and_(
                        Transaction.destination_bank_name == bank_account.bank_name,
                        Transaction.destination_account_number == bank_account.account_number
                    )
                )
            )
    
    # Apply other filters
    transaction_type = request.args.get('type')
    if transaction_type and transaction_type != 'all':
        query = query.filter_by(transaction_type=transaction_type)
    
    date_from = request.args.get('date_from')
    if date_from:
        query = query.filter(Transaction.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    date_to = request.args.get('date_to')
    if date_to:
        # Add one day to include the end date
        end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)
    
    # Get transactions ordered by newest first
    transactions = query.order_by(Transaction.timestamp.desc(), Transaction.id.desc()).all()
    
    return render_template(
        'bank_transactions.html',
        bank_accounts=bank_accounts,
        bank_balance=bank_balance,
        transactions=transactions
    )

@app.route('/add_bank_account', methods=['POST'])
@login_required
def add_bank_account():
    if request.method == 'POST':
        bank_name = request.form.get('bank_name')
        account_number = request.form.get('account_number')
        balance = float(request.form.get('balance'))
        
        # Check if this account already exists
        existing_account = BankBalance.query.filter_by(
            user_id=current_user.id,
            bank_name=bank_name,
            account_number=account_number
        ).first()
        
        if existing_account:
            flash('This bank account already exists', 'error')
            return redirect(url_for('bank_transactions'))
        
        # Create new bank account
        new_account = BankBalance(
            user_id=current_user.id,
            bank_name=bank_name,
            account_number=account_number,
            balance=balance
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        flash('Bank account added successfully', 'success')
    
    return redirect(url_for('bank_transactions'))

@app.route('/mfs_transactions')
@login_required
def mfs_transactions():
    # Get all MFS accounts and total balance
    mfs_accounts = MFSBalance.query.filter_by(user_id=current_user.id).all()
    mfs_balance = round(sum(mfs.balance for mfs in mfs_accounts),2)
    
    # Build the query for transactions - INCLUDE RECEIVED TRANSFERS
    query = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        db.or_(
            Transaction.source_type == 'mfs',
            db.and_(
                Transaction.transaction_type == 'transfer',
                Transaction.destination_type == 'mfs'
            )
        )
    )
    
    # Filter by specific MFS account if requested
    account_id = request.args.get('account')
    if account_id and account_id != 'all':
        mfs_account = MFSBalance.query.get(int(account_id))
        if mfs_account:
            query = query.filter(
                db.or_(
                    db.and_(
                        Transaction.source_mfs_name == mfs_account.mfs_name,
                        Transaction.source_mfs_number == mfs_account.account_no
                    ),
                    db.and_(
                        Transaction.destination_mfs_name == mfs_account.mfs_name,
                        Transaction.destination_mfs_number == mfs_account.account_no
                    )
                )
            )
    
    # Apply other filters
    transaction_type = request.args.get('type')
    if transaction_type and transaction_type != 'all':
        query = query.filter_by(transaction_type=transaction_type)
    
    date_from = request.args.get('date_from')
    if date_from:
        query = query.filter(Transaction.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    date_to = request.args.get('date_to')
    if date_to:
        # Add one day to include the end date
        end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)
    
    # Get transactions ordered by DATE FIRST, then by ID (both descending for newest first)
    transactions = query.order_by(Transaction.timestamp.desc(), Transaction.id.desc()).all()
    
    return render_template(
        'mfs_transactions.html',
        mfs_accounts=mfs_accounts,
        mfs_balance=mfs_balance,
        transactions=transactions
    )

@app.route('/add_mfs_account', methods=['POST'])
@login_required
def add_mfs_account():
    if request.method == 'POST':
        mfs_name = request.form.get('mfs_name')
        account_no = request.form.get('account_no')
        balance = float(request.form.get('balance'))
        
        # Check if this account already exists
        existing_account = MFSBalance.query.filter_by(
            user_id=current_user.id,
            mfs_name=mfs_name,
            account_no=account_no
        ).first()
        
        if existing_account:
            flash('This MFS account already exists', 'error')
            return redirect(url_for('mfs_transactions'))
        
        # Create new MFS account
        new_account = MFSBalance(
            user_id=current_user.id,
            mfs_name=mfs_name,
            account_no=account_no,
            balance=balance
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        flash('MFS account added successfully', 'success')
    
    return redirect(url_for('mfs_transactions'))

@app.route('/wallet_transactions')
@login_required
def wallet_transactions():
    # Get wallet balance
    wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
    wallet_balance = wallet.balance if wallet else 0
    
    # Build the query for transactions - include both sent and received transfers
    query = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        db.or_(
            Transaction.source_type == 'wallet',
            db.and_(
                Transaction.transaction_type == 'transfer',
                Transaction.destination_type == 'wallet'
            )
        )
    )
    
    # Apply filters if provided
    transaction_type = request.args.get('type')
    if transaction_type and transaction_type != 'all':
        query = query.filter_by(transaction_type=transaction_type)
    
    date_from = request.args.get('date_from')
    if date_from:
        query = query.filter(Transaction.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    date_to = request.args.get('date_to')
    if date_to:
        # Add one day to include the end date
        end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)
    
    # Order by newest first
    transactions = query.order_by(Transaction.timestamp.desc(), Transaction.id.desc()).all()
    
    return render_template(
        'wallet_transactions.html',
        wallet_balance=wallet_balance,
        transactions=transactions
    )

@app.route('/all_transactions')
@login_required
def all_transactions():
    # Get balances
    bank_balance = round(sum(account.balance for account in BankBalance.query.filter_by(user_id=current_user.id).all()),2)
    mfs_balance =  round(sum(account.balance for account in MFSBalance.query.filter_by(user_id=current_user.id).all()),2)
    wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
    wallet_balance = wallet.balance if wallet else 0
    total_balance = round((bank_balance + mfs_balance + wallet_balance),2)
    
    # Build the query for all transactions
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    # Apply filters
    account_type = request.args.get('account_type')
    if account_type and account_type != 'all':
        query = query.filter_by(source_type=account_type)
    
    transaction_type = request.args.get('type')
    if transaction_type and transaction_type != 'all':
        query = query.filter_by(transaction_type=transaction_type)
    
    date_from = request.args.get('date_from')
    if date_from:
        query = query.filter(Transaction.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
    
    date_to = request.args.get('date_to')
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(Transaction.timestamp < end_date)
    
    search_term = request.args.get('search')
    if search_term:
        search = f"%{search_term}%"
        query = query.filter(
            db.or_(
                Transaction.description.ilike(search),
                Transaction.category.ilike(search)
            )
        )
    
    # Get transactions ordered by newest first
    transactions = query.order_by(Transaction.timestamp.desc(), Transaction.id.desc()).all()
    
    # Calculate income and expense totals for the current filtered set
    income_total = round(sum(t.amount for t in transactions if t.transaction_type == 'income'),2)
    expense_total = round(sum(t.amount for t in transactions if t.transaction_type == 'expense'),2)
    
    return render_template(
        'all_transactions.html',
        transactions=transactions,
        bank_balance=bank_balance,
        mfs_balance=mfs_balance,
        wallet_balance=wallet_balance,
        total_balance=total_balance,
        income_total=income_total,
        expense_total=expense_total
    )

@app.route('/delete_transaction', methods=['POST'])
@login_required
def delete_transaction():
    transaction_id = request.form.get('transaction_id')
    
    # Find the transaction
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first()
    
    if not transaction:
        flash('Transaction not found', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Reverse the effect on account balance
    if transaction.transaction_type == 'income':
        if transaction.source_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if wallet:
                wallet.balance -= transaction.amount
        elif transaction.source_type == 'bank':
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=transaction.source_bank_name,
                account_number=transaction.source_account_number
            ).first()
            if bank:
                bank.balance -= transaction.amount
        elif transaction.source_type == 'mfs':
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=transaction.source_mfs_name,
                account_no=transaction.source_mfs_number
            ).first()
            if mfs:
                mfs.balance -= transaction.amount
    
    elif transaction.transaction_type == 'expense':
        if transaction.source_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if wallet:
                wallet.balance += transaction.amount
        elif transaction.source_type == 'bank':
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=transaction.source_bank_name,
                account_number=transaction.source_account_number
            ).first()
            if bank:
                bank.balance += transaction.amount
        elif transaction.source_type == 'mfs':
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=transaction.source_mfs_name,
                account_no=transaction.source_mfs_number
            ).first()
            if mfs:
                mfs.balance += transaction.amount
    
    elif transaction.transaction_type == 'transfer':
        # Reverse source account (add money back)
        if transaction.source_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if wallet:
                wallet.balance += transaction.amount
        elif transaction.source_type == 'bank':
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=transaction.source_bank_name,
                account_number=transaction.source_account_number
            ).first()
            if bank:
                bank.balance += transaction.amount
        elif transaction.source_type == 'mfs':
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=transaction.source_mfs_name,
                account_no=transaction.source_mfs_number
            ).first()
            if mfs:
                mfs.balance += transaction.amount
        
        # Reverse destination account (subtract money)
        if transaction.destination_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if wallet:
                wallet.balance -= transaction.amount
        elif transaction.destination_type == 'bank':
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=transaction.destination_bank_name,
                account_number=transaction.destination_account_number
            ).first()
            if bank:
                bank.balance -= transaction.amount
        elif transaction.destination_type == 'mfs':
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=transaction.destination_mfs_name,
                account_no=transaction.destination_mfs_number
            ).first()
            if mfs:
                mfs.balance -= transaction.amount
    
    # Delete the transaction
    db.session.delete(transaction)
    db.session.commit()
    
    flash('Transaction deleted successfully', 'success')
    return redirect(request.referrer or url_for('dashboard'))


@app.route('/edit_transaction', methods=['POST'])
@login_required
def edit_transaction():
    transaction_id = request.form.get('transaction_id')
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    date_str = request.form.get('date')
    description = request.form.get('description', '')
    
    # Find the transaction
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first()
    
    if not transaction:
        flash('Transaction not found', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Store original values for proper balance adjustment
    original_amount = transaction.amount
    original_type = transaction.transaction_type
    
    # If amount has changed, adjust account balances
    if amount != original_amount:
        # For income transactions
        if transaction.transaction_type == 'income':
            if transaction.source_type == 'wallet':
                wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
                if wallet:
                    # Remove old amount and add new amount
                    wallet.balance = wallet.balance - original_amount + amount
            elif transaction.source_type == 'bank':
                bank = BankBalance.query.filter_by(
                    user_id=current_user.id,
                    bank_name=transaction.source_bank_name,
                    account_number=transaction.source_account_number
                ).first()
                if bank:
                    bank.balance = bank.balance - original_amount + amount
            elif transaction.source_type == 'mfs':
                mfs = MFSBalance.query.filter_by(
                    user_id=current_user.id,
                    mfs_name=transaction.source_mfs_name,
                    account_no=transaction.source_mfs_number
                ).first()
                if mfs:
                    mfs.balance = mfs.balance - original_amount + amount
        
        # For expense transactions
        elif transaction.transaction_type == 'expense':
            if transaction.source_type == 'wallet':
                wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
                if wallet:
                    # Add back old amount and remove new amount
                    wallet.balance = wallet.balance + original_amount - amount
                    if wallet.balance < 0:
                        flash('Insufficient funds in wallet', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
            elif transaction.source_type == 'bank':
                bank = BankBalance.query.filter_by(
                    user_id=current_user.id,
                    bank_name=transaction.source_bank_name,
                    account_number=transaction.source_account_number
                ).first()
                if bank:
                    bank.balance = bank.balance + original_amount - amount
                    if bank.balance < 0:
                        flash('Insufficient funds in bank account', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
            elif transaction.source_type == 'mfs':
                mfs = MFSBalance.query.filter_by(
                    user_id=current_user.id,
                    mfs_name=transaction.source_mfs_name,
                    account_no=transaction.source_mfs_number
                ).first()
                if mfs:
                    mfs.balance = mfs.balance + original_amount - amount
                    if mfs.balance < 0:
                        flash('Insufficient funds in MFS account', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
        
        # For transfer transactions
        elif transaction.transaction_type == 'transfer':
            # First adjust source account
            if transaction.source_type == 'wallet':
                wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
                if wallet:
                    # Add back old amount and remove new amount
                    wallet.balance = wallet.balance + original_amount - amount
                    if wallet.balance < 0:
                        flash('Insufficient funds in wallet', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
            elif transaction.source_type == 'bank':
                bank = BankBalance.query.filter_by(
                    user_id=current_user.id,
                    bank_name=transaction.source_bank_name,
                    account_number=transaction.source_account_number
                ).first()
                if bank:
                    bank.balance = bank.balance + original_amount - amount
                    if bank.balance < 0:
                        flash('Insufficient funds in bank account', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
            elif transaction.source_type == 'mfs':
                mfs = MFSBalance.query.filter_by(
                    user_id=current_user.id,
                    mfs_name=transaction.source_mfs_name,
                    account_no=transaction.source_mfs_number
                ).first()
                if mfs:
                    mfs.balance = mfs.balance + original_amount - amount
                    if mfs.balance < 0:
                        flash('Insufficient funds in MFS account', 'error')
                        return redirect(request.referrer or url_for('dashboard'))
            
            # Then adjust destination account
            if transaction.destination_type == 'wallet':
                wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
                if wallet:
                    # Remove old amount and add new amount
                    wallet.balance = wallet.balance - original_amount + amount
            elif transaction.destination_type == 'bank':
                bank = BankBalance.query.filter_by(
                    user_id=current_user.id,
                    bank_name=transaction.destination_bank_name,
                    account_number=transaction.destination_account_number
                ).first()
                if bank:
                    bank.balance = bank.balance - original_amount + amount
            elif transaction.destination_type == 'mfs':
                mfs = MFSBalance.query.filter_by(
                    user_id=current_user.id,
                    mfs_name=transaction.destination_mfs_name,
                    account_no=transaction.destination_mfs_number
                ).first()
                if mfs:
                    mfs.balance = mfs.balance - original_amount + amount
    
    # Update transaction details
    transaction.amount = amount
    if category:
        transaction.category = category
    if description:
        transaction.description = description
    
    # Update timestamp if date provided
    if date_str:
        transaction.timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    
    db.session.commit()
    
    flash('Transaction updated successfully', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/monthly_tracker', methods=['GET'])
@login_required
def monthly_tracker():
    # Get the requested month and year, default to current month
    current_date = date.today()
    year = request.args.get('year', current_date.year, type=int)
    month = request.args.get('month', current_date.month, type=int)
    
    # Create date range for the month
    start_date = date(year, month, 1)
    # Get the last day of the month
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    # Format for display
    month_name = start_date.strftime('%B %Y')
    
    # Get all transactions for the month
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        func.date(Transaction.timestamp) >= start_date,
        func.date(Transaction.timestamp) <= end_date
    ).order_by(Transaction.timestamp).all()
    
    # Separate income and expenses
    incomes = [t for t in transactions if t.transaction_type == 'income']
    expenses = [t for t in transactions if t.transaction_type == 'expense']
    
    # Group by category
    income_by_category = {}
    for income in incomes:
        category = income.category or 'Uncategorized'
        if category not in income_by_category:
            income_by_category[category] = 0
        income_by_category[category] += income.amount
    
    expense_by_category = {}
    for expense in expenses:
        category = expense.category or 'Uncategorized'
        if category not in expense_by_category:
            expense_by_category[category] = 0
        expense_by_category[category] += expense.amount
    
    # Calculate totals
    total_income = round(sum(income.amount for income in incomes),2)
    total_expense = round(sum(expense.amount for expense in expenses),2)
    net_amount = round(total_income - total_expense,2)
    
    # For navigation between months
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    # Create month names list for dropdown
    month_names = [date(2000, i, 1).strftime('%B') for i in range(1, 13)]
    
    return render_template(
        'monthly_tracker.html',
        month_name=month_name,
        year=year,
        month=month,
        income_by_category=income_by_category,
        expense_by_category=expense_by_category,
        total_income=total_income,
        total_expense=total_expense,
        net_amount=net_amount,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        current_year=current_date.year,
        current_month=current_date.month,
        date=date,  # Pass the date class
        month_names=month_names  # Pass pre-calculated month names
    )

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'null')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get data for admin dashboard
    contacts = Contact.query.all()
    users = User.query.all()
    user_count = len(users)
    
    return render_template(
        'admin/dashboard.html',
        contacts=contacts,
        users=users,
        user_count=user_count
    )

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_details(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    user_details = UserDetails.query.filter_by(user_id=user_id).first()
    
    return render_template('admin/user_details.html', user=user, user_details=user_details)


@app.route('/income', methods=['POST'])
@login_required
def income():
    account_type = request.form.get('account_type')
    amount = float(request.form.get('amount'))
    date_str = request.form.get('date')
    description = request.form.get('description', 'Uncategorized')
    
    # Convert date string to datetime
    if date_str:
        timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()
    
    # Handle different account types
    if account_type == 'wallet':
        wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
        if not wallet:
            wallet = WalletBalance(user_id=current_user.id, balance=0)
            db.session.add(wallet)
        
        wallet.balance += amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='income',
            amount=amount,
            category=description,
            timestamp=timestamp,
            source_type='wallet'
        )
        
    elif account_type == 'bank':
        bank_name = request.form.get('bank_name')
        bank_acc_no = request.form.get('bank_acc_no')
        
        bank = BankBalance.query.filter_by(
            user_id=current_user.id,
            bank_name=bank_name,
            account_number=bank_acc_no
        ).first()
        
        if not bank:
            flash('Bank account not found', 'error')
            return redirect(url_for('dashboard'))
        
        bank.balance += amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='income',
            amount=amount,
            category=description,
            timestamp=timestamp,
            source_type='bank',
            source_bank_name=bank_name,
            source_account_number=bank_acc_no
        )
        
    elif account_type == 'mfs':
        mfs_name = request.form.get('mfs_name')
        mfs_acc_no = request.form.get('mfs_acc_no')
        
        mfs = MFSBalance.query.filter_by(
            user_id=current_user.id,
            mfs_name=mfs_name,
            account_no=mfs_acc_no
        ).first()
        
        if not mfs:
            flash('MFS account not found', 'error')
            return redirect(url_for('dashboard'))
        
        mfs.balance += amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='income',
            amount=amount,
            category=description,
            timestamp=timestamp,
            source_type='mfs',
            source_mfs_name=mfs_name,
            source_mfs_number=mfs_acc_no
        )
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Income added successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/expense', methods=['POST'])
@login_required
def expense():
    account_type = request.form.get('account_type')
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    date_str = request.form.get('date')
    description = request.form.get('description', '')
    
    # Convert date string to datetime
    if date_str:
        timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()
    
    # Handle different account types
    if account_type == 'wallet':
        wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
        if not wallet or wallet.balance < amount:
            flash('Insufficient funds in your wallet', 'error')
            return redirect(url_for('dashboard'))
        
        wallet.balance -= amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='expense',
            amount=amount,
            category=category,
            description=description,
            timestamp=timestamp,
            source_type='wallet'
        )
        
    elif account_type == 'bank':
        bank_name = request.form.get('bank_name')
        bank_acc_no = request.form.get('bank_acc_no')
        
        bank = BankBalance.query.filter_by(
            user_id=current_user.id,
            bank_name=bank_name,
            account_number=bank_acc_no
        ).first()
        
        if not bank:
            flash('Bank account not found', 'error')
            return redirect(url_for('dashboard'))
            
        if bank.balance < amount:
            flash('Insufficient funds in your bank account', 'error')
            return redirect(url_for('dashboard'))
            
        bank.balance -= amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='expense',
            amount=amount,
            category=category,
            description=description,
            timestamp=timestamp,
            source_type='bank',
            source_bank_name=bank_name,
            source_account_number=bank_acc_no
        )
        
    elif account_type == 'mfs':
        mfs_name = request.form.get('mfs_name')
        mfs_acc_no = request.form.get('mfs_acc_no')
        
        mfs = MFSBalance.query.filter_by(
            user_id=current_user.id,
            mfs_name=mfs_name,
            account_no=mfs_acc_no
        ).first()
        
        if not mfs:
            flash('MFS account not found', 'error')
            return redirect(url_for('dashboard'))
            
        if mfs.balance < amount:
            flash('Insufficient funds in your MFS account', 'error')
            return redirect(url_for('dashboard'))
            
        mfs.balance -= amount
        
        transaction = Transaction(
            user_id=current_user.id,
            transaction_type='expense',
            amount=amount,
            category=category,
            description=description,
            timestamp=timestamp,
            source_type='mfs',
            source_mfs_name=mfs_name,
            source_mfs_number=mfs_acc_no
        )
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Expense recorded successfully', 'success')
    return redirect(url_for('dashboard'))


@app.route('/transfer', methods=['POST'])
@login_required
def transfer():
    sender_account_type = request.form.get('sender_account_type')
    receiver_account_type = request.form.get('receiver_account_type')
    amount = float(request.form.get('amount'))
    date_str = request.form.get('date')
    description = request.form.get('description', '')
    
    # Convert date string to datetime
    if date_str:
        timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()
    
    # 1. Deduct from source account
    source_type = source_bank_name = source_account_number = source_mfs_name = source_mfs_number = None
    
    if sender_account_type == 'wallet':
        wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
        if not wallet or wallet.balance < amount:
            flash('Insufficient funds in your wallet', 'error')
            return redirect(url_for('dashboard'))
        
        wallet.balance -= amount
        source_type = 'wallet'
        
    elif sender_account_type == 'bank':
        sender_bank_name = request.form.get('sender_bank_name')
        sender_bank_acc_no = request.form.get('sender_bank_acc_no')
        
        bank = BankBalance.query.filter_by(
            user_id=current_user.id,
            bank_name=sender_bank_name,
            account_number=sender_bank_acc_no
        ).first()
        
        if not bank:
            flash('Source bank account not found', 'error')
            return redirect(url_for('dashboard'))
            
        if bank.balance < amount:
            flash('Insufficient funds in your bank account', 'error')
            return redirect(url_for('dashboard'))
            
        bank.balance -= amount
        source_type = 'bank'
        source_bank_name = sender_bank_name
        source_account_number = sender_bank_acc_no
        
    elif sender_account_type == 'mfs':
        sender_mfs_name = request.form.get('sender_mfs_name')
        sender_mfs_acc_no = request.form.get('sender_mfs_acc_no')
        
        mfs = MFSBalance.query.filter_by(
            user_id=current_user.id,
            mfs_name=sender_mfs_name,
            account_no=sender_mfs_acc_no
        ).first()
        
        if not mfs:
            flash('Source MFS account not found', 'error')
            return redirect(url_for('dashboard'))
            
        if mfs.balance < amount:
            flash('Insufficient funds in your MFS account', 'error')
            return redirect(url_for('dashboard'))
            
        mfs.balance -= amount
        source_type = 'mfs'
        source_mfs_name = sender_mfs_name
        source_mfs_number = sender_mfs_acc_no
    
    # 2. Add to destination account
    dest_type = dest_bank_name = dest_account_number = dest_mfs_name = dest_mfs_number = None
    
    if receiver_account_type == 'wallet':
        wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
        if not wallet:
            wallet = WalletBalance(user_id=current_user.id, balance=0)
            db.session.add(wallet)
        
        wallet.balance += amount
        dest_type = 'wallet'
        
    elif receiver_account_type == 'bank':
        receiver_bank_name = request.form.get('receiver_bank_name')
        receiver_bank_acc_no = request.form.get('receiver_bank_acc_no')
        
        bank = BankBalance.query.filter_by(
            user_id=current_user.id,
            bank_name=receiver_bank_name,
            account_number=receiver_bank_acc_no
        ).first()
        
        if not bank:
            flash('Destination bank account not found', 'error')
            return redirect(url_for('dashboard'))
            
        bank.balance += amount
        dest_type = 'bank'
        dest_bank_name = receiver_bank_name
        dest_account_number = receiver_bank_acc_no
        
    elif receiver_account_type == 'mfs':
        receiver_mfs_name = request.form.get('receiver_mfs_name')
        receiver_mfs_acc_no = request.form.get('receiver_mfs_acc_no')
        
        mfs = MFSBalance.query.filter_by(
            user_id=current_user.id,
            mfs_name=receiver_mfs_name,
            account_no=receiver_mfs_acc_no
        ).first()
        
        if not mfs:
            flash('Destination MFS account not found', 'error')
            return redirect(url_for('dashboard'))
            
        mfs.balance += amount
        dest_type = 'mfs'
        dest_mfs_name = receiver_mfs_name
        dest_mfs_number = receiver_mfs_acc_no
    
    # 3. Create transaction record
    transaction = Transaction(
        user_id=current_user.id,
        transaction_type='transfer',
        amount=amount,
        description=description,
        timestamp=timestamp,
        source_type=source_type,
        source_bank_name=source_bank_name,
        source_account_number=source_account_number,
        source_mfs_name=source_mfs_name,
        source_mfs_number=source_mfs_number,
        destination_type=dest_type,
        destination_bank_name=dest_bank_name,
        destination_account_number=dest_account_number,
        destination_mfs_name=dest_mfs_name,
        destination_mfs_number=dest_mfs_number
    )
    
    db.session.add(transaction)
    db.session.commit()
    
    flash('Transfer completed successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/loans')
@login_required
def loans():
    # Get all loans for the current user
    active_loans = Loan.query.filter_by(
        user_id=current_user.id,
        is_repaid=False
    ).order_by(Loan.return_date).all()
    
    repaid_loans = Loan.query.filter_by(
        user_id=current_user.id,
        is_repaid=True
    ).order_by(Loan.date_taken.desc()).all()
    
    # Get wallet, bank, and MFS accounts for repayment source
    wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
    bank_accounts = BankBalance.query.filter_by(user_id=current_user.id).all()
    mfs_accounts = MFSBalance.query.filter_by(user_id=current_user.id).all()
    
    # Calculate totals
    total_active_amount = sum(loan.remaining_amount for loan in active_loans) if active_loans else 0
    total_repaid_amount = sum(loan.amount for loan in repaid_loans) if repaid_loans else 0
    
    # Calculate loans due soon and overdue
    today = date.today()
    due_soon_amount = sum(loan.remaining_amount for loan in active_loans if 0 < (loan.return_date - today).days <= 7)
    overdue_amount = sum(loan.remaining_amount for loan in active_loans if (loan.return_date - today).days <= 0)
    
    return render_template(
        'loans.html',
        active_loans=active_loans,
        repaid_loans=repaid_loans,
        today=today,  # Pass the date object directly
        total_loans=total_active_amount,
        due_soon=due_soon_amount,
        overdue=overdue_amount,
        total_active_amount=total_active_amount,
        total_repaid_amount=total_repaid_amount,
        wallet=wallet,
        bank_accounts=bank_accounts,
        mfs_accounts=mfs_accounts
    )
@app.route('/add_loan_without_expense', methods=['POST'])
@login_required
def add_loan_without_expense():
    # Get loan details
    lender_name = request.form.get('lender_name')
    loan_amount = float(request.form.get('loan_amount'))
    return_date = datetime.strptime(request.form.get('return_date'), '%Y-%m-%d').date()
    loan_notes = request.form.get('loan_notes', '')
    account_type = request.form.get('account_type')
    
    try:
        # Create transaction for the loan amount (income)
        timestamp = datetime.now()
        
        # Handle different account types
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet:
                wallet = WalletBalance(user_id=current_user.id, balance=0)
                db.session.add(wallet)
            
            wallet.balance += loan_amount
            
            loan_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=loan_amount,
                description=f"Loan from {lender_name}",
                category="Loan",
                timestamp=timestamp,
                source_type='wallet'
            )
            
        elif account_type == 'bank':
            bank_name = request.form.get('bank_name')
            bank_acc_no = request.form.get('bank_acc_no')
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash('Bank account not found', 'error')
                return redirect(url_for('loans'))
            
            bank.balance += loan_amount
            
            loan_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=loan_amount,
                description=f"Loan from {lender_name}",
                category="Loan",
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
        elif account_type == 'mfs':
            mfs_name = request.form.get('mfs_name')
            mfs_acc_no = request.form.get('mfs_acc_no')
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash('MFS account not found', 'error')
                return redirect(url_for('loans'))
            
            mfs.balance += loan_amount
            
            loan_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=loan_amount,
                description=f"Loan from {lender_name}",
                category="Loan",
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
        
        db.session.add(loan_transaction)
        db.session.flush()
        
        # Create the loan record
        loan = Loan(
            user_id=current_user.id,
            lender_name=lender_name,
            amount=loan_amount,
            remaining_amount=loan_amount,
            date_taken=timestamp,
            return_date=return_date,
            notes=loan_notes
        )
        
        db.session.add(loan)
        db.session.commit()
        
        flash('Loan added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding loan: {str(e)}', 'error')
    
    return redirect(url_for('loans'))

@app.route('/repay_loan', methods=['POST'])
@login_required
def repay_loan():
    loan_id = request.form.get('loan_id')
    amount = float(request.form.get('amount'))
    account_type = request.form.get('account_type')
    notes = request.form.get('notes', '')
    
    # Find the loan
    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first()
    
    if not loan:
        flash('Loan not found', 'error')
        return redirect(url_for('loans'))
    
    if amount > loan.remaining_amount:
        flash('Repayment amount cannot exceed the remaining loan amount', 'error')
        return redirect(url_for('loans'))
    
    try:
        # Create expense transaction for the repayment
        timestamp = datetime.now()
        
        # Handle different account types
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet or wallet.balance < amount:
                flash('Insufficient funds in your wallet', 'error')
                return redirect(url_for('loans'))
            
            wallet.balance -= amount
            
            repayment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Loan repayment to {loan.lender_name}",
                category="Loan Repayment",
                timestamp=timestamp,
                source_type='wallet'
            )
            
        elif account_type == 'bank':
            bank_name = request.form.get('bank_name')
            bank_acc_no = request.form.get('bank_acc_no')
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash('Bank account not found', 'error')
                return redirect(url_for('loans'))
                
            if bank.balance < amount:
                flash('Insufficient funds in your bank account', 'error')
                return redirect(url_for('loans'))
                
            bank.balance -= amount
            
            repayment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Loan repayment to {loan.lender_name}",
                category="Loan Repayment",
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
        elif account_type == 'mfs':
            mfs_name = request.form.get('mfs_name')
            mfs_acc_no = request.form.get('mfs_acc_no')
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash('MFS account not found', 'error')
                return redirect(url_for('loans'))
                
            if mfs.balance < amount:
                flash('Insufficient funds in your MFS account', 'error')
                return redirect(url_for('loans'))
                
            mfs.balance -= amount
            
            repayment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Loan repayment to {loan.lender_name}",
                category="Loan Repayment",
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
        
        db.session.add(repayment_transaction)
        
        # Create loan repayment record
        repayment = LoanRepayment(
            loan_id=loan.id,
            amount=amount,
            date=timestamp,
            notes=notes
        )
        
        db.session.add(repayment)
        
        # Update loan remaining amount
        loan.remaining_amount -= amount
        
        # Check if loan is fully repaid
        if loan.remaining_amount <= 0:
            loan.is_repaid = True
            loan.remaining_amount = 0  # Ensure no negative values
        
        db.session.commit()
        
        flash('Loan repayment recorded successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing repayment: {str(e)}', 'error')
    
    return redirect(url_for('loans'))

@app.route('/loan_details/<int:loan_id>')
@login_required
def loan_details(loan_id):
    # Find the loan
    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get all repayments for this loan
    repayments = LoanRepayment.query.filter_by(loan_id=loan_id).order_by(LoanRepayment.date.desc()).all()
    
    # Get original expense transaction if available
    expense_transaction = None
    if loan.expense_transaction_id:
        expense_transaction = Transaction.query.filter_by(id=loan.expense_transaction_id).first()
    
    return render_template(
        'loan_details_partial.html',
        loan=loan,
        repayments=repayments,
        expense_transaction=expense_transaction,
        total_repaid=sum(repayment.amount for repayment in repayments)
    )

@app.route('/create_loan_for_expense', methods=['POST'])
@login_required
def create_loan_for_expense():
    # Get loan details
    lender_name = request.form.get('lender_name')
    loan_amount = float(request.form.get('loan_amount'))
    return_date = datetime.strptime(request.form.get('return_date'), '%Y-%m-%d').date()
    loan_notes = request.form.get('loan_notes', '')
    
    # Get expense details - use more flexible field naming to handle both formats
    account_type = request.form.get('expense_account_type')
    
    # Fix for "Cash" account type - map it to "wallet"
    if account_type == 'Cash':
        account_type = 'wallet'
        
    expense_amount = float(request.form.get('expense_amount'))
    category = request.form.get('expense_category')
    date_str = request.form.get('expense_date')
    description = request.form.get('expense_description', '')
    
    # Validate account type
    if account_type not in ['wallet', 'bank', 'mfs']:
        flash(f'Invalid account type: {account_type}', 'error')
        return redirect(url_for('dashboard'))
    
    # Convert date string to datetime
    if date_str:
        timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()
    
    # Start a database transaction
    try:
        transaction = None  # Initialize transaction variable to avoid reference error
        
        # Handle different account types
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet:
                wallet = WalletBalance(user_id=current_user.id, balance=0)
                db.session.add(wallet)
            
            # Add loan amount to balance
            wallet.balance += loan_amount
            
            # Create expense transaction
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='wallet'
            )
            
            # Subtract expense amount
            wallet.balance -= expense_amount
        elif account_type == 'bank':
            # Try to get bank details - check both possible field names
            bank_name = request.form.get('expense_bank_name') or request.form.get('loan_bank_name') or request.form.get('bank_name')
            bank_acc_no = request.form.get('expense_bank_acc_no') or request.form.get('loan_bank_acc_no') or request.form.get('bank_acc_no')
            
            if not bank_name or not bank_acc_no:
                flash('Bank account details missing', 'error')
                return redirect(url_for('dashboard'))
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash(f'Bank account not found: {bank_name} / {bank_acc_no}', 'error')
                return redirect(url_for('dashboard'))
            
            # Add loan amount to balance
            bank.balance += loan_amount
            
            # Create expense transaction
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
            # Subtract expense amount
            bank.balance -= expense_amount
            
        elif account_type == 'mfs':
            # Try to get MFS details - check both possible field names
            mfs_name = request.form.get('expense_mfs_name') or request.form.get('loan_mfs_name') or request.form.get('mfs_name')
            mfs_acc_no = request.form.get('expense_mfs_acc_no') or request.form.get('loan_mfs_acc_no') or request.form.get('mfs_acc_no')
            
            if not mfs_name or not mfs_acc_no:
                flash('MFS account details missing', 'error')
                return redirect(url_for('dashboard'))
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash(f'MFS account not found: {mfs_name} / {mfs_acc_no}', 'error')
                return redirect(url_for('dashboard'))
            
            # Add loan amount to balance
            mfs.balance += loan_amount
            
            # Create expense transaction
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
            
            # Subtract expense amount
            mfs.balance -= expense_amount
        
        # Make sure transaction is not None
        if transaction is None:
            raise ValueError(f"Failed to create transaction for account type: {account_type}")
            
        db.session.add(transaction)
        db.session.flush()  # Get transaction ID
        
        # Rest of the function remains the same...
        # Create loan income transaction with the same modifications for source details
        loan_transaction = Transaction(
            user_id=current_user.id,
            transaction_type='income',
            amount=loan_amount,
            description=f"Loan from {lender_name}",
            category="Loan",
            timestamp=timestamp,
            source_type=account_type
        )
        
        # Set appropriate source details
        if account_type == 'bank':
            loan_transaction.source_bank_name = bank_name
            loan_transaction.source_account_number = bank_acc_no
        elif account_type == 'mfs':
            loan_transaction.source_mfs_name = mfs_name
            loan_transaction.source_mfs_number = mfs_acc_no
        
        db.session.add(loan_transaction)
        
        # Create loan record
        loan = Loan(
            user_id=current_user.id,
            lender_name=lender_name,
            amount=loan_amount,
            remaining_amount=loan_amount,
            date_taken=timestamp,
            return_date=return_date,
            notes=loan_notes,
            expense_transaction_id=transaction.id
        )
        
        db.session.add(loan)
        db.session.commit()
        
        flash('Expense recorded and loan added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing loan and expense: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/add_loan', methods=['POST'])
@login_required
def add_loan():
    # Get loan details
    lender_name = request.form.get('lender_name')
    loan_amount = float(request.form.get('loan_amount'))
    return_date = datetime.strptime(request.form.get('return_date'), '%Y-%m-%d').date()
    loan_notes = request.form.get('loan_notes', '')
    
    # Get expense details
    account_type = request.form.get('expense_account_type')
    expense_amount = float(request.form.get('expense_amount'))
    category = request.form.get('expense_category')
    date_str = request.form.get('expense_date')
    description = request.form.get('expense_description', '')
    
    if account_type not in ['wallet', 'bank', 'mfs']:
        flash('Invalid account type selected', 'error')
        return redirect(url_for('dashboard'))

    # Convert date string to datetime
    if date_str:
        timestamp = datetime.strptime(f"{date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()
    
    # Start a database transaction
    try:
        transaction= None
        # 1. Create expense transaction
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet:
                wallet = WalletBalance(user_id=current_user.id, balance=0)
                db.session.add(wallet)
            
            # Add the loan amount to wallet
            wallet.balance += loan_amount
            
            # Then deduct the expense
            wallet.balance -= expense_amount
            
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='wallet'
            )
            
        elif account_type == 'bank':
            bank_name = request.form.get('bank_name')
            bank_acc_no = request.form.get('bank_acc_no')
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash('Bank account not found', 'error')
                return redirect(url_for('dashboard'))
            
            # Add the loan amount to bank account
            bank.balance += loan_amount
            
            # Then deduct the expense
            bank.balance -= expense_amount
            
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
        elif account_type == 'mfs':
            mfs_name = request.form.get('mfs_name')
            mfs_acc_no = request.form.get('mfs_acc_no')
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash('MFS account not found', 'error')
                return redirect(url_for('dashboard'))
            
            # Add the loan amount to MFS account
            mfs.balance += loan_amount
            
            # Then deduct the expense
            mfs.balance -= expense_amount
            
            transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=expense_amount,
                category=category,
                description=description,
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
        if transaction is None:
            raise ValueError(f"Failed to create transaction for account type: {account_type}")
            
        db.session.add(transaction)
        db.session.flush()  # Get the transaction ID
        
        # 2. Create a transaction for the loan (income)
        loan_transaction = Transaction(
            user_id=current_user.id,
            transaction_type='income',
            amount=loan_amount,
            description=f"Loan from {lender_name}",
            category="Loan",
            timestamp=timestamp,
            source_type=account_type
        )
        
        # Set the appropriate source details based on account type
        if account_type == 'bank':
            loan_transaction.source_bank_name = request.form.get('bank_name')
            loan_transaction.source_account_number = request.form.get('bank_acc_no')
        elif account_type == 'mfs':
            loan_transaction.source_mfs_name = request.form.get('mfs_name')
            loan_transaction.source_mfs_number = request.form.get('mfs_acc_no')
        
        db.session.add(loan_transaction)
        
        # 3. Create the loan record
        loan = Loan(
            user_id=current_user.id,
            lender_name=lender_name,
            amount=loan_amount,
            remaining_amount=loan_amount,
            date_taken=timestamp,
            return_date=return_date,
            notes=loan_notes,
            expense_transaction_id=transaction.id
        )
        
        db.session.add(loan)
        db.session.commit()
        
        flash('Expense recorded and loan added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing loan and expense: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
   
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        if len(email)<1 or len(message)<1:
            flash('No email/message given','error')
            return redirect(url_for('contact'))

        new_contact = Contact(name=name, email=email, message=message)
        db.session.add(new_contact)
        db.session.commit()
        
        flash('Your message has been sent successfully', 'success')
        return redirect(url_for('contact'))
    if current_user.is_authenticated:
        user_details = UserDetails.query.filter_by(user_id=current_user.id).first()
        user_email = User.query.filter_by(id=current_user.id).first().email
        return render_template('contact.html',user_details=user_details,user_email=user_email)
    
    else:
        return render_template('contact.html')
    
@app.route('/receivables')
@login_required
def receivables():
    # Get all receivables for the current user
    active_receivables = Receivable.query.filter_by(
        user_id=current_user.id,
        is_received=False
    ).order_by(Receivable.expected_return_date).all()
    
    received_receivables = Receivable.query.filter_by(
        user_id=current_user.id,
        is_received=True
    ).order_by(Receivable.date_lent.desc()).all()
    
    # Get wallet, bank, and MFS accounts for payment receiving
    wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
    bank_accounts = BankBalance.query.filter_by(user_id=current_user.id).all()
    mfs_accounts = MFSBalance.query.filter_by(user_id=current_user.id).all()
    
    # Calculate totals
    total_active_amount = sum(receivable.remaining_amount for receivable in active_receivables) if active_receivables else 0
    total_received_amount = sum(receivable.amount for receivable in received_receivables) if received_receivables else 0
    
    # Calculate receivables due soon and overdue
    today = date.today()
    due_soon_amount = sum(receivable.remaining_amount for receivable in active_receivables 
                         if receivable.expected_return_date and 0 < (receivable.expected_return_date - today).days <= 7)
    overdue_amount = sum(receivable.remaining_amount for receivable in active_receivables 
                        if receivable.expected_return_date and (receivable.expected_return_date - today).days <= 0)
    
    # Get unique debtor names for autocomplete
    existing_debtors = db.session.query(Receivable.debtor_name).filter_by(
        user_id=current_user.id
    ).distinct().all()
    existing_debtors = [debtor[0] for debtor in existing_debtors]  # Extract strings from tuples
    
    return render_template(
        'receivables.html',
        active_receivables=active_receivables,
        received_receivables=received_receivables,
        today=today,
        total_receivables=total_active_amount,
        due_soon=due_soon_amount,
        overdue=overdue_amount,
        total_active_amount=total_active_amount,
        total_received_amount=total_received_amount,
        wallet=wallet,
        bank_accounts=bank_accounts,
        mfs_accounts=mfs_accounts,
        existing_debtors=existing_debtors
    )

@app.route('/add_receivable', methods=['POST'])
@login_required
def add_receivable():
    # Get receivable details
    debtor_name = request.form.get('debtor_name')
    amount = float(request.form.get('amount'))
    expected_return_date_str = request.form.get('expected_return_date')
    date_lent_str = request.form.get('date_lent')  # Get the date lent from form
    notes = request.form.get('notes', '')
    interest_rate = float(request.form.get('interest_rate', 0))
    account_type = request.form.get('account_type')
    
    # Convert date string to date object
    expected_return_date = None
    if expected_return_date_str:
        expected_return_date = datetime.strptime(expected_return_date_str, '%Y-%m-%d').date()
    
    # Convert date lent string to datetime object
    if date_lent_str:
        date_lent = datetime.strptime(f"{date_lent_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
        # Use the date_lent for transaction timestamp as well
        timestamp = date_lent
    else:
        date_lent = datetime.now()  # Use current time if no date specified
        timestamp = date_lent
    
    try:
        # Create expense transaction (money going out)
        # Use the date_lent for the transaction timestamp
        
        # Handle different account types
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet or wallet.balance < amount:
                flash('Insufficient funds in your wallet', 'error')
                return redirect(url_for('receivables'))
            
            wallet.balance -= amount
            
            expense_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Lent money to {debtor_name}",
                category="Receivable",
                timestamp=timestamp,
                source_type='wallet'
            )
            
        elif account_type == 'bank':
            bank_name = request.form.get('bank_name')
            bank_acc_no = request.form.get('bank_acc_no')
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash('Bank account not found', 'error')
                return redirect(url_for('receivables'))
                
            if bank.balance < amount:
                flash('Insufficient funds in your bank account', 'error')
                return redirect(url_for('receivables'))
                
            bank.balance -= amount
            
            expense_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Lent money to {debtor_name}",
                category="Receivable",
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
        elif account_type == 'mfs':
            mfs_name = request.form.get('mfs_name')
            mfs_acc_no = request.form.get('mfs_acc_no')
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash('MFS account not found', 'error')
                return redirect(url_for('receivables'))
                
            if mfs.balance < amount:
                flash('Insufficient funds in your MFS account', 'error')
                return redirect(url_for('receivables'))
                
            mfs.balance -= amount
            
            expense_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='expense',
                amount=amount,
                description=f"Lent money to {debtor_name}",
                category="Receivable",
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
        
        db.session.add(expense_transaction)
        db.session.flush()
        
        # Create the receivable record
        receivable = Receivable(
            user_id=current_user.id,
            debtor_name=debtor_name,
            amount=amount,
            remaining_amount=amount,
            date_lent=date_lent,  # Use the date_lent input from user
            expected_return_date=expected_return_date,
            notes=notes,
            interest_rate=interest_rate,
            expense_transaction_id=expense_transaction.id
        )
        
        db.session.add(receivable)
        db.session.commit()
        
        flash('Receivable added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding receivable: {str(e)}', 'error')
    
    return redirect(url_for('receivables'))

@app.route('/receive_payment', methods=['POST'])
@login_required
def receive_payment():
    receivable_id = request.form.get('receivable_id')
    amount = float(request.form.get('amount'))
    account_type = request.form.get('account_type')
    notes = request.form.get('notes', '')
    payment_date_str = request.form.get('payment_date')  # Get payment date from form
    
    # Convert payment date string to datetime object
    if payment_date_str:
        timestamp = datetime.strptime(f"{payment_date_str} 12:00:00", '%Y-%m-%d %H:%M:%S')
    else:
        timestamp = datetime.now()  # Use current time if no date specified
    
    # Find the receivable
    receivable = Receivable.query.filter_by(
        id=receivable_id,
        user_id=current_user.id
    ).first()
    
    if not receivable:
        flash('Receivable not found', 'error')
        return redirect(url_for('receivables'))
    
    if amount > receivable.remaining_amount:
        flash('Payment amount cannot exceed the remaining receivable amount', 'error')
        return redirect(url_for('receivables'))
    
    try:
        # Create income transaction for the payment (using the date you specify)
        
        # Handle different account types
        if account_type == 'wallet':
            wallet = WalletBalance.query.filter_by(user_id=current_user.id).first()
            if not wallet:
                wallet = WalletBalance(user_id=current_user.id, balance=0)
                db.session.add(wallet)
            
            wallet.balance += amount
            
            payment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=amount,
                description=f"Payment received from {receivable.debtor_name}",
                category="Receivable Payment",
                timestamp=timestamp,
                source_type='wallet'
            )
            
            # Create payment record
            payment = ReceivablePayment(
                receivable_id=receivable.id,
                amount=amount,
                date=timestamp,
                notes=notes,
                received_to_type='wallet'
            )
            
        elif account_type == 'bank':
            bank_name = request.form.get('bank_name')
            bank_acc_no = request.form.get('bank_acc_no')
            
            bank = BankBalance.query.filter_by(
                user_id=current_user.id,
                bank_name=bank_name,
                account_number=bank_acc_no
            ).first()
            
            if not bank:
                flash('Bank account not found', 'error')
                return redirect(url_for('receivables'))
                
            bank.balance += amount
            
            payment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=amount,
                description=f"Payment received from {receivable.debtor_name}",
                category="Receivable Payment",
                timestamp=timestamp,
                source_type='bank',
                source_bank_name=bank_name,
                source_account_number=bank_acc_no
            )
            
            # Create payment record
            payment = ReceivablePayment(
                receivable_id=receivable.id,
                amount=amount,
                date=timestamp,
                notes=notes,
                received_to_type='bank',
                received_to_bank_name=bank_name,
                received_to_account_number=bank_acc_no
            )
            
        elif account_type == 'mfs':
            mfs_name = request.form.get('mfs_name')
            mfs_acc_no = request.form.get('mfs_acc_no')
            
            mfs = MFSBalance.query.filter_by(
                user_id=current_user.id,
                mfs_name=mfs_name,
                account_no=mfs_acc_no
            ).first()
            
            if not mfs:
                flash('MFS account not found', 'error')
                return redirect(url_for('receivables'))
                
            mfs.balance += amount
            
            payment_transaction = Transaction(
                user_id=current_user.id,
                transaction_type='income',
                amount=amount,
                description=f"Payment received from {receivable.debtor_name}",
                category="Receivable Payment",
                timestamp=timestamp,
                source_type='mfs',
                source_mfs_name=mfs_name,
                source_mfs_number=mfs_acc_no
            )
            
            # Create payment record
            payment = ReceivablePayment(
                receivable_id=receivable.id,
                amount=amount,
                date=timestamp,
                notes=notes,
                received_to_type='mfs',
                received_to_mfs_name=mfs_name,
                received_to_mfs_number=mfs_acc_no
            )
        
        db.session.add(payment_transaction)
        db.session.add(payment)
        
        # Update receivable remaining amount
        receivable.remaining_amount -= amount
        
        # Check if receivable is fully received
        if receivable.remaining_amount <= 0:
            receivable.is_received = True
            receivable.remaining_amount = 0  # Ensure no negative values
        
        db.session.commit()
        
        flash('Payment received successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing payment: {str(e)}', 'error')
    
    return redirect(url_for('receivables'))

@app.route('/receivable_details/<int:receivable_id>')
@login_required
def receivable_details(receivable_id):
    # Find the receivable
    receivable = Receivable.query.filter_by(
        id=receivable_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get all payments for this receivable
    payments = ReceivablePayment.query.filter_by(receivable_id=receivable_id).order_by(ReceivablePayment.date.desc()).all()
    
    # Get original expense transaction if available
    expense_transaction = None
    if receivable.expense_transaction_id:
        expense_transaction = Transaction.query.filter_by(id=receivable.expense_transaction_id).first()
    
    return render_template(
        'receivable_details_partial.html',
        receivable=receivable,
        payments=payments,
        expense_transaction=expense_transaction,
        total_received=sum(payment.amount for payment in payments)
    )

@app.route('/api/receivable_details/<int:receivable_id>')
@login_required
def api_receivable_details(receivable_id):
    # Find the receivable
    receivable = Receivable.query.filter_by(
        id=receivable_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get all payments for this receivable
    payments = ReceivablePayment.query.filter_by(receivable_id=receivable_id).order_by(ReceivablePayment.date.desc()).all()
    
    # Determine status
    today = date.today()
    if receivable.is_received:
        status = "Received"
    elif receivable.expected_return_date and receivable.expected_return_date < today:
        status = "Overdue"
    elif receivable.expected_return_date and (receivable.expected_return_date - today).days <= 7:
        status = "Due Soon"
    else:
        status = "Active"
    
    # Format payment data
    payment_data = []
    for payment in payments:
        payment_data.append({
            'date': payment.date.strftime('%Y-%m-%d'),
            'amount': float(payment.amount),
            'notes': payment.notes
        })
    
    return jsonify({
        'debtor_name': receivable.debtor_name,
        'amount': float(receivable.amount),
        'remaining_amount': float(receivable.remaining_amount),
        'date_lent': receivable.date_lent.strftime('%Y-%m-%d'),
        'expected_return_date': receivable.expected_return_date.strftime('%Y-%m-%d') if receivable.expected_return_date else None,
        'interest_rate': float(receivable.interest_rate) if receivable.interest_rate else 0,
        'notes': receivable.notes,
        'status': status,
        'payments': payment_data
    })

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Please enter your email address', 'error')
            return redirect(url_for('forgot_password'))
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate secure token
            token = generate_reset_token(user.email)
            
            # Send reset email
            try:
                send_reset_email(user, token)
                flash('Password reset instructions have been sent to your email', 'success')
            except Exception as e:
                flash('Error sending email. Please try again later.', 'error')
                app.logger.error(f"Failed to send reset email: {str(e)}")
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, password reset instructions have been sent', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Verify the reset token
    email = verify_reset_token(token)
    
    if not email:
        flash('Invalid or expired reset link', 'error')
        return redirect(url_for('forgot_password'))
    
    # Find the user
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid reset link', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not new_password or not confirm_password:
            flash('Please fill in all fields', 'error')
            return render_template('reset_password.html', token=token)
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('reset_password.html', token=token)
        
        # Additional password strength validation
        if (not any(char.islower() for char in new_password) or
            not any(char.isupper() for char in new_password) or
            not any(char.isdigit() for char in new_password) or
            not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?/' for char in new_password)):
            flash('Password must contain at least one lowercase letter, one uppercase letter, one number, and one special character', 'error')
            return render_template('reset_password.html', token=token)
        
        # Update user password
        user.password = generate_password_hash(new_password, method='sha256')
        db.session.commit()
        
        flash('Your password has been successfully reset. You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)

def send_reset_email(user, token):
    """Send password reset email"""
    try:
        reset_url = url_for('reset_password', token=token, _external=True)
        
        msg = Message(
            'Password Reset Request - WalletHub',
            recipients=[user.email]
        )
        
        msg.html = f'''
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">
                <div style="background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h2 style="color: #2c3e50; margin-bottom: 20px;">Password Reset Request</h2>
                    
                    <p>Hello <strong>{user.username}</strong>,</p>
                    
                    <p>We received a request to reset your password for your WalletHub account. If you didn't make this request, you can safely ignore this email.</p>
                    
                    <p>To reset your password, click the button below:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" 
                        style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            Reset My Password
                        </a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
                        {reset_url}
                    </p>
                    
                    <p style="margin-top: 30px; font-size: 14px; color: #7f8c8d;">
                        <strong>Important:</strong> This link will expire in 30 minutes for security reasons.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    
                    <p style="font-size: 12px; color: #95a5a6;">
                        If you're having trouble clicking the button, copy and paste the URL above into your web browser.
                        <br><br>
                        This is an automated email, please do not reply to this message.
                        <br><br>
                        Best regards,<br>
                        The WalletHub Team
                    </p>
                </div>
            </div>
        </body>
        </html>
        '''
        print(f"Attempting to send email to: {user.email}")
        mail.send(msg)
        print("Email sent successfully!")

    except Exception as e:
        print(f"Detailed email error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        raise e  # Re-raise the exception so it can be caught by the calling function

@app.route('/test_email')
def test_email():
    try:
        msg = Message(
            'Test Email - WalletHub',
            recipients=['ajlan_alif@stud.cou.ac.bd']  # Send to yourself for testing
        )
        msg.body = 'This is a test email to verify the email configuration is working.'
        mail.send(msg)
        return "Test email sent successfully!"
    except Exception as e:
        return f"Email test failed: {str(e)}"

@app.route('/generate_monthly_pdf')
@login_required
def generate_monthly_pdf():
    # Get the requested month and year, default to current month
    current_date = date.today()
    year = request.args.get('year', current_date.year, type=int)
    month = request.args.get('month', current_date.month, type=int)
    
    # Create date range for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    month_name = start_date.strftime('%B %Y')
    
    # Create a BytesIO buffer to hold the PDF
    buffer = BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=1*inch
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.darkblue,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.darkgreen,
        spaceAfter=20,
        spaceBefore=10
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Title
    user_details = UserDetails.query.filter_by(user_id=current_user.id).first()
    user_name = f"{user_details.first_name} {user_details.last_name}" if user_details else current_user.username
    
    title = Paragraph(f"Financial Report - {month_name}<br/>{user_name}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    # PAGE 1: INCOME SUMMARY
    elements.append(Paragraph("Income Summary", heading_style))
    
    # Get income transactions for the month
    income_transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type == 'income',
        func.date(Transaction.timestamp) >= start_date,
        func.date(Transaction.timestamp) <= end_date
    ).order_by(Transaction.source_type, Transaction.timestamp).all()
    
    if income_transactions:
        # Group by source_type
        income_data = {}
        total_income = 0
        
        for transaction in income_transactions:
            account_name = get_account_display_name(transaction, 'source')
            if account_name not in income_data:
                income_data[account_name] = []
            
            income_data[account_name].append({
                'amount': transaction.amount,
                'category': transaction.category or 'Uncategorized',
                'date': transaction.timestamp.strftime('%Y-%m-%d')
            })
            total_income += transaction.amount
        
        # Create income table
        income_table_data = [['Account', 'Date', 'Source', 'Amount (৳)']]
        
        for account_name, transactions in income_data.items():
            for trans in transactions:
                income_table_data.append([
                    account_name,
                    trans['date'],
                    trans['category'],
                    f"{trans['amount']:.2f}"
                ])
        
        # Add total row
        income_table_data.append(['', '', 'TOTAL INCOME', f"{total_income:.2f}"])
        
        income_table = Table(income_table_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        income_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgreen),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ]))
        
        elements.append(income_table)
    else:
        elements.append(Paragraph("No income transactions found for this period.", styles['Normal']))
    
    # PAGE BREAK
    elements.append(PageBreak())
    
    # PAGE 2: EXPENSE SUMMARY
    elements.append(Paragraph("Expense Summary", heading_style))
    
    # Get expense transactions for the month
    expense_transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.transaction_type == 'expense',
        func.date(Transaction.timestamp) >= start_date,
        func.date(Transaction.timestamp) <= end_date
    ).order_by(Transaction.source_type, Transaction.timestamp).all()
    
    if expense_transactions:
        # Group by source_type
        expense_data = {}
        total_expense = 0
        
        for transaction in expense_transactions:
            account_name = get_account_display_name(transaction, 'source')
            if account_name not in expense_data:
                expense_data[account_name] = []
            
            expense_data[account_name].append({
                'amount': transaction.amount,
                'category': transaction.category or 'Uncategorized',
                'date': transaction.timestamp.strftime('%Y-%m-%d')
            })
            total_expense += transaction.amount
        
        # Create expense table
        expense_table_data = [['Account', 'Date', 'Category', 'Amount (৳)']]
        
        for account_name, transactions in expense_data.items():
            for trans in transactions:
                expense_table_data.append([
                    account_name,
                    trans['date'],
                    trans['category'],
                    f"{trans['amount']:.2f}"
                ])
        
        # Add total row
        expense_table_data.append(['', '', 'TOTAL EXPENSE', f"{total_expense:.2f}"])
        
        expense_table = Table(expense_table_data, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightcoral),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ]))
        
        elements.append(expense_table)
    else:
        elements.append(Paragraph("No expense transactions found for this period.", styles['Normal']))
    
    # PAGE BREAK
    elements.append(PageBreak())
    
    # PAGE 3: RECEIVABLES SUMMARY
    elements.append(Paragraph("Receivables Summary", heading_style))
    
    # Get receivables that were created in this month or have payments in this month
    receivables = Receivable.query.filter(
        Receivable.user_id == current_user.id,
        db.or_(
            func.date(Receivable.date_lent) >= start_date,
            func.date(Receivable.date_lent) <= end_date
        )
    ).order_by(Receivable.date_lent).all()
    
    if receivables:
        receivable_table_data = [['Account', 'Amount (৳)', 'Debtor Name', 'Return Date', 'Status']]
        total_receivables = 0
        
        for receivable in receivables:
            # Get account info from the related expense transaction
            account_name = 'Unknown'
            if receivable.expense_transaction_id:
                expense_trans = Transaction.query.get(receivable.expense_transaction_id)
                if expense_trans:
                    account_name = get_account_display_name(expense_trans, 'source')
            
            status = 'Received' if receivable.is_received else 'Pending'
            return_date = receivable.expected_return_date.strftime('%Y-%m-%d') if receivable.expected_return_date else 'Not Set'
            
            receivable_table_data.append([
                account_name,
                f"{receivable.amount:.2f}",
                receivable.debtor_name,
                return_date,
                status
            ])
            total_receivables += receivable.amount
        
        # Add total row
        receivable_table_data.append(['', f"{total_receivables:.2f}", 'TOTAL RECEIVABLES', '', ''])
        
        receivable_table = Table(receivable_table_data, colWidths=[1.5*inch, 1.3*inch, 1.8*inch, 1.3*inch, 1.1*inch])
        receivable_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightyellow),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ]))
        
        elements.append(receivable_table)
    else:
        elements.append(Paragraph("No receivables found for this period.", styles['Normal']))
    
    # PAGE BREAK
    elements.append(PageBreak())
    
    # PAGE 4: LOANS SUMMARY
    elements.append(Paragraph("Loans Summary", heading_style))
    
    # Get loans that were taken in this month
    loans = Loan.query.filter(
        Loan.user_id == current_user.id,
        func.date(Loan.date_taken) >= start_date,
        func.date(Loan.date_taken) <= end_date
    ).order_by(Loan.date_taken).all()
    
    if loans:
        loan_table_data = [['Account', 'Amount (৳)', 'Lender Name', 'Return Date', 'Status']]
        total_loans = 0
        
        for loan in loans:
            # Find the income transaction for this loan
            account_name = 'Unknown'
            income_trans = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                Transaction.transaction_type == 'income',
                Transaction.category == 'Loan',
                Transaction.description.contains(loan.lender_name)
            ).first()
            
            if income_trans:
                account_name = get_account_display_name(income_trans, 'source')
            
            status = 'Repaid' if loan.is_repaid else 'Active'
            return_date = loan.return_date.strftime('%Y-%m-%d')
            
            loan_table_data.append([
                account_name,
                f"{loan.amount:.2f}",
                loan.lender_name,
                return_date,
                status
            ])
            total_loans += loan.amount
        
        # Add total row
        loan_table_data.append(['', f"{total_loans:.2f}", 'TOTAL LOANS', '', ''])
        
        loan_table = Table(loan_table_data, colWidths=[1.5*inch, 1.3*inch, 1.8*inch, 1.3*inch, 1.1*inch])
        loan_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkviolet),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lavender),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ]))
        
        elements.append(loan_table)
    else:
        elements.append(Paragraph("No loans found for this period.", styles['Normal']))
    
    # Add summary footer
    elements.append(Spacer(1, 30))
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    
    summary_text = f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>WalletHub Financial Management System"
    elements.append(Paragraph(summary_text, summary_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and return it as response
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create response
    response = app.response_class(
        pdf,
        mimetype='application/pdf'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=financial_report_{month_name.replace(" ", "_")}.pdf'
    
    return response

def get_account_display_name(transaction, account_type):
    """Helper function to get display name for accounts"""
    if account_type == 'source':
        if transaction.source_type == 'wallet':
            return 'Cash Wallet'
        elif transaction.source_type == 'bank':
            return f"{transaction.source_bank_name} - {transaction.source_account_number}"
        elif transaction.source_type == 'mfs':
            return f"{transaction.source_mfs_name} - {transaction.source_mfs_number}"
    elif account_type == 'destination':
        if transaction.destination_type == 'wallet':
            return 'Cash Wallet'
        elif transaction.destination_type == 'bank':
            return f"{transaction.destination_bank_name} - {transaction.destination_account_number}"
        elif transaction.destination_type == 'mfs':
            return f"{transaction.destination_mfs_name} - {transaction.destination_mfs_number}"
    
    return 'Unknown Account'

@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
    try:
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        amount = float(request.form.get('amount'))
        
        if amount <= 0:
            flash('Budget amount must be greater than 0', 'error')
            return redirect(url_for('dashboard'))
        
        # Check if budget already exists for this month/year
        existing_budget = Budget.query.filter_by(
            user_id=current_user.id,
            month=month,
            year=year
        ).first()
        
        if existing_budget:
            # Update existing budget
            existing_budget.amount = amount
            existing_budget.updated_at = datetime.utcnow()
            flash(f'Budget for {date(year, month, 1).strftime("%B %Y")} updated successfully!', 'success')
        else:
            # Create new budget
            new_budget = Budget(
                user_id=current_user.id,
                month=month,
                year=year,
                amount=amount
            )
            db.session.add(new_budget)
            flash(f'Budget for {date(year, month, 1).strftime("%B %Y")} set successfully!', 'success')
        
        db.session.commit()
        
    except ValueError:
        flash('Invalid budget amount', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Error setting budget. Please try again.', 'error')
        app.logger.error(f"Budget setting error: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/get_budget/<int:month>/<int:year>')
@login_required
def get_budget(month, year):
    budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=month,
        year=year
    ).first()
    
    return jsonify({
        'exists': budget is not None,
        'amount': budget.amount if budget else 0
    })

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=3000)

