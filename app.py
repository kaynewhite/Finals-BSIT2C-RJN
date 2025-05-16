from flask import Flask, render_template, send_from_directory, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db_setup import create_tables, get_db_connection, createAdmin
import sqlite3
import os

create_tables()
# createAdmin()

app = Flask(__name__)
app.secret_key = os.urandom(24)


@app.route('/')
def chome():
  if 'username' in session:
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT subscribed, username FROM Customers WHERE id = ?",
                   (session['user_id'], ))
    user = cursor.fetchone()
    db.close()

    is_premium = user['subscribed'] == 1 if user else False
    username = user['username']
    return render_template('chome.html',
                           username=username,
                           is_premium=is_premium)

  return redirect(url_for('login'))


@app.route('/logout')
def logout():
  session.clear()
  flash("You have been logged out.", "info")
  return redirect(url_for('login'))


@app.route('/account', methods=['GET', 'POST'])
def account():
  if 'user_id' not in session or session['role'] != 'customer':
    flash("Please log in as a customer to access account settings.", "warning")
    return redirect(url_for('login'))

  user_id = session['user_id']
  db = get_db_connection()
  cursor = db.cursor()

  if request.method == 'POST':
    new_name = request.form['name']
    new_username = request.form['username']
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # Get current user info
    cursor.execute("SELECT * FROM Customers WHERE id = ?", (user_id, ))
    user = cursor.fetchone()

    if not check_password_hash(user[4], current_password):
      flash("Current password is incorrect.", "danger")
      db.close()
      return redirect(url_for('account'))

    cursor.execute("UPDATE Customers SET name = ?, username = ? WHERE id = ?",
                   (new_name, new_username, user_id))
    session['username'] = new_username

    if new_password and confirm_password:
      if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        db.close()
        return redirect(url_for('account'))
      hashed_password = generate_password_hash(new_password)
      cursor.execute("UPDATE Customers SET password = ? WHERE id = ?",
                     (hashed_password, user_id))

    db.commit()
    db.close()
    flash("Account updated successfully!", "success")
    return redirect(url_for('account'))

  cursor.execute("SELECT name, username FROM Customers WHERE id = ?",
                 (user_id, ))
  user = cursor.fetchone()
  db.close()

  return render_template('account.html', user=user)


@app.route('/contact_us', methods=['GET', 'POST'])
def contact_us():
  if request.method == 'POST':
    name = request.form['name']
    email = request.form['email']
    subject = request.form['subject']
    message = request.form['message']

    print(f"Message from {name} ({email}) — {subject}: {message}")
    flash("Thank you for reaching out! We'll get back to you soon.", "success")
    return redirect(url_for('contact_us'))

  return render_template('contact_us.html')


@app.route('/premium', methods=['GET', 'POST'])
def premium():
  if 'username' not in session or session['role'] != 'customer':
    flash("You must be logged in as a customer to access this page.", "danger")
    return redirect(url_for('login'))

  if request.method == 'POST':
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE Customers SET subscribed = 1 WHERE id = ?",
                   (session['user_id'], ))
    db.commit()
    db.close()
    flash("You have successfully subscribed to Premium!", "success")
    return redirect(url_for('chome'))

  return render_template('premium.html', username=session['username'])


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

    cursor.execute("SELECT * FROM Customers WHERE username = ?", (username, ))
    existing_user = cursor.fetchone()

    if existing_user:
      flash("Username already exists!", "danger")
      db.close()
      return redirect(url_for('sign_up'))

    cursor.execute("SELECT * FROM Customers WHERE email = ?", (email, ))
    existing_email = cursor.fetchone()

    if existing_email:
      flash("Email already registered!", "danger")
      db.close()
      return redirect(url_for('sign_up'))

    cursor.execute(
        '''
            INSERT INTO Customers (name, username, email, password)
            VALUES (?, ?, ?, ?)
        ''', (full_name, username, email, hashed_password))

    db.commit()
    db.close()

    flash("Account created successfully! Please log in.", "success")
    return redirect(url_for('login'))

  return render_template('sign_up.html')


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
      cursor.execute("SELECT * FROM Customers WHERE username = ? OR email = ?",
                     (email_or_username, email_or_username))

    user = cursor.fetchone()

    if user:
      if role == 'admin':
        stored_password = user[2]
        username_from_db = user[1]
      elif role == 'staff':
        stored_password = user[4]
        username_from_db = user[2]
      else:
        stored_password = user[4]
        username_from_db = user[2]

      if check_password_hash(stored_password, password):
        session['user_id'] = user[0]
        session['role'] = role
        session['username'] = username_from_db
        session['name'] = user[1]

        if role == 'admin':
          return redirect(url_for('chome'))
        elif role == 'staff':
          return redirect(url_for('shome'))
        else:
          return redirect(url_for('chome'))
      else:
        flash('Incorrect password. Please try again.', 'error')
    else:
      flash('User not found. Please check your credentials.', 'error')

    db.close()

  return render_template('login.html')


# @app.route('/favorites')
# def favorites():
#     if 'user_id' not in session:
#         flash("You must be logged in to view your favorites.", "warning")
#         return redirect(url_for('login'))

#     customer_id = session['user_id']

#     db = get_db_connection()
#     cursor = db.cursor()

#     cursor.execute('''
#         SELECT Recipes.* FROM Recipes
#         JOIN Favorites ON Recipes.id = Favorites.recipe_id
#         WHERE Favorites.customer_id = ?
#     ''', (customer_id,))

#     favorite_recipes = cursor.fetchall()
#     db.close()

#     return render_template('favorites.html', recipes=favorite_recipes)

# @app.route('/add_to_favorites', methods=['POST'])
# def add_to_favorites():
#     if 'user_id' not in session:
#         flash("You must be logged in to favorite a recipe.", "warning")
#         return redirect(url_for('login'))

#     recipe_id = request.form['recipe_id']
#     customer_id = session['user_id']

#     db = get_db_connection()
#     cursor = db.cursor()

#     cursor.execute('''
#         SELECT * FROM Favorites WHERE customer_id = ? AND recipe_id = ?
#     ''', (customer_id, recipe_id))

#     existing_favorite = cursor.fetchone()

#     if existing_favorite:
#         flash("This recipe is already in your favorites!", "info")
#     else:
#         cursor.execute('''
#             INSERT INTO Favorites (customer_id, recipe_id)
#             VALUES (?, ?)
#         ''', (customer_id, recipe_id))
#         db.commit()
#         flash("Recipe added to favorites!", "success")

#     db.close()
#     return redirect(url_for('chome'))


@app.route('/images/<filename>')
def serve_image(filename):
  return send_from_directory('static/images', filename)


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
