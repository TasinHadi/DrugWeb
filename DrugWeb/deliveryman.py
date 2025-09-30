from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Create deliveryman blueprint
deliveryman_bp = Blueprint('deliveryman', __name__, url_prefix='/deliveryman')

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

@deliveryman_bp.route('/dashboard')
def dashboard():
    """Deliveryman dashboard"""
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
            
        except Exception as e:
            print(f"Error fetching assigned payments: {e}")
            flash("Error loading assigned payments", "error")
        finally:
            connection.close()
    
    return render_template('deliveryman_dashboard.html', 
                         assigned_payments=assigned_payments)

@deliveryman_bp.route('/handle_delivery', methods=['POST'])
def handle_delivery():
    """Handle delivery acceptance or decline"""
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

@deliveryman_bp.route('/profile')
def profile():
    """Deliveryman profile page"""
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
            
        except Exception as e:
            flash(f'Error loading profile: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('deliveryman_profile.html', deliveryman_info=deliveryman_info)