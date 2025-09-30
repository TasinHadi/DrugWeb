from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
import hashlib
from datetime import datetime
import re

# Import admin, customer, and deliveryman blueprints
from admin import admin_bp
from customer import customer_bp
from deliveryman import deliveryman_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

# Register blueprints
app.register_blueprint(admin_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(deliveryman_bp)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'drugweb',
    'user': 'root',
    'password': ''  # Add your MySQL password here
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        # Test if database exists, if not create it
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS drugweb")
        cursor.execute("USE drugweb")
        cursor.close()
        
        # Reconnect to the database
        DB_CONFIG['database'] = 'drugweb'
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        print("Please ensure MySQL server is running and accessible")
        return None

def generate_customer_id():
    """Generate next customer ID in format CM001, CM002, etc."""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT Customer_ID FROM customer ORDER BY Customer_ID DESC LIMIT 1")
        result = cursor.fetchone()
        
        if result:
            last_id = result[0]
            number = int(last_id[2:]) + 1
            new_id = f"CM{number:03d}"
        else:
            new_id = "CM001"
        
        cursor.close()
        connection.close()
        return new_id
    return "CM001"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update_medicine_db')
def update_medicine_db():
    """Add Category column to medicine table"""
    connection = get_db_connection()
    if not connection:
        return "❌ Database connection failed."
    
    try:
        cursor = connection.cursor()
        
        # Add Category column to medicine table
        cursor.execute("ALTER TABLE medicine ADD COLUMN Category VARCHAR(50)")
        connection.commit()
        
        # Update existing medicines with sample categories
        cursor.execute("UPDATE medicine SET Category = 'Pain Relief' WHERE Name LIKE '%Paracetamol%' OR Name LIKE '%Aspirin%'")
        cursor.execute("UPDATE medicine SET Category = 'Antibiotic' WHERE Name LIKE '%Amoxicillin%' OR Name LIKE '%Penicillin%'")
        cursor.execute("UPDATE medicine SET Category = 'General' WHERE Category IS NULL")
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return "✅ Category column added to medicine table and sample data updated!"
        
    except Exception as e:
        return f"Database update result: {str(e)}<br><small>Note: If error mentions 'Duplicate column name', the column already exists and this is normal.</small>"

@app.route('/update_db')
def update_db():
    """Add Status column to customer_request table"""
    connection = get_db_connection()
    if not connection:
        return "❌ Database connection failed."
    
    try:
        cursor = connection.cursor()
        
        # Add Status column to customer_request table
        cursor.execute("ALTER TABLE customer_request ADD COLUMN Status VARCHAR(20) DEFAULT 'Pending'")
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return "✅ Status column added to customer_request table successfully!"
        
    except Exception as e:
        return f"Database update result: {str(e)}<br><small>Note: If error mentions 'Duplicate column name', the column already exists and this is normal.</small>"

@app.route('/fix_db')
def fix_db():
    """Fix database by adding missing columns"""
    connection = get_db_connection()
    if not connection:
        return "❌ Database connection failed."
    
    try:
        cursor = connection.cursor()
        
        # Check if Request_ID column exists, if not add it
        cursor.execute("""
            ALTER TABLE customer_request 
            ADD COLUMN Request_ID INT AUTO_INCREMENT PRIMARY KEY FIRST
        """)
        
        # Add Status column if it doesn't exist
        cursor.execute("""
            ALTER TABLE customer_request 
            ADD COLUMN IF NOT EXISTS Status VARCHAR(20) DEFAULT 'Pending'
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return "✅ Database structure fixed! Request_ID and Status columns added."
        
    except Exception as e:
        return f"Database fix result: {str(e)} (This might be normal if columns already exist)"

@app.route('/setup_db')
def setup_db():
    """Setup database tables and create test customer"""
    connection = get_db_connection()
    if not connection:
        return "❌ Database connection failed. Please start MySQL server."
    
    try:
        cursor = connection.cursor()
        
        # Create user table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user (
                ID VARCHAR(10) PRIMARY KEY,
                F_name VARCHAR(50) NOT NULL,
                L_name VARCHAR(50) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                address TEXT,
                phone VARCHAR(20)
            )
        """)
        
        # Create customer table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer (
                Customer_ID VARCHAR(10) PRIMARY KEY,
                points INT DEFAULT 0,
                FOREIGN KEY (Customer_ID) REFERENCES user(ID)
            )
        """)
        
        # Create admin table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                Admin_ID VARCHAR(10) PRIMARY KEY,
                FOREIGN KEY (Admin_ID) REFERENCES user(ID)
            )
        """)
        
        # Create medicine table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine (
                Med_Code VARCHAR(10) PRIMARY KEY,
                Name VARCHAR(100) NOT NULL,
                Generic_name VARCHAR(100),
                Category VARCHAR(50),
                Price DECIMAL(10,2) NOT NULL,
                Stock INT DEFAULT 0
            )
        """)
        
        # Create customer_review table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_review (
                Review_ID INT AUTO_INCREMENT PRIMARY KEY,
                Customer_ID VARCHAR(10),
                review TEXT,
                FOREIGN KEY (Customer_ID) REFERENCES customer(Customer_ID)
            )
        """)
        
        # Create customer_request table with Request_ID
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_request (
                Request_ID INT AUTO_INCREMENT PRIMARY KEY,
                Customer_ID VARCHAR(10),
                request_med_name VARCHAR(100),
                Expected_date DATE,
                Status VARCHAR(20) DEFAULT 'Pending',
                FOREIGN KEY (Customer_ID) REFERENCES customer(Customer_ID)
            )
        """)
        
        # Create cart table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                Cart_ID INT AUTO_INCREMENT PRIMARY KEY,
                Customer_ID VARCHAR(10),
                Med_Code VARCHAR(10),
                Med_Name VARCHAR(100),
                Quantity INT DEFAULT 1,
                Price DECIMAL(10,2),
                Added_Date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (Customer_ID) REFERENCES customer(Customer_ID),
                FOREIGN KEY (Med_Code) REFERENCES medicine(Med_Code)
            )
        """)
        
        # Create notifications table for customer updates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id VARCHAR(10),
                message TEXT NOT NULL,
                type VARCHAR(50) DEFAULT 'general',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer(Customer_ID)
            )
        """)
        
        # Create points_history table for tracking points transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS points_history (
                history_id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id VARCHAR(10),
                points_earned INT NOT NULL,
                transaction_type VARCHAR(20) DEFAULT 'earned',
                payment_id VARCHAR(20),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customer(Customer_ID)
            )
        """)
        
        # Add missing columns to payment table if they don't exist
        try:
            cursor.execute("ALTER TABLE payment ADD COLUMN status VARCHAR(50) DEFAULT 'Assigned'")
        except:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE payment ADD COLUMN delivery_date DATE")  
        except:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE payment ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except:
            pass  # Column already exists
        
        # Create test customer
        cursor.execute("""
            INSERT IGNORE INTO user (ID, F_name, L_name, email, password, address, phone) 
            VALUES ('CM001', 'John', 'Doe', 'customer@test.com', 'password123', '123 Main St', '555-1234')
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO customer (Customer_ID, points) 
            VALUES ('CM001', 100)
        """)
        
        # Create test admin
        cursor.execute("""
            INSERT IGNORE INTO user (ID, F_name, L_name, email, password, address, phone) 
            VALUES ('AD001', 'Admin', 'User', 'admin@test.com', 'admin123', '456 Admin St', '555-5678')
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO admin (Admin_ID) 
            VALUES ('AD001')
        """)
        
        # Create test delivery man
        cursor.execute("""
            INSERT IGNORE INTO user (ID, F_name, L_name, email, password, address, phone) 
            VALUES ('DM001', 'Mike', 'Delivery', 'delivery@test.com', 'delivery123', '789 Delivery St', '555-9999')
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO deliveryman (DeliveryMan_ID, Name, Phone, Email, Area) 
            VALUES ('DM001', 'Mike Delivery', '555-9999', 'delivery@test.com', 'City Center')
        """)
        
        # Create sample medicines
        medicines = [
            ('MED001', 'Paracetamol', 'Acetaminophen', 'Pain Relief', 5.00, 100),
            ('MED002', 'Aspirin', 'Acetylsalicylic Acid', 'Pain Relief', 3.50, 75),
            ('MED003', 'Amoxicillin', 'Amoxicillin', 'Antibiotic', 12.00, 50)
        ]
        
        for med in medicines:
            cursor.execute("""
                INSERT IGNORE INTO medicine (Med_Code, Name, Generic_name, Category, Price, Stock) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, med)
        
        # Create a test payment assigned to delivery man for testing
        cursor.execute("""
            INSERT IGNORE INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID, status)
            VALUES (1001, 'CM001', 50.00, 'Cash on Delivery', 'DM001', 'Assigned')
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return """
        <h2>✅ Database Setup Complete!</h2>
        <p><strong>Test Login Credentials:</strong></p>
        <ul>
            <li>Customer: <code>customer@test.com</code> / <code>password123</code></li>
            <li>Admin: <code>admin@test.com</code> / <code>admin123</code></li>
            <li>Delivery Man: <code>delivery@test.com</code> / <code>delivery123</code></li>
        </ul>
        <p><a href="/login">Go to Login Page</a></p>
        """
        
    except Exception as e:
        return f"❌ Error setting up database: {str(e)}"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Check user credentials
            cursor.execute("SELECT * FROM user WHERE email = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            
            if user:
                user_id = user['ID']
                
                # Check user type and redirect accordingly
                if user_type == 'admin':
                    cursor.execute("SELECT * FROM admin WHERE Admin_ID = %s", (user_id,))
                    admin = cursor.fetchone()
                    if admin:
                        session['user_id'] = user_id
                        session['user_type'] = 'admin'
                        session['user_name'] = f"{user['F_name']} {user['L_name']}"
                        flash('Admin login successful!', 'success')
                        return redirect(url_for('admin.dashboard'))
                    else:
                        flash('Invalid admin credentials!', 'error')
                
                elif user_type == 'deliveryman':
                    cursor.execute("SELECT * FROM deliveryman WHERE DeliveryMan_ID = %s", (user_id,))
                    deliveryman = cursor.fetchone()
                    if deliveryman:
                        session['user_id'] = user_id
                        session['user_type'] = 'deliveryman'
                        session['user_name'] = f"{user['F_name']} {user['L_name']}"
                        flash('Delivery man login successful!', 'success')
                        return redirect(url_for('deliveryman.dashboard'))
                    else:
                        flash('Invalid delivery man credentials!', 'error')
                
                elif user_type == 'customer':
                    cursor.execute("SELECT * FROM customer WHERE Customer_ID = %s", (user_id,))
                    customer = cursor.fetchone()
                    print(f"Customer found: {customer}")  # Debug
                    if customer:
                        session['user_id'] = user_id
                        session['user_type'] = 'customer'
                        session['user_name'] = f"{user['F_name']} {user['L_name']}"
                        flash('Customer login successful!', 'success')
                        return redirect(url_for('customer.dashboard'))
                    else:
                        flash('Invalid customer credentials!', 'error')
                        print("Customer not found in customer table")  # Debug
            else:
                flash('Invalid email or password!', 'error')
                print("User not found in user table")  # Debug
            
            cursor.close()
            connection.close()
        else:
            print("Database connection failed")  # Debug
            flash('Database connection failed!', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        phone = request.form['phone']
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # Check if email already exists
            cursor.execute("SELECT * FROM user WHERE email = %s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Email already exists!', 'error')
            else:
                # Generate new customer ID
                customer_id = generate_customer_id()
                
                try:
                    # Insert into user table
                    cursor.execute("""
                        INSERT INTO user (ID, F_name, L_name, email, password, address, phone) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (customer_id, f_name, l_name, email, password, address, phone))
                    
                    # Insert into customer table
                    cursor.execute("INSERT INTO customer (Customer_ID, points) VALUES (%s, 0)", (customer_id,))
                    
                    connection.commit()
                    flash('Account created successfully! Please login.', 'success')
                    return redirect(url_for('login'))
                    
                except Error as e:
                    connection.rollback()
                    flash(f'Error creating account: {e}', 'error')
            
            cursor.close()
            connection.close()
    
    return render_template('signup.html')




@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('index'))



@app.route('/cart_minimal')
def cart_minimal():
    """Minimal cart page for testing"""
    return '''
    <html>
    <head><title>Cart Test</title></head>
    <body>
        <h1>Cart Page Test</h1>
        <p>This is a minimal cart page to test if routing works.</p>
        <a href="/customer_dashboard">Back to Dashboard</a>
    </body>
    </html>
    '''




@app.route('/check_customer_id')
def check_customer_id():
    """Check if current session customer_id exists in customer table"""
    if 'user_id' not in session:
        return "Please login first"
    
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        session_customer_id = session['user_id']
        
        # Check if customer exists
        cursor.execute("SELECT * FROM customer WHERE Customer_ID = %s", (session_customer_id,))
        customer = cursor.fetchone()
        
        # Check payment table structure for foreign key constraints
        cursor.execute("SHOW CREATE TABLE payment")
        payment_structure = cursor.fetchone()[1]
        
        # Get all customers
        cursor.execute("SELECT Customer_ID, Name FROM customer LIMIT 5")
        customers = cursor.fetchall()
        
        html = f"""
        <h1>Customer ID Debug</h1>
        <h3>Session Info:</h3>
        <p><strong>Session user_id:</strong> {session_customer_id}</p>
        <p><strong>Customer exists:</strong> {'✅ YES' if customer else '❌ NO'}</p>
        
        <h3>Sample Customers in Database:</h3>
        <table border="1">
        <tr><th>Customer_ID</th><th>Name</th></tr>
        """
        
        for cust in customers:
            html += f"<tr><td>{cust[0]}</td><td>{cust[1]}</td></tr>"
        
        html += f"""
        </table>
        
        <h3>Payment Table Structure:</h3>
        <pre>{payment_structure}</pre>
        
        <h3>Customer Details (if exists):</h3>
        """
        
        if customer:
            html += f"<p>Customer found: {customer}</p>"
        else:
            html += "<p style='color: red;'>❌ Customer not found in database!</p>"
            html += "<p><strong>Solution:</strong> Use an existing customer ID or create the customer first.</p>"
        
        return html
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"
    finally:
        cursor.close()
        connection.close()

@app.route('/check_payment_table')
def check_payment_table():
    """Check payment table structure and constraints"""
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Check table structure
        cursor.execute("DESCRIBE payment")
        columns = cursor.fetchall()
        
        # Check if table has any data
        cursor.execute("SELECT COUNT(*) FROM payment")
        count = cursor.fetchone()[0]
        
        html = "<h1>Payment Table Info</h1>"
        html += f"<p>Total records: {count}</p>"
        html += "<h3>Table Structure:</h3><table border='1'>"
        html += "<tr><th>Field</th><th>Type</th><th>Null</th><th>Key</th><th>Default</th><th>Extra</th></tr>"
        
        for col in columns:
            html += f"<tr><td>{col[0]}</td><td>{col[1]}</td><td>{col[2]}</td><td>{col[3]}</td><td>{col[4]}</td><td>{col[5]}</td></tr>"
        
        html += "</table>"
        
        # Try a test insert to see what happens
        try:
            test_payment_id = 'TEST123'
            test_customer_id = 'CUST001'
            test_amount = 100.00
            test_payment_type = 'Cash on Delivery'
            
            cursor.execute("""
                INSERT INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (test_payment_id, test_customer_id, test_amount, test_payment_type, None))
            
            html += f"<p style='color: green;'>✅ Test insert successful!</p>"
            connection.rollback()  # Don't actually save the test data
            
        except Exception as insert_error:
            html += f"<p style='color: red;'>❌ Test insert failed: {str(insert_error)}</p>"
            connection.rollback()
        
        return html
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"
    finally:
        cursor.close()
        connection.close()

@app.route('/test_payment')
def test_payment():
    """Test payment page without login requirement"""
    print("DEBUG: Test payment page accessed")
    
    # Simple test data to verify template works
    cart_items = [
        {
            'name': 'Test Medicine A',
            'quantity': 2,
            'unit_price': 15.50,
            'total': 31.00
        },
        {
            'name': 'Test Medicine B', 
            'quantity': 1,
            'unit_price': 25.75,
            'total': 25.75
        }
    ]
    total_amount = 56.75
    
    try:
        print("DEBUG: Attempting to render payment_page.html")
        return render_template('payment_page.html', 
                             cart_items=cart_items, 
                             total_amount=total_amount)
    except Exception as e:
        print(f"Template rendering error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return f"<h1>Template Error</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"



if __name__ == '__main__':
    app.run(debug=True)
