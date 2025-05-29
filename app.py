from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db_setup import create_tables, createStaff, get_db_connection, createAdmin
import sqlite3
import os

# Initial setup
create_tables()
# createAdmin()
# createStaff()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Upload config
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Check if the file is valid
def allowed_file(filename):
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Home for customers
@app.route('/')
def chome():
    if 'user_id' in session:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "SELECT subscribed, username FROM Customers WHERE id = ?",
            (session['user_id'], ))
        user = cursor.fetchone()

        is_premium = user['subscribed'] == 1 if user else False
        username = user['username']

        if is_premium or session['role'] == 'admin':
            cursor.execute("SELECT * FROM Recipes WHERE status = 'approved'")
        else:
            cursor.execute(
                "SELECT * FROM Recipes WHERE status = 'approved' AND isPremium = 0"
            )
        recipes = cursor.fetchall()

        cursor.execute("SELECT recipe_id FROM Favorites WHERE customer_id = ?",
                       (session['user_id'], ))
        favorite_ids = {row['recipe_id'] for row in cursor.fetchall()}

        db.close()

        return render_template('customer/chome.html',
                               username=username,
                               is_premium=is_premium,
                               recipes=recipes,
                               favorite_ids=favorite_ids)

    flash("You must be logged in to access the home page", "warning")
    return redirect(url_for('login'))


@app.route('/search')
def search():
    if 'user_id' not in session or session['role'] != 'customer':
        flash("Please log in to search recipes.", "danger")
        return redirect(url_for('login'))

    query = request.args.get('q', '').strip()

    if not query:
        flash("Enter a keyword to search.", "warning")
        return redirect(url_for('chome'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        '''
        SELECT id, title, image, ingredients, instructions, duration, courseType, isPremium
        FROM Recipes
        WHERE (title LIKE ? OR ingredients LIKE ?)
          AND (isPremium = 0 OR (
              isPremium = 1 AND EXISTS (
                  SELECT 1 FROM Customers WHERE id = ? AND subscribed = 1
              )
          ))
          AND title IS NOT NULL
          AND courseType IS NOT NULL
          AND status != 'rejected'  -- Exclude rejected recipes
        ORDER BY createdAt DESC
        ''', (f'%{query}%', f'%{query}%', session['user_id']))

    results = cursor.fetchall()
    print(results)
    db.close()

    # Replace None titles with a placeholder in the results
    for recipe in results:
        if recipe['title'] is None:
            recipe['title'] = "Untitled Recipe"

    # Check if customer is premium
    is_premium = False
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT subscribed FROM Customers WHERE id = ?",
                   (session['user_id'], ))
    user = cursor.fetchone()
    if user and user['subscribed'] == 1:
        is_premium = True
    db.close()

    return render_template('customer/chome.html',
                           recipes=results,
                           is_premium=is_premium)


@app.route('/recipe/<int:recipe_id>')
def view_recipe_customer(recipe_id):
    if 'user_id' not in session or session['role'] != 'customer':
        flash("Unauthorized access. Please log in as a customer.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM Recipes WHERE id = ?", (recipe_id, ))
    recipe = cursor.fetchone()

    if not recipe:
        db.close()
        flash("Recipe not found.", "warning")
        return redirect(url_for('chome'))

    if recipe['isPremium'] == 1:
        cursor.execute("SELECT subscribed FROM Customers WHERE id = ?",
                       (session['user_id'], ))
        user = cursor.fetchone()
        if not user or user['subscribed'] == 0:
            db.close()
            flash("This recipe is only available to Premium members.",
                  "danger")
            return redirect(url_for('chome'))

    cursor.execute(
        '''
        SELECT Comments.*, Customers.username
        FROM Comments
        JOIN Customers ON Comments.commentor_id = Customers.id
        WHERE recipe_id = ?
        ORDER BY commentedAt DESC
    ''', (recipe_id, ))
    comments = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) as like_count FROM Likes WHERE recipe_id = ?",
        (recipe_id, ))
    like_count = cursor.fetchone()['like_count']

    cursor.execute(
        "SELECT * FROM Likes WHERE customer_id = ? AND recipe_id = ?",
        (session['user_id'], recipe_id))
    liked = cursor.fetchone() is not None

    cursor.execute("SELECT recipe_id FROM Favorites WHERE customer_id = ?",
                   (session['user_id'], ))
    favorite_ids = {row['recipe_id'] for row in cursor.fetchall()}

    db.close()

    return render_template('customer/view_recipe.html',
                           recipe=recipe,
                           comments=comments,
                           like_count=like_count,
                           liked=liked,
                           favorite_ids=favorite_ids,
                           user_id=session['user_id'])


@app.route('/recipe/<int:recipe_id>/like', methods=['POST'])
def like_recipe(recipe_id):
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM Likes WHERE customer_id = ? AND recipe_id = ?",
        (session['user_id'], recipe_id))
    liked = cursor.fetchone()

    if liked:
        cursor.execute(
            "DELETE FROM Likes WHERE customer_id = ? AND recipe_id = ?",
            (session['user_id'], recipe_id))
    else:
        cursor.execute(
            "INSERT INTO Likes (customer_id, recipe_id) VALUES (?, ?)",
            (session['user_id'], recipe_id))

    db.commit()
    db.close()
    return redirect(url_for('view_recipe_customer', recipe_id=recipe_id))


@app.route('/recipe/<int:recipe_id>/comment', methods=['POST'])
def add_comment(recipe_id):
    if 'user_id' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))

    comment = request.form['comment'].strip()
    if not comment:
        flash("Comment cannot be empty.", "warning")
        return redirect(url_for('view_recipe_customer', recipe_id=recipe_id))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO Comments (comment, commentor_id, recipe_id) VALUES (?, ?, ?)",
        (comment, session['user_id'], recipe_id))
    db.commit()
    db.close()

    flash("Comment added successfully!", "success")
    return redirect(url_for('view_recipe_customer', recipe_id=recipe_id))


@app.route('/recipe/<int:recipe_id>/delete_comment/<int:comment_id>',
           methods=['POST'])
def delete_comment(recipe_id, comment_id):
    if 'user_id' not in session or session['role'] != 'customer':
        flash("Unauthorized access. Please log in as a customer.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM Comments WHERE id = ? AND commentor_id = ?",
                   (comment_id, session['user_id']))
    comment = cursor.fetchone()

    if comment:
        cursor.execute("DELETE FROM Comments WHERE id = ?", (comment_id, ))
        db.commit()
        flash("Comment deleted successfully.", "success")
    else:
        flash("You are not authorized to delete this comment.", "danger")

    db.close()
    return redirect(url_for('view_recipe_customer', recipe_id=recipe_id))


@app.route('/favorite/<int:recipe_id>', methods=['POST'])
def toggle_favorite(recipe_id):
    if 'user_id' not in session:
        flash("You must be logged in to manage favorites.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id FROM Favorites WHERE customer_id = ? AND recipe_id = ?",
        (session['user_id'], recipe_id))
    favorite = cursor.fetchone()

    if favorite:
        cursor.execute(
            "DELETE FROM Favorites WHERE customer_id = ? AND recipe_id = ?",
            (session['user_id'], recipe_id))
        db.commit()
        flash("Recipe removed from favorites.", "success")
    else:
        cursor.execute(
            "INSERT INTO Favorites (customer_id, recipe_id) VALUES (?, ?)",
            (session['user_id'], recipe_id))
        db.commit()
        flash("Recipe added to favorites.", "success")

    db.close()

    return redirect(url_for('view_recipe_customer', recipe_id=recipe_id))


@app.route('/favorites')
def favorites():
    if 'user_id' not in session:
        flash("You must be logged in to view your favorites.", "warning")
        return redirect(url_for('login'))

    customer_id = session['user_id']

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        '''
        SELECT Recipes.* FROM Recipes
        JOIN Favorites ON Recipes.id = Favorites.recipe_id
        WHERE Favorites.customer_id = ?
    ''', (customer_id, ))

    favorite_recipes = cursor.fetchall()
    db.close()

    return render_template('customer/favorites.html', recipes=favorite_recipes)


@app.route('/ahome')
def ahome():
    if 'username' in session:
        db = get_db_connection()
        cursor = db.cursor()

        # Get user info
        cursor.execute(
            "SELECT subscribed, username FROM Customers WHERE id = ?",
            (session['user_id'], ))
        user = cursor.fetchone()

        is_premium = user['subscribed'] == 1 if user else False
        username = user['username']

        # Recipe filtering
        if is_premium or session['role'] == 'admin':
            cursor.execute("SELECT * FROM Recipes WHERE status = 'approved'")
        else:
            cursor.execute("SELECT * FROM Recipes WHERE status = 'approved' AND isPremium = 0")
        recipes = cursor.fetchall()

        # count queries
        cursor.execute("SELECT COUNT(*) FROM Customers")
        user_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Staff")
        staff_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Recipes WHERE status = 'approved'")
        approved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Recipes WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]

        db.close()

        return render_template(
            'admin/ahome.html',
            username=username,
            is_premium=is_premium,
            recipes=recipes,
            user_count=user_count,
            staff_count=staff_count,
            approved_count=approved_count,
            pending_count=pending_count
        )

    return redirect(url_for('login'))



# Home for staff
@app.route('/shome')
def shome():
    if 'user_id' not in session or session['role'] != 'staff':
        flash("Unauthorized access. Please log in as staff.", "danger")
        return redirect(url_for('login'))
    return redirect(url_for('view_status', status='pending'))


# Add recipe (GET/POST)
@app.route('/staff/add', methods=['GET', 'POST'])
def add_recipe():
    if 'user_id' not in session or session['role'] != 'staff':
        flash("Unauthorized access. Please log in as staff.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']

        # Get lists from form and join them with commas
        ingredients_list = request.form.getlist('ingredients[]')
        instructions_list = request.form.getlist('instructions[]')

        ingredients = ', '.join([item.strip() for item in ingredients_list if item.strip()])
        instructions = ', '.join([item.strip() for item in instructions_list if item.strip()])

        duration = request.form['duration']
        course_type = request.form['course_type']
        is_premium = 1 if 'isPremium' in request.form else 0

        allowed_course_types = [
            "Appetizer", "Beverage", "Dessert", "Main Course", "Salad", "Soup"
        ]
        if course_type not in allowed_course_types:
            flash("Invalid course type selected.", "danger")
            return redirect(url_for('add_recipe'))

        image_file = request.files['image']
        image_filename = None

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Make filename unique if needed
            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(filepath):
                filename = f"{base}_{counter}{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                counter += 1

            image_file.save(filepath)
            image_filename = filename
        else:
            flash("Invalid or missing image file.", "danger")
            return redirect(url_for('add_recipe'))

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            '''
            INSERT INTO Recipes (title, ingredients, instructions, duration, courseType, isPremium, image, staff_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (title, ingredients, instructions, duration, course_type,
             is_premium, image_filename, session['user_id'])
        )
        db.commit()
        db.close()

        flash("Recipe submitted for approval.", "success")
        return redirect(url_for('add_recipe'))

    return render_template('staff/add_recipe.html')



# View recipes by status (staff only)
@app.route('/staff/status/<status>')
def view_status(status):
    if 'user_id' not in session or session['role'] != 'staff':
        flash("Unauthorized access. Please log in as staff.", "danger")
        return redirect(url_for('login'))

    if status not in ['approved', 'pending', 'rejected']:
        flash("Invalid status category.", "danger")
        return redirect(url_for('shome'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute(
        '''
        SELECT * FROM Recipes
        WHERE status = ? AND staff_id = ?
        ORDER BY createdAt DESC
        ''', (status, session['user_id']))
    recipes = cursor.fetchall()
    db.close()

    return render_template('staff/status.html', recipes=recipes, status=status)


@app.route('/staff/recipe/<int:recipe_id>')
def view_staff_recipe(recipe_id):
    if 'user_id' not in session or session['role'] != 'staff':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Recipes WHERE id = ? AND staff_id = ?",
                   (recipe_id, session['user_id']))
    recipe = cursor.fetchone()
    db.close()

    if not recipe:
        flash("Recipe not found or access denied.", "warning")
        return redirect(url_for('shome'))

    return render_template('staff/view_recipe.html', recipe=recipe)

@app.route('/admin/status/<status>')
def admin_view_status(status):
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    if status not in ['approved', 'pending', 'rejected']:
        flash("Invalid status filter.", "danger")
        return redirect(url_for('chome'))

    db = get_db_connection()
    cursor = db.cursor()

    # Join Recipes with Staff to get staff name
    cursor.execute("""
        SELECT Recipes.id, Recipes.title, Recipes.isPremium, Recipes.createdAt,
               Staff.name AS staff_name
        FROM Recipes
        JOIN Staff ON Recipes.staff_id = Staff.id
        WHERE Recipes.status = ?
    """, (status,))

    recipes = cursor.fetchall()
    db.close()

    return render_template('admin/status.html', recipes=recipes, status=status)

@app.route('/admin/recipe/<int:recipe_id>')
def view_recipe(recipe_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    # Get recipe
    cursor.execute("SELECT * FROM Recipes WHERE id = ?", (recipe_id,))
    recipe = cursor.fetchone()

    if not recipe:
        db.close()
        flash("Recipe not found.", "danger")
        return redirect(url_for('admin_view_status', status='pending'))

    cursor.execute('''
        SELECT Comments.comment, Comments.commentedAt, Customers.name
        FROM Comments
        JOIN Customers ON Comments.commentor_id = Customers.id
        WHERE Comments.recipe_id = ?
        ORDER BY Comments.commentedAt DESC
    ''', (recipe_id,))
    comments = cursor.fetchall()

    db.close()
    return render_template('admin/view_recipe.html', recipe=recipe, comments=comments)

@app.route('/admin/recipes/<int:recipe_id>/approve')
def approve_recipe(recipe_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE Recipes SET status = 'approved' WHERE id = ?",
                   (recipe_id, ))
    db.commit()
    db.close()

    flash("Recipe approved.", "success")
    return redirect(request.referrer
                    or url_for('admin_status', status='pending'))


@app.route('/admin/recipes/<int:recipe_id>/reject')
def reject_recipe(recipe_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE Recipes SET status = 'rejected' WHERE id = ?",
                   (recipe_id, ))
    db.commit()
    db.close()

    flash("Recipe rejected.", "info")
    return redirect(request.referrer
                    or url_for('admin_status', status='pending'))


@app.route('/admin/create_staff', methods=['GET', 'POST'])
def create_staff():
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access. Please log in as admin.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('create_staff'))

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM Staff WHERE username = ?", (username, ))
        if cursor.fetchone():
            flash("Username already exists!", "danger")
            db.close()
            return redirect(url_for('create_staff'))

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO Staff (name, username, password) VALUES (?, ?, ?)",
            (name, username, hashed_password))
        db.commit()
        db.close()

        flash("Staff account created successfully!", "success")
        return redirect(url_for('create_staff'))

    return render_template('admin/create_staff.html')


@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM Customers WHERE subscribed = 1")
    subscribed_users = cursor.fetchall()

    cursor.execute("SELECT * FROM Customers WHERE subscribed = 0")
    unsubscribed_users = cursor.fetchall()

    cursor.execute("SELECT * FROM Customers WHERE isBanned = 1")
    banned_users = cursor.fetchall()

    db.close()

    return render_template('admin/users.html',
                           subscribed_users=subscribed_users,
                           unsubscribed_users=unsubscribed_users,
                           banned_users=banned_users)


@app.route('/admin/ban_user', methods=['POST'])
def ban_user():
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    user_id = request.form['user_id']

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("UPDATE Customers SET isBanned = 1 WHERE id = ?",
                   (user_id, ))
    db.commit()
    db.close()

    flash("User has been banned.", "info")
    return redirect(url_for('admin_users'))


@app.route('/admin/unban_user', methods=['POST'])
def unban_user():
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    user_id = request.form['user_id']

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("UPDATE Customers SET isBanned = 0 WHERE id = ?",
                   (user_id, ))
    db.commit()
    db.close()

    flash("User has been unbanned.", "success")
    return redirect(url_for('admin_users'))


@app.route('/admin/inbox')
def admin_inbox():
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Contact_Us ORDER BY createdAt DESC")
    messages = cursor.fetchall()
    db.close()

    return render_template('admin/inbox.html', messages=messages)


@app.route('/admin/inbox/delete/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM Contact_Us WHERE id = ?", (message_id, ))
    db.commit()
    db.close()

    flash("Message deleted successfully.", "success")
    return redirect(url_for('admin_inbox'))


# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


# Customer account settings
@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session or session['role'] != 'customer':
        flash("Please log in as a customer to access account settings.",
              "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    db = get_db_connection()
    cursor = db.cursor()

    if request.method == 'POST':
        new_name = request.form['name']
        new_username = request.form['username']
        new_email = request.form['email']
        current_password = request.form.get('current_password', '')
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        cursor.execute("SELECT * FROM Customers WHERE id = ?", (user_id, ))
        user = cursor.fetchone()

        if new_password or current_password:
            if not check_password_hash(user['password'], current_password):
                flash("Current password is incorrect or empty.", "danger")
                db.close()
                return redirect(url_for('account'))

            if new_password and new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                db.close()
                return redirect(url_for('account'))

            if new_password:
                hashed_password = generate_password_hash(new_password)
                cursor.execute(
                    "UPDATE Customers SET password = ? WHERE id = ?",
                    (hashed_password, user_id))

        cursor.execute(
            "UPDATE Customers SET name = ?, username = ?, email = ? WHERE id = ?",
            (new_name, new_username, new_email, user_id))
        session['username'] = new_username
        session['name'] = new_name
        session['email'] = new_email

        db.commit()
        db.close()
        flash("Account updated successfully!", "success")
        return redirect(url_for('account'))

    cursor.execute("SELECT name, username, email FROM Customers WHERE id = ?",
                   (user_id, ))
    user = cursor.fetchone()
    db.close()

    return render_template('customer/account.html', user=user)


# Contact Us
@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        customer_id = session.get(
            'user_id') if 'user_id' in session and session.get(
                'role') == 'customer' else None

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            '''
            INSERT INTO Contact_Us (customer_id, name, email, subject, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (customer_id, name, email, subject, message))
        db.commit()
        db.close()

        flash("Thank you for reaching out! We'll get back to you soon.",
              "success")
        return redirect(url_for('contact_us'))

    return render_template('customer/contact_us.html')


# Premium Subscription
@app.route('/premium', methods=['GET', 'POST'])
def premium():
    if 'username' not in session or session['role'] != 'customer':
        flash("You must be logged in as a customer to access this page.",
              "danger")
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT subscribed FROM Customers WHERE id = ?",
                   (session['user_id'], ))
    user = cursor.fetchone()
    subscribed = user['subscribed'] if user else 0

    if request.method == 'POST' and subscribed == 0:
        cursor.execute("UPDATE Customers SET subscribed = 1 WHERE id = ?",
                       (session['user_id'], ))
        db.commit()
        db.close()
        flash("You have successfully subscribed to Premium!", "success")
        return redirect(url_for('chome'))

    db.close()

    return render_template('customer/premium.html',
                           subscribed=subscribed,
                           username=session['username'])


# Sign Up
@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('sign_up'))

        hashed_password = generate_password_hash(password)

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM Customers WHERE username = ?",
                       (username, ))
        if cursor.fetchone():
            flash("Username already exists!", "danger")
            db.close()
            return redirect(url_for('sign_up'))

        cursor.execute("SELECT * FROM Customers WHERE email = ?", (email, ))
        if cursor.fetchone():
            flash("Email already registered!", "danger")
            db.close()
            return redirect(url_for('sign_up'))

        cursor.execute(
            "INSERT INTO Customers (name, username, email, password) VALUES (?, ?, ?, ?)",
            (full_name, username, email, hashed_password))
        customer_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO plainPass (customer_id, password) VALUES (?, ?)",
            (customer_id, password))
        db.commit()
        db.close()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('auth/sign_up.html')


# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_or_username = request.form['emailOrUsername']
        password = request.form['password']
        role = request.form['role']

        db = get_db_connection()
        cursor = db.cursor()

        if role == 'admin':
            cursor.execute("SELECT * FROM Managers WHERE username = ?",
                           (email_or_username, ))
        elif role == 'staff':
            cursor.execute("SELECT * FROM Staff WHERE username = ?",
                           (email_or_username, ))
        else:
            cursor.execute(
                "SELECT * FROM Customers WHERE username = ? OR email = ?",
                (email_or_username, email_or_username))

        user = cursor.fetchone()

        if user:
            if role == 'customer' and user['isBanned']:

                print("Role: ", role)
                print("isBanned: ", user['isBanned'])
                flash("Your account has been banned.", "danger")
                db.close()
                return redirect(url_for('login'))

            stored_password = user[2] if role == 'admin' else user[4]
            username_from_db = user[1] if role == 'admin' else user[2]

            if check_password_hash(stored_password, password):
                session['user_id'] = user[0]
                session['role'] = role
                session['username'] = username_from_db
                session['name'] = user[1]

                if role == 'admin':
                    return redirect(url_for('ahome'))
                elif role == 'staff':
                    return redirect(url_for('shome'))
                else:
                    return redirect(url_for('chome'))
            else:
                flash("Incorrect password.", "danger")
        else:
            flash("User not found.", "danger")

        db.close()

    return render_template('auth/login.html')


# Serve uploaded images
@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5173, debug=True)
