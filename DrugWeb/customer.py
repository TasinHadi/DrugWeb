from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date, timedelta
import random
import string

# Create customer blueprint
customer_bp = Blueprint('customer', __name__, url_prefix='/customer')

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'drugweb',
    'user': 'root',
    'password': ''
}

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS drugweb")
        cursor.execute("USE drugweb")
        cursor.close()
        
        DB_CONFIG['database'] = 'drugweb'
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

@customer_bp.route('/dashboard')
def dashboard():
    """Customer dashboard"""
    if 'user_id' not in session or session['user_type'] != 'customer':
        flash('Please login as customer first!', 'error')
        return redirect(url_for('login'))
    
    # Get search and sort parameters
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
        
        # Build query based on search and sort
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

@customer_bp.route('/notifications')
def notifications():
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

@customer_bp.route('/points')
def points():
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

@customer_bp.route('/browse')
def browse_medicines():
    """Browse medicines with search, filter, and pagination"""
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

@customer_bp.route('/get_notifications')
def get_notifications():
    """Get notifications via AJAX"""
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

@customer_bp.route('/reviews', methods=['GET', 'POST'])
def reviews():
    """Customer reviews system"""
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

@customer_bp.route('/request_medicine', methods=['GET', 'POST'])
def request_medicine():
    """Request medicine system"""
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

@customer_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    """Customer profile management"""
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

@customer_bp.route('/all_notifications')
def all_notifications():
    """Show all customer notifications"""
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

# Cart Management Routes
@customer_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """Add item to cart"""
    
    if 'user_id' not in session or session['user_type'] != 'customer':
        return jsonify({'success': False, 'message': 'Please login as customer first'})
    
    try:
        data = request.json
        
        med_code = data.get('med_code')
        med_name = data.get('med_name')
        quantity = int(data.get('quantity', 1))
        price = float(data.get('price', 0))
        customer_id = session['user_id']
        
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

@customer_bp.route('/cart')
def view_cart():
    """Display the user's cart"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('customer.dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.Cart_ID, c.Med_Code, c.quantity, c.total_price,
                   m.Name as Med_Name, m.Price as unit_price
            FROM cart c 
            JOIN medicine m ON c.Med_Code = m.Med_Code
            WHERE c.Customer_ID = %s
            ORDER BY c.Cart_ID DESC
        """, (session['user_id'],))
        cart_items = cursor.fetchall()
        
        # Calculate total cart value
        total_cart_value = sum(item['total_price'] for item in cart_items)
        
        return render_template('cart.html', cart_items=cart_items, total_cart_value=total_cart_value)
        
    except Exception as e:
        print(f"Error fetching cart: {e}")
        flash("Error loading cart", "error")
        return redirect(url_for('customer.dashboard'))
    finally:
        cursor.close()
        connection.close()

@customer_bp.route('/update_cart_quantity', methods=['POST'])
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

@customer_bp.route('/remove_from_cart', methods=['POST'])
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

@customer_bp.route('/proceed_checkout')
def proceed_checkout():
    """Redirect to payment page from cart"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('customer.payment_page'))

@customer_bp.route('/payment_page')
def payment_page():
    """Display payment page with cart items and payment options"""
    if 'user_id' not in session:
        flash("Please login first", "error")
        return redirect(url_for('login'))
    
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

@customer_bp.route('/process_payment', methods=['POST'])
def process_payment():
    """Process payment and save to database"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    payment_type = request.form.get('payment_method')
    
    if not payment_type:
        flash("Please select a payment method", "error")
        return redirect(url_for('customer.payment_page'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('customer.payment_page'))
    
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
        
        if total_amount <= 0:
            flash("Cart is empty", "error")
            return redirect(url_for('customer.dashboard'))
        
        # Generate unique payment ID
        payment_id = 'PAY' + ''.join(random.choices(string.digits, k=6))
        
        # Save payment record to existing payment table
        
        try:
            # First check if payment_id already exists
            cursor.execute("SELECT COUNT(*) FROM payment WHERE payment_id = %s", (payment_id,))
            if cursor.fetchone()[0] > 0:
                # Generate a new payment ID if collision
                payment_id = 'PAY' + ''.join(random.choices(string.digits, k=8))
            
            # Convert values to ensure proper types
            customer_id_str = str(session['user_id'])
            total_amount_decimal = float(total_amount)
            payment_type_str = str(payment_type)
            
            cursor.execute("""
                INSERT INTO payment (payment_id, Customer_ID, amount, payment_type, DeliveryMan_ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (payment_id, customer_id_str, total_amount_decimal, payment_type_str, None))
            
        except Exception as insert_error:
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
            
            # Update the flash message to include points earned
            flash(f"Payment successful! Payment ID: {payment_id}. You earned {points_earned} points!", "success")
        else:
            flash(f"Payment successful! Payment ID: {payment_id}", "success")
        
        # Clear cart after successful payment
        cursor.execute("DELETE FROM cart WHERE Customer_ID = %s", (session['user_id'],))
        
        connection.commit()
        
        return redirect(url_for('customer.dashboard'))
        
    except Exception as e:
        connection.rollback()
        flash("Payment failed. Please try again.", "error")
        return redirect(url_for('customer.payment_page'))
    finally:
        cursor.close()
        connection.close()