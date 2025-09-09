# DrugWeb - Online Pharmacy Management System

A complete web-based pharmacy management system built with Flask and MySQL.

## Features

### User Types
- **Customers**: Browse medicines, search, sort, add to cart, and place orders
- **Admin**: Manage medicine inventory, view statistics, and monitor stock levels
- **Delivery Personnel**: Manage deliveries and track performance

### Key Functionality
- User authentication and role-based access control
- Medicine catalog with search and sorting capabilities
- Inventory management system
- Customer registration with auto-generated IDs (CM001, CM002, etc.)
- Responsive web design with Bootstrap

## Setup Instructions

### Prerequisites
- Python 3.7+
- MySQL Server
- XAMPP (or similar for easy MySQL setup)

### Database Setup
1. Start MySQL server (through XAMPP or standalone)
2. Import the provided `drugweb.sql` file into MySQL
3. Database name: `drugweb`

### Application Setup
1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Update database configuration in `app.py`:
   ```python
   DB_CONFIG = {
       'host': 'localhost',
       'database': 'drugweb',
       'user': 'root',
       'password': 'your_mysql_password'  # Update this
   }
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to: `http://localhost:5000`

## Default Login Credentials

### Admin
- Email: `tasinhadi@gamil.com`
- Password: `1234`
- User Type: Admin

### Delivery Man
- Email: `atikjoyad@gamil.com`
- Password: `1234`
- User Type: Delivery Man

### Customer
- Customers need to sign up to create accounts
- Customer IDs are auto-generated as CM001, CM002, etc.

## Project Structure
```
DrugWeb/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── static/
│   └── style.css         # Custom CSS styles
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Landing page
│   ├── login.html        # Login page
│   ├── signup.html       # Customer signup
│   ├── admin_dashboard.html      # Admin dashboard
│   ├── customer_dashboard.html   # Customer home page
│   └── deliveryman_dashboard.html # Delivery dashboard
└── README.md
```

## Usage

### For Customers
1. Sign up for a new account or login if you have one
2. Browse popular medicines on the dashboard
3. Use search and sort functionality to find specific medicines
4. View medicine details including price and stock availability

### For Admin
1. Login with admin credentials
2. View complete medicine inventory
3. Monitor stock levels and availability
4. View statistics and analytics

### For Delivery Personnel
1. Login with delivery man credentials
2. View delivery dashboard
3. Track delivery statistics and earnings

## Technologies Used
- **Backend**: Flask (Python)
- **Database**: MySQL
- **Frontend**: HTML5, CSS3, Bootstrap 5
- **Icons**: Font Awesome
- **Database Connector**: mysql-connector-python

## Future Enhancements
- Shopping cart functionality
- Order processing system
- Payment integration
- Real-time notifications
- Advanced reporting and analytics
- Mobile app development

## Contributing
Feel free to fork this project and submit pull requests for any improvements.

## License
This project is open source and available under the MIT License.
