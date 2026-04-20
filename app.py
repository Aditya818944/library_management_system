from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'library_secret_key_2024'

DB = 'library.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            serial_no TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT 'book'
        );
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            membership_no TEXT UNIQUE NOT NULL,
            expiry_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS book_issue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            member_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            remarks TEXT,
            returned INTEGER DEFAULT 0,
            FOREIGN KEY(book_id) REFERENCES books(id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS fine_pay (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            fine_amount REAL DEFAULT 0,
            fine_paid INTEGER DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(issue_id) REFERENCES book_issue(id)
        );
    ''')
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
        c.execute("INSERT INTO users (username, password, role) VALUES ('user', 'user123', 'user')")
    except:
        pass
    try:
        c.execute("INSERT INTO books (title, author, serial_no, type) VALUES ('Python Programming', 'Mark Lutz', 'BK001', 'book')")
        c.execute("INSERT INTO books (title, author, serial_no, type) VALUES ('Clean Code', 'Robert Martin', 'BK002', 'book')")
        c.execute("INSERT INTO books (title, author, serial_no, type) VALUES ('The Matrix', 'Wachowski', 'MV001', 'movie')")
        c.execute("INSERT INTO members (name, membership_no, expiry_date) VALUES ('Rahul Sharma', 'MEM001', '2025-12-31')")
        c.execute("INSERT INTO members (name, membership_no, expiry_date) VALUES ('Priya Singh', 'MEM002', '2025-06-30')")
    except:
        pass
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    books_issued = conn.execute("SELECT COUNT(*) FROM book_issue WHERE returned=0").fetchone()[0]
    total_members = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    pending_fines = conn.execute("SELECT COUNT(*) FROM fine_pay WHERE fine_paid=0 AND fine_amount>0").fetchone()[0]
    conn.close()
    return render_template('dashboard.html', total_books=total_books, books_issued=books_issued,
                           total_members=total_members, pending_fines=pending_fines)

@app.route('/book_available', methods=['GET', 'POST'])
def book_available():
    if 'user' not in session:
        return redirect(url_for('login'))
    books = []
    error = None
    searched = False
    if request.method == 'POST':
        action = request.form.get('action', 'search')
        if action == 'issue':
            selected_book_id = request.form.get('selected_book')
            if not selected_book_id:
                flash('Please select a book first.', 'warning')
            else:
                return redirect(url_for('book_issue', book_id=selected_book_id))
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        if not title and not author:
            error = 'Please enter a book title or author name to search.'
        else:
            searched = True
            conn = get_db()
            query = "SELECT * FROM books WHERE 1=1"
            params = []
            if title:
                query += " AND title LIKE ?"
                params.append(f'%{title}%')
            if author:
                query += " AND author LIKE ?"
                params.append(f'%{author}%')
            books = conn.execute(query, params).fetchall()
            conn.close()
    return render_template('book_available.html', books=books, error=error, searched=searched)

@app.route('/book_issue', methods=['GET', 'POST'])
def book_issue():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    books = conn.execute("SELECT * FROM books").fetchall()
    members = conn.execute("SELECT * FROM members").fetchall()
    today = datetime.today().strftime('%Y-%m-%d')
    default_return = (datetime.today() + timedelta(days=15)).strftime('%Y-%m-%d')
    preselect_book = request.args.get('book_id', '')

    if request.method == 'POST':
        book_id = request.form.get('book_id')
        member_id = request.form.get('member_id')
        issue_date = request.form.get('issue_date')
        return_date = request.form.get('return_date')
        remarks = request.form.get('remarks', '')
        errors = []
        if not book_id: errors.append('Book name is required.')
        if not member_id: errors.append('Member name is required.')
        if not issue_date: errors.append('Issue date is required.')
        if not return_date: errors.append('Return date is required.')
        if issue_date and issue_date < today: errors.append('Issue date cannot be less than today.')
        if issue_date and return_date:
            issue_dt = datetime.strptime(issue_date, '%Y-%m-%d')
            return_dt = datetime.strptime(return_date, '%Y-%m-%d')
            if return_dt < issue_dt: errors.append('Return date cannot be before issue date.')
            if (return_dt - issue_dt).days > 15: errors.append('Return date cannot be more than 15 days from issue date.')
        if errors:
            for e in errors: flash(e, 'danger')
        else:
            conn.execute("INSERT INTO book_issue (book_id, member_id, issue_date, return_date, remarks) VALUES (?,?,?,?,?)",
                         (book_id, member_id, issue_date, return_date, remarks))
            conn.commit()
            flash('Book issued successfully!', 'success')
            conn.close()
            return redirect(url_for('book_issue'))
    conn.close()
    return render_template('book_issue.html', books=books, members=members,
                           today=today, default_return=default_return, preselect_book=preselect_book)

@app.route('/return_book', methods=['GET', 'POST'])
def return_book():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    issues = conn.execute("""
        SELECT bi.*, b.title, b.author, b.serial_no, m.name as member_name
        FROM book_issue bi
        JOIN books b ON bi.book_id = b.id
        JOIN members m ON bi.member_id = m.id
        WHERE bi.returned = 0
    """).fetchall()
    if request.method == 'POST':
        issue_id = request.form.get('issue_id')
        return_date = request.form.get('return_date')
        serial_no = request.form.get('serial_no')
        errors = []
        if not issue_id: errors.append('Please select a book to return.')
        if not serial_no: errors.append('Serial number is mandatory.')
        if not return_date: errors.append('Return date is required.')
        if errors:
            for e in errors: flash(e, 'danger')
        else:
            issue = conn.execute("SELECT * FROM book_issue WHERE id=?", (issue_id,)).fetchone()
            original_return = datetime.strptime(issue['return_date'], '%Y-%m-%d')
            actual_return = datetime.strptime(return_date, '%Y-%m-%d')
            fine = 0
            if actual_return > original_return:
                days_late = (actual_return - original_return).days
                fine = days_late * 2
            conn.execute("DELETE FROM fine_pay WHERE issue_id=?", (issue_id,))
            conn.execute("INSERT INTO fine_pay (issue_id, fine_amount) VALUES (?,?)", (issue_id, fine))
            conn.commit()
            conn.close()
            return redirect(url_for('fine_pay', issue_id=issue_id))
    conn.close()
    return render_template('return_book.html', issues=issues)

@app.route('/fine_pay/<int:issue_id>', methods=['GET', 'POST'])
def fine_pay(issue_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    fine_record = conn.execute("SELECT * FROM fine_pay WHERE issue_id=? ORDER BY id DESC LIMIT 1", (issue_id,)).fetchone()
    issue = conn.execute("""
        SELECT bi.*, b.title, b.author, b.serial_no, m.name as member_name
        FROM book_issue bi JOIN books b ON bi.book_id=b.id JOIN members m ON bi.member_id=m.id
        WHERE bi.id=?
    """, (issue_id,)).fetchone()
    if request.method == 'POST':
        fine_paid = 1 if request.form.get('fine_paid') else 0
        remarks = request.form.get('remarks', '')
        if fine_record['fine_amount'] > 0 and not fine_paid:
            flash('You must check "Fine Paid" before completing the return.', 'danger')
        else:
            conn.execute("UPDATE fine_pay SET fine_paid=?, remarks=? WHERE issue_id=?", (fine_paid, remarks, issue_id))
            conn.execute("UPDATE book_issue SET returned=1 WHERE id=?", (issue_id,))
            conn.commit()
            flash('Book returned successfully!', 'success')
            conn.close()
            return redirect(url_for('return_book'))
    conn.close()
    return render_template('fine_pay.html', fine=fine_record, issue=issue)

@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        serial_no = request.form.get('serial_no', '').strip()
        book_type = request.form.get('type', 'book')
        errors = []
        if not title: errors.append('Title is required.')
        if not author: errors.append('Author is required.')
        if not serial_no: errors.append('Serial number is required.')
        if errors:
            for e in errors: flash(e, 'danger')
        else:
            try:
                conn = get_db()
                conn.execute("INSERT INTO books (title, author, serial_no, type) VALUES (?,?,?,?)",
                             (title, author, serial_no, book_type))
                conn.commit()
                conn.close()
                flash('Book added successfully!', 'success')
                return redirect(url_for('add_book'))
            except:
                flash('Serial number already exists.', 'danger')
    return render_template('add_book.html')

@app.route('/update_book', methods=['GET', 'POST'])
def update_book():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db()
    books = conn.execute("SELECT * FROM books").fetchall()
    if request.method == 'POST':
        book_id = request.form.get('book_id')
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        serial_no = request.form.get('serial_no', '').strip()
        book_type = request.form.get('type', 'book')
        errors = []
        if not book_id: errors.append('Please select a book.')
        if not title: errors.append('Title is required.')
        if not author: errors.append('Author is required.')
        if not serial_no: errors.append('Serial number is required.')
        if errors:
            for e in errors: flash(e, 'danger')
        else:
            conn.execute("UPDATE books SET title=?, author=?, serial_no=?, type=? WHERE id=?",
                         (title, author, serial_no, book_type, book_id))
            conn.commit()
            flash('Book updated successfully!', 'success')
            conn.close()
            return redirect(url_for('update_book'))
    conn.close()
    return render_template('update_book.html', books=books)

@app.route('/user_management', methods=['GET', 'POST'])
def user_management():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    if request.method == 'POST':
        user_type = request.form.get('user_type', 'new')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'user')
        if not username:
            flash('Name is mandatory.', 'danger')
        else:
            if user_type == 'new':
                try:
                    conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (username, password, role))
                    conn.commit()
                    flash('User added successfully!', 'success')
                except:
                    flash('Username already exists.', 'danger')
            else:
                conn.execute("UPDATE users SET password=?, role=? WHERE username=?", (password, role, username))
                conn.commit()
                flash('User updated successfully!', 'success')
            conn.close()
            return redirect(url_for('user_management'))
    conn.close()
    return render_template('user_management.html', users=users)

@app.route('/update_membership', methods=['GET', 'POST'])
def update_membership():
    if 'user' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    member = None
    if request.method == 'POST':
        action = request.form.get('action')
        membership_no = request.form.get('membership_no', '').strip()
        duration = request.form.get('duration', '6')
        if not membership_no:
            flash('Membership number is mandatory.', 'danger')
        else:
            conn = get_db()
            member = conn.execute("SELECT * FROM members WHERE membership_no=?", (membership_no,)).fetchone()
            if not member:
                flash('Membership number not found.', 'danger')
            elif action == 'extend':
                months = int(duration)
                expiry = datetime.strptime(member['expiry_date'], '%Y-%m-%d')
                new_expiry = expiry + timedelta(days=30 * months)
                conn.execute("UPDATE members SET expiry_date=? WHERE membership_no=?",
                             (new_expiry.strftime('%Y-%m-%d'), membership_no))
                conn.commit()
                flash(f'Membership extended by {months} months!', 'success')
            elif action == 'cancel':
                conn.execute("DELETE FROM members WHERE membership_no=?", (membership_no,))
                conn.commit()
                flash('Membership cancelled successfully.', 'success')
            conn.close()
            return redirect(url_for('update_membership'))
    return render_template('update_membership.html', member=member)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
