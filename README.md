# WalletHub - Personal Finance Management System

![WalletHub Logo](static/DALL·E%202024-12-07%2016.53.09%20-%20A%20sleek%20and%20modern%20logo%20design%20for%20'WalletHub',%20incorporating%20the%20colors%20black,%20green,%20and%20light%20violet.%20The%20design%20features%20a%20stylized%20wallet%20icon%20co.webp)

WalletHub is a comprehensive personal finance management application that helps users track their finances across multiple accounts including banks, mobile financial services (MFS), and digital wallets. Built with Flask and MySQL, it provides a unified platform for managing all your financial activities.

## 🚀 Features

### Multi-Account Management

- **Bank Accounts**: Track multiple bank accounts with real-time balance updates
- **Mobile Financial Services (MFS)**: Manage mobile money accounts (bKash, Nagad, etc.)
- **Digital Wallet**: Monitor cash and digital wallet balances

### Transaction Management

- **Income Tracking**: Record income from various sources
- **Expense Monitoring**: Categorize and track all expenses
- **Inter-Account Transfers**: Move money between different accounts
- **Transaction History**: Comprehensive transaction logs with filtering options

### Loan Management

- **Loan Tracking**: Record loans taken and given
- **Repayment Scheduling**: Track loan repayments and due dates
- **Outstanding Balance**: Monitor remaining loan amounts

### Financial Analytics

- **Monthly Reports**: Visual charts showing income and expense patterns
- **Category Analysis**: Breakdown of spending by categories
- **PDF Reports**: Download monthly financial reports
- **Balance Insights**: Real-time overview of total financial position

### User Management

- **Secure Authentication**: Password hashing with SHA-256
- **Profile Management**: Update personal information and profile photos
- **Account Security**: Change passwords and delete accounts

## 🛠️ Technology Stack

- **Backend**: Flask (Python)
- **Database**: MySQL with SQLAlchemy ORM
- **Frontend**: HTML5, CSS3, JavaScript
- **Authentication**: Flask-Login
- **Charts**: Chart.js for data visualization
- **UI Components**: Select2 for enhanced dropdowns
- **File Uploads**: Image handling for profile photos

## 📋 Prerequisites

Before running this application, make sure you have the following installed:

- Python 3.7 or higher
- MySQL Server
- pip (Python package installer)

## 🔧 Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/WalletHub.git
   cd WalletHub
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up MySQL database**

   ```sql
   CREATE DATABASE wh;
   ```

5. **Configure database connection**
   Update the database URI in `app.py`:

   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/wh'
   ```

6. **Initialize the database**

   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

7. **Create upload directory**
   ```bash
   mkdir static/uploads
   ```

## 🚀 Running the Application

1. **Start the Flask development server**

   ```bash
   python app.py
   ```

2. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

## 📱 Usage

### Getting Started

1. **Sign Up**: Create a new account with username, email, and secure password
2. **Profile Setup**: Complete your profile with personal details and photo
3. **Account Setup**: Add your bank accounts, MFS accounts, and wallet balance
4. **Start Tracking**: Begin recording your financial transactions

### Managing Transactions

- **Income**: Record salary, business income, or other earnings
- **Expenses**: Track daily expenses with categories
- **Transfers**: Move money between your accounts
- **Loans**: Record loans and track repayments

### Financial Analysis

- **Dashboard**: Get an overview of all your accounts and balances
- **Monthly Tracker**: View detailed monthly financial reports
- **Transaction History**: Filter and search through your transaction history

## 🔐 Security Features

- **Password Security**: SHA-256 hashing for all passwords
- **Session Management**: Secure session handling with Flask-Login
- **Input Validation**: Protection against SQL injection and XSS
- **File Upload Security**: Validated file types and size limits
- **Account Isolation**: Users can only access their own data

## 📊 Database Schema

The application uses the following main database tables:

- `user`: User authentication and basic information
- `user_details`: Extended user profile information
- `bank_balance`: Bank account information and balances
- `mfs_balance`: Mobile Financial Services account data
- `wallet_balance`: Digital wallet balance
- `transaction`: All financial transactions
- `loan`: Loan information and tracking
- `loan_repayment`: Loan repayment records

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Known Issues

- No automatic bank API integration (manual entry required)
- Limited to MySQL database (PostgreSQL support planned)
- No mobile app (web-based only)

## 🚧 Future Enhancements

- [ ] Banking API integration for automatic transaction import
- [ ] Mobile application development
- [ ] Advanced budgeting tools
- [ ] Investment portfolio tracking
- [ ] Multi-currency support
- [ ] Recurring transaction automation
- [ ] Financial goal setting and tracking

## 📞 Support

If you encounter any issues or have questions, please:

1. Check the [Issues](https://github.com/yourusername/WalletHub/issues) page
2. Create a new issue if your problem isn't already listed
3. Provide detailed information about the issue including error messages and steps to reproduce

## 🙏 Acknowledgments

- Flask team for the excellent web framework
- Chart.js for beautiful data visualizations
- Select2 for enhanced UI components
- MySQL team for the reliable database system

---

**Made with ❤️ for better personal finance management**
