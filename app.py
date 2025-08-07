from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from datetime import date, datetime, timedelta
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/wh'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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
            file_ext = photo.filename.rsplit('.', 1)[1].lower()
            filename = f"{current_user.username}.{file_ext}"
            photo.save(os.path.join('static','uploads', filename))
            photo_path = 'static/uploads/' + filename
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

    return render_template('dashboard.html', 
                         total_balance=total_balance,
                         bank_balance=bank_balance, 
                         mfs_balance=mfs_balance, 
                         wallet_balance=wallet_balance_amount,
                         bank_accounts=bank_balances,
                         mfs_accounts=mfs_balances,
                         today_date=date.today().strftime('%Y-%m-%d'),
                         active_loans=active_loans,
                         active_loans_amount=active_loans_amount,
                         due_soon_loans=due_soon_loans)

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
    mfs_balance = sum(mfs.balance for mfs in mfs_accounts)
    
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
    total_income = sum(income.amount for income in incomes)
    total_expense = sum(expense.amount for expense in expenses)
    net_amount = total_income - total_expense
    
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
    

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=3000)

