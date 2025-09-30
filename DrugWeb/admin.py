from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error

# Create admin blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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

@admin_bp.route('/payments')
def admin_payments():
    """Admin view to see all customer payments"""
    if 'user_id' not in session or session['user_type'] != 'admin':
        flash('Please login as admin first!', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash("Database connection failed", "error")
        return redirect(url_for('admin.dashboard'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT p.payment_id, p.Customer_ID, p.amount, p.payment_type, p.DeliveryMan_ID,
                   CONCAT(u.F_name, ' ', u.L_name) as customer_name, u.phone as customer_phone, u.address as customer_address
            FROM payment p
            JOIN customer c ON p.Customer_ID = c.Customer_ID
            JOIN user u ON c.Customer_ID = u.ID
            ORDER BY p.payment_id DESC
        """)
        
        payments = cursor.fetchall()
        
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
        
        return render_template('admin_payments.html', 
                             payments=payments, 
                             deliverymen=deliverymen)
        
    except Exception as e:
        flash(f"Error loading payments: {str(e)}", "error")
        return redirect(url_for('admin.dashboard'))
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/assign_deliveryman', methods=['POST'])
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
        
        cursor.execute("""
            UPDATE payment 
            SET DeliveryMan_ID = %s 
            WHERE payment_id = %s
        """, (deliveryman_id, payment_id))
        
        if cursor.rowcount > 0:
            connection.commit()
            
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
        connection.rollback()
        return jsonify({'success': False, 'message': 'Database error occurred'})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/dashboard')
def dashboard():
    """Admin dashboard"""
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
            cursor.execute("SELECT * FROM medicine ORDER BY Med_Code")
            medicines = cursor.fetchall()
            
            cursor.execute("""
                SELECT cr.*, CONCAT(u.F_name, ' ', u.L_name) as customer_name
                FROM customer_review cr
                JOIN customer c ON cr.Customer_ID = c.Customer_ID
                JOIN user u ON c.Customer_ID = u.ID
            """)
            reviews = cursor.fetchall()
            
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
        
        cursor.close()
        connection.close()
    
    return render_template('admin_dashboard.html', 
                         medicines=medicines, 
                         reviews=reviews, 
                         requests=requests)

@admin_bp.route('/profile')
def profile():
    """Admin profile page"""
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
            
        except Exception as e:
            flash(f'Error loading profile: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('admin_profile.html', admin_info=admin_info)

@admin_bp.route('/handle_request', methods=['POST'])
def handle_request():
    """Handle customer medicine requests (accept/decline)"""
    if 'user_id' not in session or session['user_type'] != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access'})
    
    customer_id = request.json.get('customer_id')
    medicine_name = request.json.get('medicine_name')
    action = request.json.get('action')
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        try:
            try:
                cursor.execute("""
                    ALTER TABLE customer_request 
                    ADD COLUMN IF NOT EXISTS Status VARCHAR(20) DEFAULT 'Pending'
                """)
                connection.commit()
            except:
                pass
            
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
                cursor.execute("""
                    UPDATE customer_request 
                    SET Status = 'Accepted' 
                    WHERE Customer_ID = %s AND request_med_name = %s
                """, (customer_id, medicine_name))
                message = f'Request for {medicine_name} has been accepted successfully!'
                
            elif action == 'decline':
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

@admin_bp.route('/get_deliverymen', methods=['GET'])
def get_deliverymen():
    """Get list of available delivery men for assignment"""
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