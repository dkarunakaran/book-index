from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import sys
from PIL import Image
import pytesseract
import argparse
import cv2
import sqlite3
import re

__author__ = ''
__source__ = ''

app = Flask(__name__)

# Reference code: https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun
# Create a SQLite database and table
conn = sqlite3.connect('data/data.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Book (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT
    )
''')
conn.commit()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS Indexes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        page TEXT,
        book_id INTEGER,
        CONSTRAINT fk_book  
        FOREIGN KEY (book_id) 
        REFERENCES Book(book_id) 
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
    cursor.execute('SELECT * FROM Indexes')
    indexes = cursor.fetchall()
    conn.close()
    return render_template("show.html", indexes=indexes)


@app.route("/")
def index():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title FROM Book') 
  books = cursor.fetchall()
  conn.close()
  return render_template("index.html", books=books)

@app.route("/upload")
def upload():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title FROM Book') 
  books = cursor.fetchall()
  conn.close()
  return render_template("upload.html", books=books)

@app.route("/search", methods = ['GET', 'POST'])
def search():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title FROM Book') 
  books = cursor.fetchall()

  if request.method == 'POST' and request.form['keyword'] != "" :
      keyword = request.form['keyword'].strip().lower()
      query = f"SELECT i.page, b.title FROM Indexes i INNER JOIN Book b ON i.book_id=b.id WHERE i.keyword LIKE '%{keyword}%'"
      cursor.execute(query)
      results = cursor.fetchall()
      conn.close()
      return render_template("search.html", books=books, indexes=results)
  else:
     conn.close()
     return render_template("search.html", books=books)


def contains_any_letter_regex(data):
  """Checks if the data string contains any letters (a-z or A-Z) using regex.

  Args:
    data: The string to check.

  Returns:
    True if the data contains at least one letter, False otherwise.
  """

  pattern = r"[a-zA-Z]+"  # Matches one or more letters
  return bool(re.search(pattern, data))

@app.route('/uploader', methods = ['GET', 'POST'])
def upload_file():
   if request.form['book'] != "" and request.method == 'POST':
      
      f = request.files['file']

      book = request.form['book'].lower()

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

      conn = sqlite3.connect('data/data.db')
      cursor = conn.cursor()
      query = f"SELECT id FROM Book where title LIKE '{book}%' LIMIT 1"
      cursor.execute(query)
      book_id = cursor.fetchall()
    
      if len(book_id) == 0:
        cursor.execute("""INSERT INTO Book (title) VALUES (?)""", [book])
        conn.commit()
        query = f"SELECT id FROM Book where title LIKE '{book}%' LIMIT 1"
        cursor.execute(query)
        book_id = cursor.fetchall()
        book_id = book_id[0][0]
      else:
        book_id = book_id[0][0]

    
      # Using readlines()
      file1 = open('extracted_text.txt', 'r')
      Lines = file1.readlines()
      count = 0

      # Strips the newline character
      for line in Lines:
        if line.strip() != "":
            index_name = None
            index_page = []
            count += 1
            data = line.strip().split(",")
            for item in data:
               item = item.strip()
               if contains_any_letter_regex(item) and index_name is None:
                  index_name = item.strip()
               elif contains_any_letter_regex(item) is False:
                  index_page.append(item)
            for page in index_page:
               if index_name != None:
                  cursor.execute("""INSERT INTO Indexes (keyword, page, book_id) VALUES (?, ?, ?)""", [index_name.lower(), page, book_id])
                  conn.commit()     
            #print("Line{}: {}".format(count, data))

      os.remove('extracted_text.txt')

      conn = sqlite3.connect('data/data.db')
      cursor = conn.cursor()
      cursor.execute('SELECT id, title FROM Book') 
      books = cursor.fetchall()

      conn.close() 


      return render_template("uploaded.html", displaytext=text, fname=filename, bname=book, books=books)
   
   else:
      return render_template("error.html")
      

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(debug=True, host='0.0.0.0', port=port)
