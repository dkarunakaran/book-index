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
import pandas as pd
from collections import defaultdict

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
        title TEXT,
        author TEXT
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
@app.route('/show/<page_id>', methods=['GET'])
def get_show_page(page_id):
    conn = sqlite3.connect('data/data.db')
    cursor = conn.cursor()
    cursor.execute(f"select keyword, page FROM Indexes WHERE book_id={page_id} order by keyword ASC")
    result = cursor.fetchall()
    cursor.execute(f"SELECT id, title, author FROM Book where id={page_id}") 
    book = cursor.fetchall()
    conn.close()
    return render_template("show_page.html", book=book, result=result)

# Endpoint to get all books' indexes
@app.route('/show', methods=['GET'])
def get_show():
    conn = sqlite3.connect('data/data.db')
    cursor = conn.cursor()
    cursor.execute("select b.id as 'Book ID', b.title as 'Title', count(i.id) as 'Total Indexes' from Indexes i INNER join Book b on i.book_id=b.id GROUP by b.title order by b.title ASC")
    result = cursor.fetchall()
    conn.close()
    return render_template("show.html", result=result)


@app.route("/")
def index():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title, author FROM Book') 
  books = cursor.fetchall()
  conn.close()
  return render_template("index.html", books=books)

@app.route("/upload")
def upload():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title, author FROM Book') 
  books = cursor.fetchall()
  conn.close()
  return render_template("upload.html", books=books)

@app.route("/search", methods = ['GET', 'POST'])
def search():
  conn = sqlite3.connect('data/data.db')
  cursor = conn.cursor()
  cursor.execute('SELECT id, title, author FROM Book') 
  books = cursor.fetchall()
  # Defining a dict
  d = defaultdict(list)
  if request.method == 'POST' and request.form['keyword'] != "" :
      keyword = request.form['keyword'].strip().lower()
      query = f"SELECT b.id, i.page, b.title FROM Indexes i INNER JOIN Book b ON i.book_id=b.id WHERE i.keyword LIKE '%{keyword}%' ORDER BY b.title ASC, i.page"
      cursor.execute(query)
      results = cursor.fetchall()
      conn.close()
      for _, page, title in results:
         if page is "" or page in d[title]:
            continue
         d[title].append(page)

      return render_template("search.html", books=books, results=d)
  else:
     conn.close()
     return render_template("search.html", books=books, results=d)


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
      author = request.form['author']

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
        cursor.execute("""INSERT INTO Book (title, author) VALUES (?,?)""", [book, author])
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
            index_name = []
            index_page = []
            count += 1
            data = line.strip().split(",")
            for item in data:
               item = item.strip()
               if contains_any_letter_regex(item):
                  index_name.append(item.strip())
               elif contains_any_letter_regex(item) is False:
                  index_page.append(item)
            if len(index_name) > 0:
              separator = ' ' 
              index_name_joined = separator.join(index_name)
              for page in index_page: 
                  cursor.execute("""INSERT INTO Indexes (keyword, page, book_id) VALUES (?, ?, ?)""", [index_name_joined.lower(), page, book_id])
                  conn.commit()     
            #print("Line{}: {}".format(count, data))

      os.remove('extracted_text.txt')

      conn = sqlite3.connect('data/data.db')
      cursor = conn.cursor()
      cursor.execute('SELECT id, title, author FROM Book') 
      books = cursor.fetchall()

      conn.close() 


      return render_template("uploaded.html", displaytext=text, fname=filename, bname=book, books=books, aname=author)
   
   else:
      return render_template("error.html")
      

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(debug=True, host='0.0.0.0', port=port)
