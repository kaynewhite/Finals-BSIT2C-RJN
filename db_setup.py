from werkzeug.security import generate_password_hash
import sqlite3


def get_db_connection():
  conn = sqlite3.connect('RecipeHub.db')
  conn.row_factory = sqlite3.Row
  return conn


def createStaff():
  db = get_db_connection()
  cursor = db.cursor()

  hashed_pw = generate_password_hash("ronron123")

  cursor.execute(
      '''
    INSERT INTO Staff (name, username, email, password)
    VALUES (?, ?, ?, ?)
    ''', ("Christian", "Notary", "christian.notario@lspu.edu.ph", hashed_pw))

  db.commit()
  db.close()


def createAdmin():
  db = get_db_connection()
  cursor = db.cursor()

  hashed_pw = generate_password_hash("ronronpogisabuongworld")

  cursor.execute(
      '''
    INSERT INTO Managers (username, password)
    VALUES (?, ?)
    ''', ("Ronnie", hashed_pw))

  db.commit()
  db.close()


def create_tables():

  db = get_db_connection()
  cursor = db.cursor()

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Customers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      username TEXT,
      email TEXT,
      password TEXT,
      isBanned INTEGER DEFAULT 0,
      subscribed INTEGER DEFAULT 0,
      subscribedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Staff (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      username TEXT,
      email TEXT,
      password TEXT
    )''')

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Managers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT,
      password TEXT
    )''')

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Recipes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT,
      image TEXT,
      ingredients TEXT,
      instructions TEXT,
      duration INTEGER,
      isPremium INTEGER DEFAULT 0,
      status TEXT DEFAULT 'pending',
      staff_id INTEGER,
      createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (staff_id) REFERENCES Staff(id)
    )''')

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Favorites (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id INTEGER,
      recipe_id INTEGER,
      favoritedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (customer_id) REFERENCES Customers(id),
      FOREIGN KEY (recipe_id) REFERENCES Recipes(id)
    )''')

  cursor.execute('''
    CREATE TABLE IF NOT EXISTS Comments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      comment TEXT,
      commentor_id INTEGER,
      recipe_id INTEGER,
      commentedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (commentor_id) REFERENCES Customers(id),
      FOREIGN KEY (recipe_id) REFERENCES Recipes(id)
    )''')

  cursor.execute('''
  CREATE TABLE IF NOT EXISTS Contact_Us (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id INTEGER,
      name TEXT,
      email TEXT,
      subject TEXT,
      message TEXT,
      createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (customer_id) REFERENCES Customers(id)
  )
  ''')

  db.commit()
  db.close()


def update_table():
  db = get_db_connection()
  cursor = db.cursor()

  cursor.execute('''
  ALTER TABLE Customers ADD subscribedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
''')

  db.commit()
  db.close()
