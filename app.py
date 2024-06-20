from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import sys
from PIL import Image
import pytesseract
import argparse
import cv2
import sqlite3

__author__ = ''
__source__ = ''

app = Flask(__name__)

# Reference code: https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun
# Create a SQLite database and table
conn = sqlite3.connect('data/data.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS book_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        page INTEGER,
        book TEXT
    )
''')
conn.commit()
conn.close()

UPLOAD_FOLDER = './static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# Endpoint to get all users
@app.route('/show', methods=['GET'])
def get_users():
    conn = sqlite3.connect('data/data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM book_index')
    indexes = cursor.fetchall()
    conn.close()
    return jsonify({'indexes': indexes})

# Endpoint to add a user
@app.route('/add')
def add_user():
    try:
        # Get user data from the request
        title = "dhanoop"
        page = "37"

        # Validate user input
        if not title or not page:
            return jsonify({'error': 'Name and age are required'}), 400

        # Insert user into the database
        conn = sqlite3.connect('data/data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO book_index (title, page) VALUES (?, ?)', (title, page))
        conn.commit()
        conn.close()

        return jsonify({'message': 'User added successfully'}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/")
def index():
  return render_template("index.html")

@app.route("/about")
def about():
  return render_template("about.html")

@app.route('/uploader', methods = ['GET', 'POST'])
def upload_file():
   if request.method == 'POST':
      f = request.files['file']

      # create a secure filename
      filename = secure_filename(f.filename)

      # save file to /static/uploads
      filepath = os.path.join(app.config['UPLOAD_FOLDER'],filename)
      f.save(filepath)
      
      # load the example image and convert it to grayscale
      image = cv2.imread(filepath)
      gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
      
      # apply thresholding to preprocess the image
      gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

      # apply median blurring to remove any blurring
      gray = cv2.medianBlur(gray, 3)

      # save the processed image in the /static/uploads directory
      ofilename = os.path.join(app.config['UPLOAD_FOLDER'],"{}.png".format(os.getpid()))
      cv2.imwrite(ofilename, gray)
      
      # perform OCR on the processed image
      text = pytesseract.image_to_string(Image.open(ofilename))
      
      # remove the processed image
      os.remove(ofilename)

      file = open('extracted_text.txt', 'w')
      file.write(text)
      file.close()

      # Using readlines()
      file1 = open('extracted_text.txt', 'r')
      Lines = file1.readlines()
      count = 0

      # Strips the newline character
      for line in Lines:
        if line.strip() != "":
            count += 1
            data = line.strip().split(",")
            print("Line{}: {}".format(count, data))

      os.remove('extracted_text.txt')

      return render_template("uploaded.html", displaytext=text, fname=filename)

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(debug=True, host='0.0.0.0', port=port)
