from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
import hashlib
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

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

@app.route('/debug_db')
def debug_db():
    """Debug route to check database connection and tables"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Check if tables exist
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            # Check user table
            cursor.execute("SELECT COUNT(*) as count FROM user")
            user_count = cursor.fetchone()
            
            # Check customer table  
            cursor.execute("SELECT COUNT(*) as count FROM customer")
            customer_count = cursor.fetchone()
            
            # Get sample data
            cursor.execute("SELECT * FROM user LIMIT 3")
            sample_users = cursor.fetchall()
            
            cursor.execute("SELECT * FROM customer LIMIT 3")
            sample_customers = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            return {
                'connection': 'Success',
                'tables': tables,
                'user_count': user_count,
                'customer_count': customer_count,
                'sample_users': sample_users,
                'sample_customers': sample_customers
            }
        except Exception as e:
            return {'error': str(e)}
    else:
        return {'connection': 'Failed'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        print(f"Login attempt: email={email}, user_type={user_type}")  # Debug
        
        connection = get_db_connection()
        if connection:
            print("Database connection successful")  # Debug
            cursor = connection.cursor(dictionary=True)
            
            # Check user credentials
            cursor.execute("SELECT * FROM user WHERE email = %s AND password = %s", (email, password))
            user = cursor.fetchone()
            
            print(f"User found: {user}")  # Debug
            
            if user:
                user_id = user['ID']
                print(f"User ID: {user_id}")  # Debug
                
                # Check user type and redirect accordingly
                if user_type == 'admin':
                    cursor.execute("SELECT * FROM admin WHERE Admin_ID = %s", (user_id,))
                    admin = cursor.fetchone()
                    if admin:
                        session['user_id'] = user_id
                        session['user_type'] = 'admin'
                        session['user_name'] = f"{user['F_name']} {user['L_name']}"
                        flash('Admin login successful!', 'success')
                        return redirect(url_for('admin_dashboard'))
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
                        return redirect(url_for('deliveryman_dashboard'))
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
                        return redirect(url_for('customer_dashboard'))
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

@app.route('/admin_payments')
def admin_payments():
    """Admin view to see all customer payments"""
    if 'user_id' not in session or session['user_type'] != 'admin':
        flash('Please login as admin first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('admin_dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # First get all payments with customer details (simplified query)
        cursor.execute("""
            SELECT p.payment_id, p.Customer_ID, p.amount, p.payment_type, p.DeliveryMan_ID,
                   CONCAT(u.F_name, ' ', u.L_name) as customer_name, u.phone as customer_phone, u.address as customer_address
            FROM payment p
            JOIN customer c ON p.Customer_ID = c.Customer_ID
            JOIN user u ON c.Customer_ID = u.ID
            ORDER BY p.payment_id DESC
        """)
        
        payments = cursor.fetchall()
        
        # Add delivery man info separately to handle potential missing records
        for payment in payments:
            if payment['DeliveryMan_ID']:
                try:
                    cursor.execute("""
                        SELECT CONCAT(u.F_name, ' ', u.L_name) as Name, u.phone as Phone 
                        FROM deliveryman d 
                        JOIN user u ON d.DeliveryMan_ID = u.ID 
                        WHERE d.DeliveryMan_ID = %s
                    """, (payment['DeliveryMan_ID'],))
                    deliveryman = cursor.fetchone()
                    if deliveryman:
                        payment['deliveryman_name'] = deliveryman['Name']
                        payment['deliveryman_phone'] = deliveryman['Phone']
                    else:
                        payment['deliveryman_name'] = None
                        payment['deliveryman_phone'] = None
                except:
                    payment['deliveryman_name'] = None
                    payment['deliveryman_phone'] = None
            else:
                payment['deliveryman_name'] = None
                payment['deliveryman_phone'] = None
        
        # Get all available delivery men for assignment
        try:
            cursor.execute("""
                SELECT d.DeliveryMan_ID, CONCAT(u.F_name, ' ', u.L_name) as Name, u.phone as Phone 
                FROM deliveryman d 
                JOIN user u ON d.DeliveryMan_ID = u.ID 
                ORDER BY u.F_name, u.L_name
            """)
            deliverymen = cursor.fetchall()
        except:
            deliverymen = []
        
        print(f"DEBUG: Found {len(payments)} payments and {len(deliverymen)} delivery men")
        
        return render_template('admin_payments.html', 
                             payments=payments, 
                             deliverymen=deliverymen)
        
    except Exception as e:
        print(f"Error fetching payments: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        flash(f"Error loading payments: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
        connection.close()

@app.route('/assign_deliveryman', methods=['POST'])
def assign_deliveryman():
    """Assign a delivery man to a payment"""
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    payment_id = request.form.get('payment_id')
    deliveryman_id = request.form.get('deliveryman_id')
    
    if not payment_id or not deliveryman_id:
        return jsonify({'success': False, 'message': 'Missing payment ID or delivery man ID'})
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    try:
        cursor = connection.cursor()
        
        # Update payment with delivery man assignment
        cursor.execute("""
            UPDATE payment 
            SET DeliveryMan_ID = %s 
            WHERE payment_id = %s
        """, (deliveryman_id, payment_id))
        
        if cursor.rowcount > 0:
            connection.commit()
            
            # Get delivery man name for response
            cursor.execute("SELECT Name FROM deliveryman WHERE DeliveryMan_ID = %s", (deliveryman_id,))
            deliveryman = cursor.fetchone()
            deliveryman_name = deliveryman[0] if deliveryman else "Unknown"
            
            return jsonify({
                'success': True, 
                'message': f'Delivery man {deliveryman_name} assigned successfully',
                'deliveryman_name': deliveryman_name
            })
        else:
            return jsonify({'success': False, 'message': 'Payment not found'})
            
    except Exception as e:
        print(f"Error assigning delivery man: {e}")
        connection.rollback()
        return jsonify({'success': False, 'message': 'Database error occurred'})
    finally:
        cursor.close()
        connection.close()

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['user_type'] != 'admin':
        flash('Please login as admin first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    medicines = []
    reviews = []
    requests = []
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        try:
            # 1. Get medicines ordered by Med_Code
            cursor.execute("SELECT * FROM medicine ORDER BY Med_Code")
            medicines = cursor.fetchall()
            
            # 2. Get customer reviews with customer names
            cursor.execute("""
                SELECT cr.*, CONCAT(u.F_name, ' ', u.L_name) as customer_name
                FROM customer_review cr
                JOIN customer c ON cr.Customer_ID = c.Customer_ID
                JOIN user u ON c.Customer_ID = u.ID
            """)
            reviews = cursor.fetchall()
            
            # 3. Get medicine requests with customer names (handle missing Status column)
            try:
                cursor.execute("""
                    SELECT cmr.Customer_ID, cmr.request_med_name, cmr.Expected_date, 
                           IFNULL(cmr.Status, 'Pending') as Status,
                           CONCAT(u.F_name, ' ', u.L_name) as customer_name 
                    FROM customer_request cmr
                    JOIN customer c ON cmr.Customer_ID = c.Customer_ID
                    JOIN user u ON c.Customer_ID = u.ID
                    ORDER BY cmr.request_med_name
                """)
            except:
                # If Status column doesn't exist, add it first
                cursor.execute("ALTER TABLE customer_request ADD COLUMN Status VARCHAR(20) DEFAULT 'Pending'")
                connection.commit()
                cursor.execute("""
                    SELECT cmr.Customer_ID, cmr.request_med_name, cmr.Expected_date, 
                           IFNULL(cmr.Status, 'Pending') as Status,
                           CONCAT(u.F_name, ' ', u.L_name) as customer_name 
                    FROM customer_request cmr
                    JOIN customer c ON cmr.Customer_ID = c.Customer_ID
                    JOIN user u ON c.Customer_ID = u.ID
                    ORDER BY cmr.request_med_name
                """)
            requests = cursor.fetchall()
            
        except Exception as e:
            flash(f'Database error: {str(e)}', 'error')
            print(f"Admin dashboard error: {e}")
        
        cursor.close()
        connection.close()
    
    return render_template('admin_dashboard.html', 
                         medicines=medicines, 
                         reviews=reviews, 
                         requests=requests)

@app.route('/customer_dashboard')
def customer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    # Get search and sort parameters (removed category)
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'name')
    show_all = request.args.get('show_all', '0')
    
    connection = get_db_connection()
    medicines = []
    customer_points = 0
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get customer's current points
        try:
            cursor.execute("SELECT points FROM customer WHERE Customer_ID = %s", (session['user_id'],))
            points_result = cursor.fetchone()
            customer_points = points_result['points'] if points_result else 0
        except Exception as e:
            print(f"Error fetching customer points: {e}")
            customer_points = 0
        
        # Build query based on search and sort (no category)
        base_query = "SELECT * FROM medicine WHERE 1=1"
        params = []
        
        # Add search condition
        if search:
            base_query += " AND (Name LIKE %s OR Generic_name LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        # Add sorting
        if sort_by == 'price':
            base_query += " ORDER BY Price ASC"
        elif sort_by == 'price_desc':
            base_query += " ORDER BY Price DESC"
        else:
            base_query += " ORDER BY Name ASC"
        
        # Add limit if not showing all
        if show_all != '1' and not search:
            base_query += " LIMIT 9"
        
        cursor.execute(base_query, params)
        medicines = cursor.fetchall()
        cursor.close()
        connection.close()
    
    return render_template('customer_dashboard.html', medicines=medicines, 
                         search=search, sort_by=sort_by, show_all=show_all, customer_points=customer_points)

@app.route('/customer_notifications')
def customer_notifications():
    """Customer view to see delivery status notifications"""
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    customer_id = session['user_id']
    connection = get_db_connection()
    notifications = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all notifications for this customer, ordered by newest first
            cursor.execute("""
                SELECT notification_id, message, type, is_read, created_at
                FROM notifications
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            notifications = cursor.fetchall()
            
            # Mark all notifications as read
            cursor.execute("""
                UPDATE notifications SET is_read = TRUE WHERE customer_id = %s
            """, (customer_id,))
            
            connection.commit()
            
        except Exception as e:
            print(f"Error fetching notifications: {e}")
            flash("Error loading notifications", "error")
        finally:
            connection.close()
    
    return render_template('customer_notifications.html', notifications=notifications)

@app.route('/customer_points')
def customer_points():
    """Customer view to see points balance and transaction history"""
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    customer_id = session['user_id']
    connection = get_db_connection()
    points_history = []
    current_points = 0
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get current points balance
            cursor.execute("SELECT points FROM customer WHERE Customer_ID = %s", (customer_id,))
            points_result = cursor.fetchone()
            current_points = points_result['points'] if points_result else 0
            
            # Get points transaction history
            cursor.execute("""
                SELECT points_earned, transaction_type, payment_id, description, created_at
                FROM points_history
                WHERE customer_id = %s
                ORDER BY created_at DESC
            """, (customer_id,))
            
            points_history = cursor.fetchall()
            
        except Exception as e:
            print(f"Error fetching points history: {e}")
            flash("Error loading points history", "error")
        finally:
            connection.close()
    
    return render_template('customer_points.html', 
                         points_history=points_history, 
                         current_points=current_points)

@app.route('/browse_medicines')
def browse_medicines():
    if 'user_id' not in session or session['user_type'] != 'customer':
        return redirect(url_for('login'))
    
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'name')
    category = request.args.get('category', '')
    page = int(request.args.get('page', 1))
    per_page = 12  # Show 12 medicines per page
    
    medicines = []
    total_count = 0
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Build the base query
        base_query = "SELECT * FROM medicine WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM medicine WHERE 1=1"
        params = []
        
        # Add search condition
        if search:
            base_query += " AND (Name LIKE %s OR Generic_name LIKE %s OR Category LIKE %s)"
            count_query += " AND (Name LIKE %s OR Generic_name LIKE %s OR Category LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        # Add category filter
        if category:
            base_query += " AND Category = %s"
            count_query += " AND Category = %s"
            params.append(category)
        
        # Add ordering
        if sort_by == 'price':
            base_query += " ORDER BY Price ASC"
        elif sort_by == 'price_desc':
            base_query += " ORDER BY Price DESC"
        else:
            base_query += " ORDER BY Name ASC"
        
        # Get total count for pagination
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['total']
        
        # Add pagination
        offset = (page - 1) * per_page
        base_query += f" LIMIT {per_page} OFFSET {offset}"
        
        # Get medicines
        cursor.execute(base_query, params)
        medicines = cursor.fetchall()
        
        # Get all categories for filter dropdown
        cursor.execute("SELECT DISTINCT Category FROM medicine WHERE Category IS NOT NULL AND Category != '' ORDER BY Category")
        categories = cursor.fetchall()
        
        cursor.close()
        connection.close()
    
    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    return render_template('browse_medicines.html', 
                         medicines=medicines, 
                         categories=categories,
                         search=search, 
                         sort_by=sort_by,
                         category=category,
                         page=page,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next,
                         total_count=total_count)

@app.route('/get_notifications')
def get_notifications():
    if 'user_id' not in session or session['user_type'] != 'customer':
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    customer_id = session['user_id']
    connection = get_db_connection()
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Get unread notifications for the customer
            cursor.execute("""
                SELECT Notification_ID, Message, Type, Created_at, Is_read
                FROM notifications 
                WHERE Customer_ID = %s 
                ORDER BY Created_at DESC
                LIMIT 10
            """, (customer_id,))
            
            notifications = cursor.fetchall()
            
            # Mark notifications as read
            cursor.execute("""
                UPDATE notifications 
                SET Is_read = 1 
                WHERE Customer_ID = %s AND Is_read = 0
            """, (customer_id,))
            
            connection.commit()
            return jsonify({'success': True, 'notifications': notifications})
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
        finally:
            cursor.close()
            connection.close()
    
    return jsonify({'success': False, 'message': 'Database connection failed'})

@app.route('/deliveryman_dashboard')
def deliveryman_dashboard():
    if 'user_id' not in session or session['user_type'] != 'deliveryman':
        flash('Please login as delivery man first!', 'error')
        return redirect(url_for('login'))
    
    deliveryman_id = session['user_id']
    connection = get_db_connection()
    assigned_payments = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get all payments assigned to this delivery man (including reassigned ones)
            cursor.execute("""
                SELECT p.payment_id as Payment_ID, p.Customer_ID, p.amount as Total_Amount, 
                       p.payment_type, p.DeliveryMan_ID,
                       CONCAT(u.F_name, ' ', u.L_name) as Customer_name,
                       u.email as Customer_email, u.phone as Customer_phone, 
                       u.address as Customer_address,
                       COALESCE(p.status, 'Assigned') as Status,
                       p.created_at as Payment_date, p.delivery_date
                FROM payment p
                JOIN customer c ON p.Customer_ID = c.Customer_ID
                JOIN user u ON c.Customer_ID = u.ID
                WHERE p.DeliveryMan_ID = %s
                ORDER BY p.created_at DESC
            """, (deliveryman_id,))
            
            assigned_payments = cursor.fetchall()
            print(f"DEBUG: Found {len(assigned_payments)} payments for delivery man {deliveryman_id}")
            
        except Exception as e:
            print(f"Error fetching assigned payments: {e}")
            flash("Error loading assigned payments", "error")
        finally:
            connection.close()
    
    return render_template('deliveryman_dashboard.html', 
                         assigned_payments=assigned_payments)

@app.route('/deliveryman/handle_delivery', methods=['POST'])
def handle_delivery():
    if 'user_id' not in session or session['user_type'] != 'deliveryman':
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    deliveryman_id = session['user_id']
    data = request.get_json()
    
    payment_id = data.get('payment_id')
    action = data.get('action')  # 'accept' or 'decline'
    delivery_date = data.get('delivery_date')
    
    if not payment_id or not action:
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Verify this payment is assigned to this delivery man
        cursor.execute("""
            SELECT p.*, CONCAT(u.F_name, ' ', u.L_name) as customer_name,
                   u.email as customer_email
            FROM payment p
            JOIN customer c ON p.Customer_ID = c.Customer_ID  
            JOIN user u ON c.Customer_ID = u.ID
            WHERE p.payment_id = %s AND p.DeliveryMan_ID = %s
        """, (payment_id, deliveryman_id))
        
        payment = cursor.fetchone()
        if not payment:
            return jsonify({'success': False, 'message': 'Payment not found or not assigned to you'})
        
        if action == 'accept':
            # Update payment status to accepted
            cursor.execute("""
                UPDATE payment 
                SET status = 'Accepted for Delivery', delivery_date = %s 
                WHERE payment_id = %s
            """, (delivery_date, payment_id))
            
            # Add notification for customer
            notification_message = f"Great news! Your order (Payment #{payment_id}) has been accepted by our delivery partner and will be delivered on {delivery_date}."
            cursor.execute("""
                INSERT INTO notifications (customer_id, message, type, created_at)
                VALUES (%s, %s, 'delivery_accepted', NOW())
            """, (payment['Customer_ID'], notification_message))
            
            message = f"Order #{payment_id} accepted for delivery on {delivery_date}. Customer has been notified."
            
        elif action == 'decline':
            # Update payment to remove delivery man assignment
            cursor.execute("""
                UPDATE payment 
                SET DeliveryMan_ID = NULL, status = 'Pending Assignment' 
                WHERE payment_id = %s
            """, (payment_id,))
            
            # Add notification for customer
            notification_message = f"We apologize, but your order (Payment #{payment_id}) needs to be reassigned to a different delivery partner. Our admin will assign it shortly."
            cursor.execute("""
                INSERT INTO notifications (customer_id, message, type, created_at)
                VALUES (%s, %s, 'delivery_declined', NOW())
            """, (payment['Customer_ID'], notification_message))
            
            message = f"Order #{payment_id} declined and made available for reassignment. Customer has been notified."
        
        connection.commit()
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        print(f"Error handling delivery action: {e}")
        connection.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while processing your request'})
    finally:
        connection.close()

@app.route('/debug/deliveryman')
def debug_deliveryman():
    if 'user_id' not in session or session['user_type'] != 'deliveryman':
        return jsonify({'error': 'Unauthorized'})
    
    deliveryman_id = session['user_id']
    connection = get_db_connection()
    debug_info = {}
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Get deliveryman info
            cursor.execute("SELECT * FROM deliveryman WHERE DeliveryMan_ID = %s", (deliveryman_id,))
            deliveryman_info = cursor.fetchone()
            debug_info['deliveryman_info'] = deliveryman_info
            debug_info['session_user_id'] = deliveryman_id
            
        except Exception as e:
            debug_info['error'] = str(e)
        finally:
            cursor.close()
            connection.close()
    
    return jsonify(debug_info)

@app.route('/deliveryman_profile')
def deliveryman_profile():
    if 'user_id' not in session or session['user_type'] != 'deliveryman':
        flash('Please login as delivery man first!', 'error')
        return redirect(url_for('login'))
    
    deliveryman_id = session['user_id']
    connection = get_db_connection()
    deliveryman_info = {}
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT u.F_name, u.L_name, u.email, u.phone, u.address,
                       d.DeliveryMan_ID
                FROM user u
                JOIN deliveryman d ON u.ID = d.DeliveryMan_ID
                WHERE u.ID = %s
            """, (deliveryman_id,))
            
            deliveryman_info = cursor.fetchone() or {}
            print(f"DEBUG: Deliveryman info: {deliveryman_info}")
            
        except Exception as e:
            print(f"DEBUG: Error loading profile: {e}")
            flash(f'Error loading profile: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('deliveryman_profile.html', deliveryman_info=deliveryman_info)

@app.route('/admin_profile')
def admin_profile():
    if 'user_id' not in session or session['user_type'] != 'admin':
        flash('Please login as admin first!', 'error')
        return redirect(url_for('login'))
    
    admin_id = session['user_id']
    connection = get_db_connection()
    admin_info = {}
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT u.F_name, u.L_name, u.email, u.phone, u.address,
                       a.Admin_ID
                FROM user u
                JOIN admin a ON u.ID = a.Admin_ID
                WHERE u.ID = %s
            """, (admin_id,))
            
            admin_info = cursor.fetchone() or {}
            print(f"DEBUG: Admin info: {admin_info}")
            
        except Exception as e:
            print(f"DEBUG: Error loading admin profile: {e}")
            flash(f'Error loading profile: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('admin_profile.html', admin_info=admin_info)


@app.route('/debug/database_state')
def debug_database_state():
    connection = get_db_connection()
    debug_info = {}
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Check medicines
            cursor.execute("SELECT Med_Code, Name, Stock FROM medicine LIMIT 5")
            medicines = cursor.fetchall()
            debug_info['medicines'] = medicines
            
        except Exception as e:
            debug_info['error'] = str(e)
        finally:
            cursor.close()
            connection.close()
    
    return jsonify(debug_info)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    
    if request.method == 'POST':
        review_text = request.form['review']
        customer_id = session['user_id']
        
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute("""
                    INSERT INTO customer_review (Customer_ID, review) 
                    VALUES (%s, %s)
                """, (customer_id, review_text))
                connection.commit()
                flash('Your review has been submitted successfully!', 'success')
            except Error as e:
                connection.rollback()
                flash(f'Error submitting review: {e}', 'error')
            finally:
                cursor.close()
    
    # Fetch all reviews with customer names
    reviews_list = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT cr.review, u.F_name, u.L_name, cr.Customer_ID
            FROM customer_review cr
            JOIN user u ON cr.Customer_ID = u.ID
            ORDER BY cr.Customer_ID DESC
        """)
        reviews_list = cursor.fetchall()
        cursor.close()
        connection.close()
    
    return render_template('reviews.html', reviews=reviews_list)

@app.route('/request_medicine', methods=['GET', 'POST'])
def request_medicine():
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    
    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        expected_date = request.form['expected_date']
        customer_id = session['user_id']
        
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute("""
                    INSERT INTO customer_request (Customer_ID, request_med_name, Expected_date) 
                    VALUES (%s, %s, %s)
                """, (customer_id, medicine_name, expected_date))
                connection.commit()
                flash('Your medicine request has been submitted successfully!', 'success')
            except Error as e:
                connection.rollback()
                flash(f'Error submitting request: {e}', 'error')
            finally:
                cursor.close()
    
    # Fetch customer's previous requests with status
    requests_list = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # First ensure the Status column exists
        try:
            cursor.execute("ALTER TABLE customer_request ADD COLUMN IF NOT EXISTS Status VARCHAR(20) DEFAULT 'Pending'")
            connection.commit()
        except:
            pass  # Column might already exist
        
        try:
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       IFNULL(Status, 'Pending') as Status
                FROM customer_request
                WHERE Customer_ID = %s
                ORDER BY request_med_name DESC
            """, (session['user_id'],))
        except:
            # If Status column still doesn't exist, add it and retry
            cursor.execute("ALTER TABLE customer_request ADD COLUMN Status VARCHAR(20) DEFAULT 'Pending'")
            connection.commit()
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       IFNULL(Status, 'Pending') as Status
                FROM customer_request
                WHERE Customer_ID = %s
                ORDER BY request_med_name DESC
            """, (session['user_id'],))
        requests_list = cursor.fetchall()
        cursor.close()
        connection.close()
    
    return render_template('request_medicine.html', requests=requests_list)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    user_info = {}
    customer_info = {}
    
    if request.method == 'POST':
        # Update profile information
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute("""
                    UPDATE user SET F_name = %s, L_name = %s, email = %s, 
                    phone = %s, address = %s WHERE ID = %s
                """, (f_name, l_name, email, phone, address, session['user_id']))
                connection.commit()
                session['user_name'] = f"{f_name} {l_name}"
                flash('Profile updated successfully!', 'success')
            except Error as e:
                connection.rollback()
                flash(f'Error updating profile: {e}', 'error')
            finally:
                cursor.close()
    
    # Fetch user and customer information
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get user info
        cursor.execute("SELECT * FROM user WHERE ID = %s", (session['user_id'],))
        user_info = cursor.fetchone() or {}
        
        # Get customer info (points)
        cursor.execute("SELECT * FROM customer WHERE Customer_ID = %s", (session['user_id'],))
        customer_info = cursor.fetchone() or {}
        
        # Get recent requests for notifications with status
        try:
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       IFNULL(Status, 'Pending') as Status 
                FROM customer_request 
                WHERE Customer_ID = %s 
                ORDER BY request_med_name DESC 
                LIMIT 5
            """, (session['user_id'],))
        except:
            # If Status column doesn't exist, just get without it
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       'Pending' as Status 
                FROM customer_request 
                WHERE Customer_ID = %s 
                ORDER BY request_med_name DESC 
                LIMIT 5
            """, (session['user_id'],))
        recent_requests = cursor.fetchall()
        
        # Get recent reviews
        cursor.execute("""
            SELECT review 
            FROM customer_review 
            WHERE Customer_ID = %s 
            ORDER BY Customer_ID DESC 
            LIMIT 3
        """, (session['user_id'],))
        recent_reviews = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('profile.html', 
                             user_info=user_info, 
                             customer_info=customer_info,
                             recent_requests=recent_requests,
                             recent_reviews=recent_reviews)
    
    return render_template('profile.html', user_info={}, customer_info={})

@app.route('/notifications')
def notifications():
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    notifications = []
    
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Create notifications based on requests and current date
        try:
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       IFNULL(Status, 'Pending') as Status 
                FROM customer_request 
                WHERE Customer_ID = %s 
                ORDER BY request_med_name DESC
            """, (session['user_id'],))
        except:
            # If Status column doesn't exist, just get without it
            cursor.execute("""
                SELECT request_med_name, Expected_date, 
                       'Pending' as Status 
                FROM customer_request 
                WHERE Customer_ID = %s 
                ORDER BY request_med_name DESC
            """, (session['user_id'],))
        requests = cursor.fetchall()
        
        from datetime import date, timedelta
        today = date.today()
        
        for request in requests:
            expected_date = request['Expected_date']
            status = request.get('Status', 'Pending')
            
            # Add status-based notifications first
            if status == 'Accepted':
                notifications.append({
                    'type': 'accepted',
                    'title': 'Request Accepted',
                    'message': f"Great! Your request for '{request['request_med_name']}' has been accepted by admin",
                    'date': expected_date or today,
                    'icon': 'fas fa-check-circle',
                    'class': 'alert-success'
                })
            elif status == 'Declined':
                notifications.append({
                    'type': 'declined',
                    'title': 'Request Declined',
                    'message': f"Sorry, your request for '{request['request_med_name']}' has been declined",
                    'date': expected_date or today,
                    'icon': 'fas fa-times-circle',
                    'class': 'alert-danger'
                })
            
            # Add date-based notifications only for pending requests
            if status == 'Pending' or not status:
                if expected_date:
                    days_diff = (expected_date - today).days
                    
                    if days_diff < 0:
                        notifications.append({
                            'type': 'overdue',
                            'title': 'Request Overdue',
                            'message': f"Your request for '{request['request_med_name']}' was expected on {expected_date.strftime('%B %d, %Y')}",
                            'date': expected_date,
                            'icon': 'fas fa-exclamation-triangle',
                            'class': 'alert-danger'
                        })
                    elif days_diff == 0:
                        notifications.append({
                            'type': 'today',
                            'title': 'Request Due Today',
                            'message': f"Your request for '{request['request_med_name']}' is expected today",
                            'date': expected_date,
                            'icon': 'fas fa-bell',
                            'class': 'alert-warning'
                        })
                    elif days_diff <= 3:
                        notifications.append({
                            'type': 'upcoming',
                            'title': 'Request Due Soon',
                            'message': f"Your request for '{request['request_med_name']}' is expected in {days_diff} day{'s' if days_diff > 1 else ''}",
                            'date': expected_date,
                            'icon': 'fas fa-info-circle',
                            'class': 'alert-info'
                        })
        
        # Add welcome notification for new users
        cursor.execute("SELECT points FROM customer WHERE Customer_ID = %s", (session['user_id'],))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
    
    # Sort notifications by date (newest first)
    notifications.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('notifications.html', notifications=notifications)

# Admin routes for request management
@app.route('/admin/handle_request', methods=['POST'])
def handle_request():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    customer_id = request.json.get('customer_id')
    medicine_name = request.json.get('medicine_name')
    action = request.json.get('action')  # 'accept' or 'decline'
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        try:
            # First, ensure the Status column exists
            try:
                cursor.execute("""
                    ALTER TABLE customer_request 
                    ADD COLUMN IF NOT EXISTS Status VARCHAR(20) DEFAULT 'Pending'
                """)
                connection.commit()
            except:
                pass  # Column might already exist
            
            # Check if the request exists
            cursor.execute("""
                SELECT Customer_ID, request_med_name 
                FROM customer_request 
                WHERE Customer_ID = %s AND request_med_name = %s
                LIMIT 1
            """, (customer_id, medicine_name))
            request_info = cursor.fetchone()
            
            if not request_info:
                return jsonify({'success': False, 'message': 'Request not found'})
            
            if action == 'accept':
                # Update request status to accepted
                cursor.execute("""
                    UPDATE customer_request 
                    SET Status = 'Accepted' 
                    WHERE Customer_ID = %s AND request_med_name = %s
                """, (customer_id, medicine_name))
                
                message = f'Request for {medicine_name} has been accepted successfully!'
                
            elif action == 'decline':
                # Update request status to declined
                cursor.execute("""
                    UPDATE customer_request 
                    SET Status = 'Declined' 
                    WHERE Customer_ID = %s AND request_med_name = %s
                """, (customer_id, medicine_name))
                
                message = f'Request for {medicine_name} has been declined.'
                
            else:
                return jsonify({'success': False, 'message': 'Invalid action'})
            
            connection.commit()
            return jsonify({'success': True, 'message': message})
            
        except Exception as e:
            connection.rollback()
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
        finally:
            cursor.close()
            connection.close()
    
    return jsonify({'success': False, 'message': 'Database connection failed'})

@app.route('/admin/get_deliverymen', methods=['GET'])
def get_deliverymen():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT d.DeliveryMan_ID, CONCAT(u.F_name, ' ', u.L_name) as name 
                FROM deliveryman d
                JOIN user u ON d.DeliveryMan_ID = u.ID
            """)
            deliverymen = cursor.fetchall()
            return jsonify({'success': True, 'deliverymen': deliverymen})
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})
        finally:
            cursor.close()
            connection.close()
    
    return jsonify({'success': False, 'message': 'Database connection failed'})

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    print(f"Session data: {dict(session)}")  # Debug
    
    if 'user_id' not in session or session['user_type'] != 'customer':
        return jsonify({'success': False, 'message': 'Please login as customer first'})
    
    try:
        data = request.json
        print(f"Received data: {data}")  # Debug
        
        med_code = data.get('med_code')
        med_name = data.get('med_name')
        quantity = int(data.get('quantity', 1))
        price = float(data.get('price', 0))
        customer_id = session['user_id']
        
        print(f"Parsed - Code: {med_code}, Name: {med_name}, Price: {price}, Qty: {quantity}, Customer: {customer_id}")  # Debug
        
        if not med_code or quantity <= 0:
            return jsonify({'success': False, 'message': 'Invalid input data'})
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'})
        
        cursor = connection.cursor(dictionary=True)
        
        # Check if medicine exists and has enough stock
        cursor.execute("SELECT Stock FROM medicine WHERE Med_code = %s", (med_code,))
        medicine = cursor.fetchone()
        
        if not medicine:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Medicine not found'})
        
        if medicine['Stock'] < quantity:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': f'Only {medicine["Stock"]} units available'})
        
        # Check if item already exists in cart
        cursor.execute("""
            SELECT quantity FROM cart 
            WHERE Customer_ID = %s AND Med_Code = %s
        """, (customer_id, med_code))
        
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item['quantity'] + quantity
            new_total = new_quantity * price
            cursor.execute("""
                UPDATE cart 
                SET quantity = %s, total_price = %s
                WHERE Customer_ID = %s AND Med_Code = %s
            """, (new_quantity, new_total, customer_id, med_code))
        else:
            # Add new item to cart
            total_price = quantity * price
            cursor.execute("""
                INSERT INTO cart (Customer_ID, Med_Code, quantity, total_price) 
                VALUES (%s, %s, %s, %s)
            """, (customer_id, med_code, quantity, total_price))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Item added to cart successfully'})
        
    except Exception as e:
        print(f"Error adding to cart: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

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

@app.route('/test_basic')
def test_basic():
    """Basic test route"""
    return "Cart test route is working!"

@app.route('/test_simple_cart')
def test_simple_cart():
    """Simple cart test"""
    cart_items = [
        {
            'Cart_ID': 1,
            'Med_Code': 'MED001',
            'quantity': 2,
            'total_price': 100.0,
            'Med_Name': 'Test Medicine',
            'unit_price': 50.0
        }
    ]
    total_cart_value = 100.0
    return render_template('cart.html', cart_items=cart_items, total_cart_value=total_cart_value)

@app.route('/test_cart_direct')
def test_cart_direct():
    """Test cart page directly without login"""
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.Cart_ID, c.Med_Code, c.quantity, c.total_price,
                   m.Name as Med_Name, m.Price as unit_price
            FROM cart c 
            JOIN medicine m ON c.Med_Code = m.Med_Code
            LIMIT 10
        """)
        cart_items = cursor.fetchall()
        
        # Calculate total cart value
        total_cart_value = sum(item['total_price'] for item in cart_items) if cart_items else 0
        
        return render_template('cart.html', cart_items=cart_items, total_cart_value=total_cart_value)
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        if cursor:
            cursor.close()
        connection.close()

# New Cart Management Routes
@app.route('/cart')
def view_cart():
    """Display the user's cart"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('customer_dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        print(f"Debug: Fetching cart for user_id: {session['user_id']}")
        cursor.execute("""
            SELECT c.Cart_ID, c.Med_Code, c.quantity, c.total_price,
                   m.Name as Med_Name, m.Price as unit_price
            FROM cart c 
            JOIN medicine m ON c.Med_Code = m.Med_Code
            WHERE c.Customer_ID = %s
            ORDER BY c.Cart_ID DESC
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        print(f"Debug: Found {len(cart_items)} cart items")
        print(f"Debug: Cart items: {cart_items}")
        
        # Calculate total cart value
        total_cart_value = sum(item['total_price'] for item in cart_items)
        print(f"Debug: Total cart value: {total_cart_value}")
        
        return render_template('cart.html', cart_items=cart_items, total_cart_value=total_cart_value)
        
    except Exception as e:
        print(f"Error fetching cart: {e}")
        flash("Error loading cart", "error")
        return redirect(url_for('customer_dashboard'))
    finally:
        cursor.close()
        connection.close()

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    """Update quantity of item in cart"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.get_json()
    cart_id = data.get('cart_id')
    new_quantity = data.get('quantity')
    
    if not cart_id or not new_quantity or int(new_quantity) < 1:
        return jsonify({'success': False, 'message': 'Invalid quantity'})
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    try:
        cursor = connection.cursor()
        
        # Get current item details to calculate new total
        cursor.execute("""
            SELECT c.Med_Code, m.Price 
            FROM cart c 
            JOIN medicine m ON c.Med_Code = m.Med_Code 
            WHERE c.Cart_ID = %s
        """, (cart_id,))
        
        item = cursor.fetchone()
        if not item:
            return jsonify({'success': False, 'message': 'Item not found'})
        
        new_total = int(new_quantity) * item[1]  # quantity * unit price
        
        # Update the quantity and total
        cursor.execute("""
            UPDATE cart 
            SET quantity = %s, total_price = %s
            WHERE Cart_ID = %s AND Customer_ID = %s
        """, (new_quantity, new_total, cart_id, session['user_id']))
        
        connection.commit()
        
        return jsonify({
            'success': True, 
            'new_quantity': int(new_quantity),
            'item_total': float(new_total)
        })
        
    except Exception as e:
        print(f"Error updating cart: {e}")
        return jsonify({'success': False, 'message': 'Error updating cart'})
    finally:
        cursor.close()
        connection.close()

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    """Remove item from cart"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.get_json()
    cart_id = data.get('cart_id')
    
    if not cart_id:
        return jsonify({'success': False, 'message': 'Invalid item'})
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Database connection failed'})
    
    try:
        cursor = connection.cursor()
        
        # Remove the item
        cursor.execute("""
            DELETE FROM cart 
            WHERE Cart_ID = %s AND Customer_ID = %s
        """, (cart_id, session['user_id']))
        
        connection.commit()
        
        return jsonify({'success': True, 'message': 'Item removed from cart'})
        
    except Exception as e:
        print(f"Error removing from cart: {e}")
        return jsonify({'success': False, 'message': 'Error removing item'})
    finally:
        cursor.close()
        connection.close()

@app.route('/test_add_simple')
def test_add_simple():
    """Simple test to add an item to cart"""
    if 'user_id' not in session:
        return "❌ Not logged in"
    
    try:
        connection = get_db_connection()
        if not connection:
            return "❌ Database connection failed"
        
        cursor = connection.cursor()
        
        # Try to insert a simple test item
        cursor.execute("""
            INSERT INTO cart (Customer_ID, Med_Code, quantity, total_price) 
            VALUES (%s, 'TEST001', 1, 10.00)
        """, (session['user_id'],))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return "✅ Test item added to cart successfully!"
        
    except Exception as e:
        import traceback
        return f"❌ Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>"

@app.route('/test_cart_table')
def test_cart_table():
    """Test if cart table exists and is accessible"""
    try:
        connection = get_db_connection()
        if not connection:
            return "❌ Database connection failed"
        
        cursor = connection.cursor()
        
        # Test if cart table exists
        cursor.execute("SHOW TABLES LIKE 'cart'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            return "❌ Cart table does not exist"
        
        # Test cart table structure
        cursor.execute("DESCRIBE cart")
        columns = cursor.fetchall()
        
        # Test if we can query the cart table
        cursor.execute("SELECT COUNT(*) FROM cart")
        count = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return f"✅ Cart table exists with {len(columns)} columns and {count} items<br>Columns: {[col[0] for col in columns]}"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

@app.route('/test_route')
def test_route():
    return "Test route works!"

@app.route('/proceed_checkout')
def proceed_checkout():
    """Redirect to payment page from cart"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('payment_page'))

@app.route('/debug_payment_error')
def debug_payment_error():
    """Comprehensive payment debugging to catch exact error"""
    if 'user_id' not in session:
        return "Please <a href='/test_login'>login first</a>"
    
    connection = get_db_connection()
    if not connection:
        return "❌ Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Step 1: Check customer exists
        print(f"DEBUG: Checking customer {session['user_id']}")
        cursor.execute("SELECT Customer_ID, Name FROM customer WHERE Customer_ID = %s", (session['user_id'],))
        customer = cursor.fetchone()
        
        if not customer:
            return f"❌ Customer {session['user_id']} not found in database"
        
        # Step 2: Check cart items
        cursor.execute("""
            SELECT SUM(c.total_price) as total, COUNT(*) as item_count
            FROM cart c 
            WHERE c.Customer_ID = %s
        """, (session['user_id'],))
        
        cart_result = cursor.fetchone()
        total_amount = cart_result[0] if cart_result and cart_result[0] else 0
        item_count = cart_result[1] if cart_result else 0
        
        if total_amount <= 0:
            return f"❌ Cart is empty. Total: {total_amount}, Items: {item_count}"
        
        # Step 3: Check payment table structure
        cursor.execute("DESCRIBE payment")
        payment_columns = [col[0] for col in cursor.fetchall()]
        
        # Step 4: Try payment insert with detailed error catching
        import random, string
        payment_id = 'PAY' + ''.join(random.choices(string.digits, k=6))
        customer_id_str = str(session['user_id'])
        payment_type = 'Cash on Delivery'
        
        html = f"""
        <h1>Payment Debug Results</h1>
        <h3>✅ Customer Check:</h3>
        <p>Customer ID: {customer[0]}, Name: {customer[1]}</p>
        
        <h3>✅ Cart Check:</h3>
        <p>Total Amount: ৳{total_amount:.2f}, Items: {item_count}</p>
        
        <h3>✅ Payment Table Columns:</h3>
        <p>{', '.join(payment_columns)}</p>
        
        <h3>Payment Insert Test:</h3>
        <p>Trying to insert: ID={payment_id}, Customer={customer_id_str}, Amount={total_amount}, Type={payment_type}</p>
        """
        
        try:
            cursor.execute("""
                INSERT INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (payment_id, customer_id_str, total_amount, payment_type, None))
            
            html += "<p style='color: green;'>✅ Payment insert SUCCESS!</p>"
            connection.rollback()  # Don't save test data
            
        except Exception as insert_error:
            html += f"<p style='color: red;'>❌ Payment insert FAILED: {str(insert_error)}</p>"
            html += f"<p style='color: red;'>Error type: {type(insert_error).__name__}</p>"
            
            import traceback
            html += f"<pre style='color: red;'>{traceback.format_exc()}</pre>"
            connection.rollback()
        
        return html
        
    except Exception as e:
        import traceback
        return f"<h1>Debug Error</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"
    finally:
        cursor.close()
        connection.close()

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

@app.route('/test_payment_form')
def test_payment_form():
    """Simple test form to submit payment"""
    return '''
    <h1>Test Payment Form</h1>
    <form method="POST" action="/process_payment">
        <p>
            <input type="radio" name="payment_method" value="Cash on Delivery" checked>
            <label>Cash on Delivery</label>
        </p>
        <p>
            <input type="radio" name="payment_method" value="Online Payment">
            <label>Online Payment</label>
        </p>
        <button type="submit">Submit Payment</button>
    </form>
    <p><a href="/test_login">Login First</a> | <a href="/add_test_item">Add Test Item</a></p>
    '''

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

@app.route('/test_payment_processing')
def test_payment_processing():
    """Test payment processing with simulated form data"""
    if 'user_id' not in session:
        return "Please login first"
    
    # Simulate form data
    payment_method = 'Cash on Delivery'
    
    print(f"DEBUG: Test payment processing for user {session['user_id']}")
    print(f"DEBUG: Payment method: {payment_method}")
    
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        print(f"DEBUG: Processing payment for user {session['user_id']}")
        print(f"DEBUG: Payment method selected: {payment_method}")
        
        # Calculate total from cart using same method as cart view
        cursor.execute("""
            SELECT SUM(c.total_price) as total
            FROM cart c 
            WHERE c.Customer_ID = %s
        """, (session['user_id'],))
        
        result = cursor.fetchone()
        total_amount = result[0] if result and result[0] else 0
        
        print(f"DEBUG: Calculated total amount: {total_amount}")
        
        if total_amount <= 0:
            return "Cart is empty"
        
        # Generate unique payment ID
        import random, string
        payment_id = 'PAY' + ''.join(random.choices(string.digits, k=6))
        
        print(f"DEBUG: Generated payment ID: {payment_id}")
        
        # Save payment record to existing payment table
        print(f"DEBUG: Inserting payment record...")
        
        try:
            # First check if payment_id already exists
            cursor.execute("SELECT COUNT(*) FROM payment WHERE payment_id = %s", (payment_id,))
            if cursor.fetchone()[0] > 0:
                # Generate a new payment ID if collision
                payment_id = 'PAY' + ''.join(random.choices(string.digits, k=8))
                print(f"DEBUG: Payment ID collision, generated new ID: {payment_id}")
            
            # Convert values to ensure proper types
            customer_id_str = str(session['user_id'])
            total_amount_decimal = float(total_amount)
            payment_type_str = str(payment_method)
            
            print(f"DEBUG: Inserting - ID: {payment_id}, Customer: {customer_id_str}, Amount: {total_amount_decimal}, Type: {payment_type_str}")
            
            cursor.execute("""
                INSERT INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (payment_id, customer_id_str, total_amount_decimal, payment_type_str, None))
            
            print(f"DEBUG: Payment record inserted successfully")
            
        except Exception as insert_error:
            print(f"DEBUG: Insert error details: {str(insert_error)}")
            raise insert_error
        
        # Clear cart after successful payment
        print(f"DEBUG: Clearing cart for user {session['user_id']}")
        cursor.execute("DELETE FROM cart WHERE Customer_ID = %s", (session['user_id'],))
        
        connection.commit()
        print(f"DEBUG: Transaction committed successfully")
        
        return f"<h1>Payment Successful!</h1><p>Payment ID: {payment_id}</p><p>Amount: ৳{total_amount:.2f}</p><p>Method: {payment_method}</p>"
        
    except Exception as e:
        print(f"Payment processing error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        connection.rollback()
        return f"<h1>Payment Failed</h1><p>Error: {str(e)}</p><pre>{traceback.format_exc()}</pre>"
    finally:
        cursor.close()
        connection.close()

@app.route('/debug_amounts')
def debug_amounts():
    """Debug route to compare cart and payment amounts"""
    if 'user_id' not in session:
        return "Please login first"
    
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get cart items with detailed info
        cursor.execute("""
            SELECT c.Cart_ID, c.Med_Code, c.quantity, c.total_price,
                   m.Name as Med_Name, m.Price as unit_price
            FROM cart c 
            JOIN medicine m ON c.Med_Code = m.Med_Code
            WHERE c.Customer_ID = %s
            ORDER BY c.Cart_ID DESC
        """, (session['user_id'],))
        
        cart_items = cursor.fetchall()
        
        # Calculate totals
        cart_total = sum(item['total_price'] for item in cart_items)
        
        html = f"""
        <h1>Amount Debug</h1>
        <h2>User ID: {session['user_id']}</h2>
        <h3>Cart Items:</h3>
        <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr><th>Name</th><th>Unit Price</th><th>Quantity</th><th>Stored Total</th><th>Calculated Total</th></tr>
        """
        
        for item in cart_items:
            calculated_total = item['unit_price'] * item['quantity']
            html += f"""
            <tr>
                <td>{item['Med_Name']}</td>
                <td>৳{item['unit_price']:.2f}</td>
                <td>{item['quantity']}</td>
                <td>৳{item['total_price']:.2f}</td>
                <td>৳{calculated_total:.2f}</td>
            </tr>
            """
        
        html += f"""
        </table>
        <h3>Total Amounts:</h3>
        <p><strong>Cart Total (from stored total_price): ৳{cart_total:.2f}</strong></p>
        <p><a href="/view_cart">View Cart</a> | <a href="/payment_page">Payment Page</a></p>
        """
        
        return html
        
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        cursor.close()
        connection.close()

@app.route('/create_test_deliveryman')
def create_test_deliveryman():
    """Create test delivery men for testing assignment functionality"""
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Check if delivery men already exist
        cursor.execute("SELECT COUNT(*) FROM deliveryman")
        count = cursor.fetchone()[0]
        
        if count > 0:
            return f"<h3>Delivery men already exist ({count} found)</h3><p><a href='/admin_payments'>Go to Payment Management</a></p>"
        
        # Create test delivery men
        test_deliverymen = [
            ('DM001', 'John Smith', '01712345678', 'john.smith@email.com', 'Dhaka'),
            ('DM002', 'Ahmed Hassan', '01798765432', 'ahmed.hassan@email.com', 'Chittagong'),
            ('DM003', 'Rahim Khan', '01555123456', 'rahim.khan@email.com', 'Sylhet')
        ]
        
        for dm in test_deliverymen:
            cursor.execute("""
                INSERT INTO deliveryman (DeliveryMan_ID, Name, Phone, Email, Area) 
                VALUES (%s, %s, %s, %s, %s)
            """, dm)
        
        connection.commit()
        
        return f"""
        <h3>✅ Test delivery men created successfully!</h3>
        <ul>
            <li>John Smith (DM001) - 01712345678 - Dhaka</li>
            <li>Ahmed Hassan (DM002) - 01798765432 - Chittagong</li>
            <li>Rahim Khan (DM003) - 01555123456 - Sylhet</li>
        </ul>
        <p><a href='/admin_payments' class='btn btn-success'>Go to Payment Management</a></p>
        """
        
    except Exception as e:
        connection.rollback()
        return f"<h3>Error creating delivery men:</h3><p>{str(e)}</p>"
    finally:
        cursor.close()
        connection.close()

@app.route('/test_admin_login')
def test_admin_login():
    """Simulate admin login for testing"""
    session['user_id'] = 'ADMIN001'
    session['user_type'] = 'admin'
    session['user_name'] = 'Test Admin'
    return redirect(url_for('admin_dashboard'))

@app.route('/test_login')
def test_login():
    """Simulate login for testing - use a real customer ID from database"""
    connection = get_db_connection()
    if not connection:
        return "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Get the first available customer from the database
        cursor.execute("SELECT Customer_ID, Name FROM customer LIMIT 1")
        customer = cursor.fetchone()
        
        if customer:
            session['user_id'] = customer[0]
            session['user_type'] = 'customer'
            session['user_name'] = customer[1]
            return f"<h1>Test Login Successful!</h1><p>Logged in as: {customer[1]} (ID: {customer[0]})</p><p><a href='/customer_dashboard'>Go to Dashboard</a></p>"
        else:
            return "<h1>No customers found in database</h1><p>Please create a customer first.</p>"
            
    except Exception as e:
        return f"<h1>Login Error</h1><p>{str(e)}</p>"
    finally:
        cursor.close()
        connection.close()

@app.route('/debug_test')
def debug_test():
    """Simple debug test"""
    return "<h1>Debug Test Works!</h1><p>Server is responding correctly.</p>"

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

@app.route('/payment_page')
def payment_page():
    """Display payment page with cart items and payment options"""
    if 'user_id' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login'))
    
    print(f"DEBUG: Payment page accessed by user {session['user_id']}")
    
    connection = get_db_connection()
    if not connection:
        # Fallback test data if database fails
        cart_items = [
            {
                'name': 'Sample Medicine',
                'quantity': 1,
                'unit_price': 20.00,
                'total': 20.00
            }
        ]
        total_amount = 20.00
        print("DEBUG: Using fallback data due to database connection failure")
    else:
        try:
            cursor = connection.cursor(dictionary=True)
            # Get cart items for the user - same query as cart view
            cursor.execute("""
                SELECT c.Cart_ID, c.Med_Code, c.quantity, c.total_price,
                       m.Name as Med_Name, m.Price as unit_price
                FROM cart c 
                JOIN medicine m ON c.Med_Code = m.Med_Code
                WHERE c.Customer_ID = %s
                ORDER BY c.Cart_ID DESC
            """, (session['user_id'],))
            
            cart_results = cursor.fetchall()
            
            cart_items = []
            total_amount = 0
            
            for item in cart_results:
                cart_items.append({
                    'name': item['Med_Name'],
                    'quantity': item['quantity'], 
                    'unit_price': float(item['unit_price']),
                    'total': float(item['total_price'])
                })
                total_amount += float(item['total_price'])
            
            cursor.close()
            connection.close()
            
            print(f"DEBUG: Loaded {len(cart_items)} items from database")
            
        except Exception as e:
            print(f"Database error in payment_page: {e}")
            # Fallback data
            cart_items = [
                {
                    'name': 'Sample Medicine',
                    'quantity': 1,
                    'unit_price': 20.00,
                    'total': 20.00
                }
            ]
            total_amount = 20.00
    
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

@app.route('/process_payment', methods=['POST'])
def process_payment():
    """Process payment and save to database"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    payment_type = request.form.get('payment_method')
    
    if not payment_type:
        flash("Please select a payment method", "error")
        return redirect(url_for('payment_page'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('payment_page'))
    
    try:
        cursor = connection.cursor()
        
        print(f"DEBUG: Processing payment for user {session['user_id']}")
        print(f"DEBUG: Payment method selected: {payment_type}")
        
        # Calculate total from cart using same method as cart view
        cursor.execute("""
            SELECT SUM(c.total_price) as total
            FROM cart c 
            WHERE c.Customer_ID = %s
        """, (session['user_id'],))
        
        result = cursor.fetchone()
        total_amount = result[0] if result and result[0] else 0
        
        print(f"DEBUG: Calculated total amount: {total_amount}")
        
        if total_amount <= 0:
            print("DEBUG: Cart is empty, redirecting to dashboard")
            flash("Cart is empty", "error")
            return redirect(url_for('customer_dashboard'))
        
        # Generate unique payment ID
        import random, string
        payment_id = 'PAY' + ''.join(random.choices(string.digits, k=6))
        
        print(f"DEBUG: Generated payment ID: {payment_id}")
        
        # Save payment record to existing payment table
        print(f"DEBUG: Inserting payment record...")
        
        try:
            # First check if payment_id already exists
            cursor.execute("SELECT COUNT(*) FROM payment WHERE payment_id = %s", (payment_id,))
            if cursor.fetchone()[0] > 0:
                # Generate a new payment ID if collision
                payment_id = 'PAY' + ''.join(random.choices(string.digits, k=8))
                print(f"DEBUG: Payment ID collision, generated new ID: {payment_id}")
            
            # Convert values to ensure proper types
            customer_id_str = str(session['user_id'])
            total_amount_decimal = float(total_amount)
            payment_type_str = str(payment_type)
            
            print(f"DEBUG: Inserting - ID: {payment_id}, Customer: {customer_id_str}, Amount: {total_amount_decimal}, Type: {payment_type_str}")
            
            cursor.execute("""
                INSERT INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (payment_id, customer_id_str, total_amount_decimal, payment_type_str, None))
            
            print(f"DEBUG: Payment record inserted successfully")
            
        except Exception as insert_error:
            print(f"DEBUG: Insert error details: {str(insert_error)}")
            raise insert_error
        
        # Award points for successful purchase
        # Points calculation: 1 point for every 10 BDT spent (rounded down)
        points_earned = int(total_amount_decimal // 10)
        
        if points_earned > 0:
            print(f"DEBUG: Awarding {points_earned} points for purchase of ৳{total_amount_decimal}")
            
            # Add points to customer's account
            cursor.execute("""
                UPDATE customer 
                SET points = points + %s 
                WHERE Customer_ID = %s
            """, (points_earned, customer_id_str))
            
            # Log the points transaction
            cursor.execute("""
                INSERT INTO points_history (customer_id, points_earned, transaction_type, payment_id, description, created_at)
                VALUES (%s, %s, 'earned', %s, %s, NOW())
            """, (customer_id_str, points_earned, payment_id, f"Purchase reward: {points_earned} points for ৳{total_amount_decimal} purchase"))
            
            print(f"DEBUG: Points awarded successfully")
            # Update the flash message to include points earned
            flash(f"Payment successful! Payment ID: {payment_id}. You earned {points_earned} points!", "success")
        else:
            flash(f"Payment successful! Payment ID: {payment_id}", "success")
        
        # Clear cart after successful payment
        print(f"DEBUG: Clearing cart for user {session['user_id']}")
        cursor.execute("DELETE FROM cart WHERE Customer_ID = %s", (session['user_id'],))
        
        connection.commit()
        print(f"DEBUG: Transaction committed successfully")
        
        return redirect(url_for('customer_dashboard'))
        
    except Exception as e:
        print(f"Payment processing error: {e}")
        connection.rollback()
        flash("Payment failed. Please try again.", "error")
        return redirect(url_for('payment_page'))
    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    app.run(debug=True)
