import csv
import io
import os
import re
import sqlite3 as sql

from flask import Flask, flash, make_response, redirect, render_template, request, session, url_for
from flask_mail import Mail, Message
from flask_session import Session
from functools import wraps
from random import randint
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.wrappers import Response

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure mail (Ref: CS50 Week 9 Notes)
# Use os.getenv() to avoid inserting sensitive info in the code (Ref: https://www.reddit.com/r/flask/comments/2v5j2y/question_about_osenvironget_when_using_flaskmail/)
app = Flask(__name__)
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_PORT"] = 587
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
mail = Mail(app)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Connect to database
conn = sql.connect('service.db')
cur = conn.cursor()

# Define function for requiring login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (session.get("student_number") is None) and (session.get("teacher_id") is None):
            flash("Please log in first.")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


# To create a variable that can be passed into layout.html (https://flask.palletsprojects.com/en/2.0.x/templating/#context-processors)
@app.context_processor
def check_identity():
    if session.get("student_number"):
        cur.execute("SELECT * FROM students WHERE student_number = ?", [session["student_number"]])
        rows = cur.fetchall()
        identity = rows[0][1] + "(" + str(rows[0][2]) + ")" + " " + rows[0][4] + " " + rows[0][3]
    elif session.get("teacher_id"):
        cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
        rows = cur.fetchall()
        identity = rows[0][2]
    else:
        identity = "Not signed in"
    return dict(identity=identity)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/teacher_login", methods=["GET", "POST"])
def teacher_login():
    # User reaches the route via GET: Go to the page for logging in
    if request.method == "GET":
        # Forget any user id (de facto log out)
        session.clear()
        return render_template("teacher_login.html")

    # User POST information
    else:
        # Handle Login ID
        login_id = request.form.get("login_id")
        if not login_id:
            flash("Please provide Login ID.")
            return render_template("teacher_login.html")
        # Query database for account information of the username
        cur.execute("SELECT * FROM teachers WHERE login_id = ?", [login_id])
        rows = cur.fetchall()

        # Ensure valid login ID
        if len(rows) != 1 or rows[0][6]:
            flash("Invalid Login ID.")
            return render_template("teacher_login.html")

        # Get password
        password = request.form.get("password")
        # If the password is only the default personal code i.e. a six-digit integer:
        try:
            # Check if the personal code is correct
            if int(password) == int(rows[0][3]):
                session["teacher_id"] = rows[0][0]
                return render_template("teacher_createpw.html")
            else:
                flash("Invalid personal code.")
                return render_template("teacher_login.html")
        # If password already exists i.e. the "hash" cannot be cast to be an integer:
        except ValueError:
            # Check if the password is correct
            if check_password_hash(rows[0][3], password) == False:
                flash("Invalid password.")
                return render_template("teacher_login.html")
            else:
                session["teacher_id"] = rows[0][0]
                flash("Login successful. Welcome back!")
                return redirect(url_for("index"))


@app.route("/teacher_createpw", methods=["GET", "POST"])
@login_required
def teacher_createpw():
    # User reaches the route via GET: Go to the page for logging in
    if request.method == "GET":
        # Forget any user id (de facto log out)
        session.clear()
        return render_template("teacher_login.html")

    # User POST information
    else:
        error = None

        # Get password created by the user
        password = request.form.get("password")
        if not password:
            error = "Creating a password is a must."

        # Ensure requirement fulfillment (at least one letter and one number)
        counter_letter = 0
        counter_number = 0
        for i in range(len(password)):
            if password[i].isalpha() == True:
                counter_letter += 1
            if password[i].isdecimal() == True:
                counter_number += 1
        if (counter_letter == 0) or (counter_number == 0):
            error = "Password does not fulfill all the requirements. Please create another password."

        # Handle password confirmation
        confirm_pw = request.form.get("confirm_pw")
        if not confirm_pw:
            error = "Please confirm your password."
        if confirm_pw != password:
            error = "Password not matched. Please double-check your password."

        # If error:
        if error != None:
            return render_template("teacher_createpw.html", error=error)
        # If no error: Hash the password and add it into the teachers table
        else:
            hashed_pw = generate_password_hash(confirm_pw, method='pbkdf2:sha256', salt_length=8)
            conn = sql.connect('service.db')
            cur = conn.cursor()
            cur.execute("UPDATE teachers SET hash = ? WHERE teacher_id = ?", [hashed_pw, session["teacher_id"]])
            conn.commit()
            flash("Password created!")
            return redirect(url_for("index"))


@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    # User reaches the route via GET: Go to the page for logging in
    if request.method == "GET":
        # Forget any user id (de facto log out)
        session.clear()
        levels = "123456"
        class_codes = "ABCDE"
        return render_template("student_login.html", levels=levels, class_codes=class_codes)

    # User POST information
    else:
        # Handle Class and Class Number
        class_name = request.form.get("class_name")
        class_number = request.form.get("class_number")
        if (not class_name) or (not class_number):
            flash("Please provide your class and class number.")
            return render_template("student_login.html")
        # Query database for account information of the username
        conn = sql.connect('service.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE class = ? AND class_number = ?", [class_name, class_number])
        rows = cur.fetchall()

        # Ensure valid login ID
        if len(rows) != 1:
            flash("No such student.")
            levels = "123456"
            class_codes = "ABCDE"
            return render_template("student_login.html", levels=levels, class_codes=class_codes)

        # Get password
        password = request.form.get("password")
        # If the password is only the default personal code i.e. a six-digit integer:
        try:
            # Check if the personal code is correct
            if int(password) == int(rows[0][6]):
                session["student_number"] = rows[0][0]
                return render_template("student_createpw.html")
            else:
                flash("Invalid personal code.")
                levels = "123456"
                class_codes = "ABCDE"
                return render_template("student_login.html", levels=levels, class_codes=class_codes)
        # If password already exists i.e. the "hash" cannot be cast to be an integer:
        except ValueError:
            # Check if the password is correct
            if check_password_hash(rows[0][6], password) == False:
                flash("Invalid password.")
                levels = "123456"
                class_codes = "ABCDE"
                return render_template("student_login.html", levels=levels, class_codes=class_codes)
            else:
                session["student_number"] = rows[0][0]
                flash("Login successful. Welcome back!")
                return redirect(url_for("index"))


@app.route("/student_createpw", methods=["GET", "POST"])
@login_required
def student_createpw():
    # User reaches the route via GET: Go to the page for logging in
    if request.method == "GET":
        # Forget any user id (de facto log out)
        session.clear()
        flash("Login required.")
        levels = "123456"
        class_codes = "ABCDE"
        return render_template("student_login.html", levels=levels, class_codes=class_codes)

    # User POST information
    else:
        error = None

        # Get password created by the user
        password = request.form.get("password")
        if not password:
            error = "Creating a password is a must."

        # Ensure requirement fulfillment (at least one letter and one number)
        counter_letter = 0
        counter_number = 0
        for i in range(len(password)):
            if password[i].isalpha() == True:
                counter_letter += 1
            if password[i].isdecimal() == True:
                counter_number += 1
        if (counter_letter == 0) or (counter_number == 0):
            error = "Password does not fulfill all the requirements. Please create another password."

        # Handle password confirmation
        confirm_pw = request.form.get("confirm_pw")
        if not confirm_pw:
            error = "Please confirm your password."
        if confirm_pw != password:
            error = "Password not matched. Please double-check your password."

        # If error:
        if error != None:
            return render_template("student_createpw.html", error=error)
        # If no error: Hash the password and add it into the students table
        else:
            hashed_pw = generate_password_hash(confirm_pw, method='pbkdf2:sha256', salt_length=8)
            cur.execute("UPDATE students SET hash = ? WHERE student_number = ?", [hashed_pw, session["student_number"]])
            conn.commit()
            flash("Password created!")
            return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/add_int_record", methods=["GET", "POST"])
@login_required
def add_int_record():
    cur.execute("SELECT * FROM organisations WHERE disabled = ? ORDER BY org_name ASC", [0])
    organisations = cur.fetchall()
    levels = "123456"
    class_codes = "ABCDE"
    subjects = [
        "Art / Visual Arts",
        "Biology",
        "Business, Accounting and Financial Studies",
        "Chemistry",
        "Chinese History",
        "Chinese Language",
        "Chinese Literature",
        "Computer Literacy",
        "Economics",
        "English Language",
        "Geography",
        "Health Management and Social Care",
        "History",
        "Home Economics",
        "Information and Communication Technology",
        "Integrated Science",
        "Liberal Studies",
        "Life and Society",
        "Literature in English",
        "Mathematics",
        "Mathematics (M1)",
        "Mathematics (M2)",
        "Music",
        "Physical Education",
        "Physics",
        "Project Learning",
        "Putonghua",
        "Religious Education",
        "Tourism and Hospitality Studies"
        ]
    cur.execute("SELECT * FROM teachers WHERE disabled = ? AND teacher_id != ? ORDER BY name ASC", [0, 1])
    teachers = cur.fetchall()

    # User reached route via GET
    if request.method == "GET":
        # Check if the user has signed in as a teacher, not student
        if session.get("student_number") is None:
            flash("Please sign in as a student.")
            return redirect(url_for("index"))

        else:
            # Create select menu of organisations
            return render_template("add_int_record.html", organisations=organisations, levels=levels, class_codes=class_codes, subjects=subjects, teachers=teachers)

    # User POST information
    else:
        error = None

        # Get record data and check validity
        org_name = request.form.get("org_name")
        if not org_name:
            error = "Please select an organisation."

        # For "Others"
        if org_name == "Others":
            others = request.form.get("others")
            if not others:
                error = "Please specify the organisation / activity you worked for."
            post = request.form.get("post")
            if not post:
                error = "Please indicate your post."
            hours = request.form.get("hours")
            if not hours:
                error = "Please indicate the number of hours you have served."
            teacher = request.form.get("teacher")
            if not teacher:
                error = "Please specify the teacher responsible for your record."
            # Convert teacher name to be teacher's login id
            cur.execute("SELECT * FROM teachers WHERE name = ?", [teacher])
            rows = cur.fetchall()
            if len(rows) != 1:
                error = "Invalid teacher name."
            else:
                teacher_login_id = rows[0][1]
        # For "Subject Leader"
        if org_name == "Subject Leader":
            subject = request.form.get("subject")
            if not subject:
                error = "Please specify the subject you worked for."
            class_name = request.form.get("class_name")
            if not class_name:
                error = "Please specify the class you worked for."
            hours = request.form.get("hours")
            if not hours:
                error = "Please indicate the number of hours you have served."
            teacher = request.form.get("teacher")
            if not teacher:
                error = "Please specify the teacher responsible for your record."
            # Convert teacher name to be teacher's login id
            cur.execute("SELECT * FROM teachers WHERE name = ?", [teacher])
            rows = cur.fetchall()
            if len(rows) != 1:
                error = "Invalid teacher name."
            else:
                teacher_login_id = rows[0][1]
        # For normal club / society / team
        if (org_name != "Subject Leader") & (org_name != "Others"):
            post = request.form.get("post")
            if not post:
                error = "Please indicate your post."
            hours = request.form.get("hours")
            if not hours:
                error = "Please indicate the number of hours you have served."
            if hours.isdecimal() != True:
                error = "Number of hours should be a number. Do not include any words and other unnecessary characters."
            cur.execute("SELECT * FROM organisations WHERE org_name = ?", [org_name])
            rows = cur.fetchall()
            teacher_login_id = rows[0][2]

        # If error:
        if error != None:
            return render_template("add_int_record.html", error=error, organisations=organisations, levels=levels, class_codes=class_codes, subjects=subjects, teachers=teachers)
        # If no error: Add it into int_records table
        else:
            if (org_name != "Subject Leader") & (org_name != "Others"):
                cur.execute("INSERT INTO int_records (student_number, org_name, post, hours, teacher) VALUES (?, ?, ?, ?, ?)", [session["student_number"], org_name, post, int(hours), teacher_login_id])
                conn.commit()
                flash("Record added! Please continue to add other records if needed.")
                return redirect(url_for("myrecords"))
            elif org_name == "Others":
                cur.execute("INSERT INTO int_records (student_number, org_name, post, hours, teacher) VALUES (?, ?, ?, ?, ?)", [session["student_number"], others, post, int(hours), teacher_login_id])
                conn.commit()
                flash("Record added! Please continue to add other records if needed.")
                return redirect(url_for("myrecords"))
            else:
                cur.execute("INSERT INTO int_records (student_number, org_name, post, hours, subject, teacher) VALUES (?, ?, ?, ?, ?, ?)", [session["student_number"], org_name, class_name, int(hours), subject, teacher_login_id])
                conn.commit()
                flash("Record added! Please continue to add other records if needed.")
                return redirect(url_for("myrecords"))


@app.route("/add_ext_record", methods=["GET", "POST"])
@login_required
def add_ext_record():
    # User reached route via GET
    if request.method == "GET":
        # Check if the user has signed in as a teacher, not student
        if session.get("student_number") is None:
            flash("Please sign in as a student.")
            return redirect(url_for("index"))
        else:
            return render_template("add_ext_record.html")

    # User POST information
    else:
        error = None

        # Get record data and check validity
        org_name = request.form.get("org_name")
        if not org_name:
            error = "Please select an organisation."
        contact = request.form.get("contact")
        if not contact:
            error = "Please provide contact information of the external organisation / activity for school's verification."
        post = request.form.get("post")
        if not post:
            error = "Please indicate your post."
        hours = request.form.get("hours")
        if not hours:
            error = "Please indicate the number of hours you have served."
        if hours.isdecimal() != True:
            error = "Number of hours should be a number. Do not include any words and other unnecessary characters."

        # If error:
        if error != None:
            return render_template("add_ext_record.html", error=error)
        # If no error: Add it into ext_records table
        else:
            cur.execute("INSERT INTO ext_records (student_number, org_name, contact, post, hours) VALUES (?, ?, ?, ?, ?)", [session["student_number"], org_name, contact, post, int(hours)])
            conn.commit()
            flash("Record added! Please continue to add other records if needed.")
            return redirect(url_for("myrecords"))


@app.route("/myrecords", methods=["GET", "POST"])
@login_required
def myrecords():
    # User reached route via GET
    if request.method == "GET":
        # Check if the user has signed in as a teacher, not student
        if session.get("student_number") is None:
            flash("Please sign in as a student.")
            return redirect(url_for("index"))

        else:
            # Create two tables - one for internal records, one for external records
            cur.execute("SELECT * FROM int_records WHERE student_number = ?", [session["student_number"]])
            int_records = cur.fetchall()
            cur.execute("SELECT * FROM ext_records WHERE student_number = ?", [session["student_number"]])
            ext_records = cur.fetchall()
            # Obtain data about number of hours endorsed
            cur.execute("SELECT * FROM students WHERE student_number = ?", [session["student_number"]])
            rows = cur.fetchall()
            total_hours = rows[0][7]
            return render_template("myrecords.html", int_records=int_records, ext_records=ext_records, total_hours=total_hours)

    # User POST information
    else:
        # If the user deletes an internal service record
        if request.form.get("int_rec_id"):
            int_rec_id = request.form.get("int_rec_id")
            status = request.form.get("status")
            cur.execute("UPDATE int_records SET status = ? WHERE int_rec_id = ?", [status, int_rec_id])
            conn.commit()
            flash("Record deleted.")
            return redirect(url_for("myrecords"))
        # If the user deletes an external service record
        else:
            ext_rec_id = request.form.get("ext_rec_id")
            status = request.form.get("status")
            cur.execute("UPDATE ext_records SET status = ? WHERE ext_rec_id = ?", [status, ext_rec_id])
            conn.commit()
            flash("Record deleted.")
            return redirect(url_for("myrecords"))


@app.route("/review", methods=["GET", "POST"])
@login_required
def review():
    # User reached route via GET
    if request.method == "GET":
        # Check if the user has signed in as a student, not teacher
        if session.get("teacher_id") is None:
            flash("Please sign in as a teacher.")
            return redirect(url_for("index"))

        else:
            # Create a table of records for review
            cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
            rows = cur.fetchall()
            teacher_login_id = rows[0][1]
            cur.execute("SELECT int_rec_id, int_records.student_number, students.student_number, org_name, post, hours, status, subject, teacher, students.class, students.class_number, students.firstname, students.lastname FROM int_records INNER JOIN students ON int_records.student_number = students.student_number AND teacher = ? AND status != ? ORDER BY int_records.status ASC", [teacher_login_id, "deleted"])
            for_review = cur.fetchall()
            return render_template("review.html", for_review=for_review)

    # User POST information
    else:
        error = None

        int_rec_id = request.form.get("int_rec_id")
        hours = request.form.get("hours")
        status = request.form.get("status")

        cur.execute("SELECT * FROM int_records WHERE int_rec_id = ?", [int_rec_id])
        rows = cur.fetchall()
        old_status = rows[0][5]
        old_hours = rows[0][4]

        # If the student has not deleted the record:
        if old_status != "deleted":

            # Check if the hours input is valid
            if hours.isdecimal() != True:
                error = "Number of hours should be a number. Do not include any words and other unnecessary characters."
                cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                rows = cur.fetchall()
                teacher_login_id = rows[0][1]
                cur.execute("SELECT int_rec_id, int_records.student_number, students.student_number, org_name, post, hours, status, subject, teacher, students.class, students.class_number, students.firstname, students.lastname FROM int_records INNER JOIN students ON int_records.student_number = students.student_number AND teacher = ? AND status != ? ORDER BY int_records.status ASC", [teacher_login_id, "deleted"])
                for_review = cur.fetchall()
                return render_template("review.html", for_review=for_review, error=error)

            # If status is not changed
            if status == None:
                # If hours is also not changed
                if int(hours) == int(old_hours):
                    error = "There is no change!"
                    cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                    rows = cur.fetchall()
                    teacher_login_id = rows[0][1]
                    cur.execute("SELECT int_rec_id, int_records.student_number, students.student_number, org_name, post, hours, status, subject, teacher, students.class, students.class_number, students.firstname, students.lastname FROM int_records INNER JOIN students ON int_records.student_number = students.student_number AND teacher = ? AND status != ? ORDER BY int_records.status ASC", [teacher_login_id, "deleted"])
                    for_review = cur.fetchall()
                    return render_template("review.html", for_review=for_review, error=error)

                # If only hours is changed
                else:

                    # Need to change hours in student record if the record is endorsed
                    if old_status == "endorsed":
                        student_number = request.form.get("student_number")
                        cur.execute("SELECT * FROM students WHERE student_number = ?", [student_number])
                        rows = cur.fetchall()
                        change_in_hours = int(hours) - int(old_hours)
                        total_hours = rows[0][7]
                        total_hours = int(total_hours) + int(change_in_hours)
                        cur.execute("UPDATE int_records SET hours = ? WHERE int_rec_id = ?", [int(hours), int_rec_id])
                        cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                        conn.commit()
                        flash("Record updated!")
                        return redirect(url_for("review"))

                    # Just change the int_records table if the record is not endorsed
                    else:
                        cur.execute("UPDATE int_records SET hours = ? WHERE int_rec_id = ?", [int(hours), int_rec_id])
                        conn.commit()
                        flash("Record updated!")
                        return redirect(url_for("review"))

            # If status is changed
            student_number = request.form.get("student_number")
            cur.execute("SELECT * FROM students WHERE student_number = ?", [student_number])
            rows = cur.fetchall()

            # From pending / rejected to endorsed: Add total_hours
            if status == "endorsed":
                total_hours = rows[0][7]
                total_hours = int(total_hours) + int(hours)
                cur.execute("UPDATE int_records SET status = ?, hours = ? WHERE int_rec_id = ?", [status, int(hours), int_rec_id])
                cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                conn.commit()
                flash("Record updated!")
                return redirect(url_for("review"))

            # From endorsed to pending / rejected: Deduct total_hours given before
            elif old_status == "endorsed":
                total_hours = rows[0][7]
                total_hours = total_hours - int(hours)
                cur.execute("UPDATE int_records SET status = ?, hours = ? WHERE int_rec_id = ?", [status, int(hours), int_rec_id])
                cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                conn.commit()
                flash("Record updated!")
                return redirect(url_for("review"))

            # From pending to rejected or rejected to pending: No need to change total_hours
            else:
                cur.execute("UPDATE int_records SET status = ?, hours = ? WHERE int_rec_id = ?", [status, int(hours), int_rec_id])
                conn.commit()
                flash("Record updated!")
                return redirect(url_for("review"))

        # If the student has just deleted the record:
        else:
            error = "The student has just deleted the record."
            cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
            rows = cur.fetchall()
            teacher_login_id = rows[0][1]
            cur.execute("SELECT * FROM int_records INNER JOIN students ON int_records.student_number = students.student_number AND teacher = ? AND status != ? ORDER BY int_records.status ASC", [teacher_login_id, "deleted"])
            for_review = cur.fetchall()
            return render_template("review.html", for_review=for_review, error=error)


@app.route("/reviewext", methods=["GET", "POST"])
@login_required
def reviewext():
    # User reached route via GET
    if request.method == "GET":
        # Check if the user is a teacher
        if session.get("teacher_id") is None:
            flash("You have no access to this.")
            return redirect(url_for("index"))

        else:
            # Check if the teacher is designated for reviewing external records
            cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
            rows = cur.fetchall()
            if not rows[0][5]:
                flash("You have no access to this.")
                return redirect(url_for("index"))
            else:
                # Create a table of external records for review
                cur.execute("SELECT ext_rec_id, ext_records.student_number, students.student_number, org_name, contact, post, hours, status, students.class, students.class_number, students.firstname, students.lastname FROM ext_records INNER JOIN students ON ext_records.student_number = students.student_number AND status != ? ORDER BY ext_records.status ASC", ["deleted"])
                for_review = cur.fetchall()
                return render_template("reviewext.html", for_review=for_review)

    # User POST information
    else:
        error = None

        ext_rec_id = request.form.get("ext_rec_id")
        hours = request.form.get("hours")
        status = request.form.get("status")
        cur.execute("SELECT * FROM ext_records WHERE ext_rec_id = ?", ext_rec_id)
        rows = cur.fetchall()
        old_status = rows[0][6]
        old_hours = rows[0][5]

        # If the student has not deleted the record:
        if old_status != "deleted":

            # Check if the hours input is valid
            if hours.isdecimal() != True:
                error = "Number of hours should be a number. Do not include any words and other unnecessary characters."
                cur.execute("SELECT ext_rec_id, ext_records.student_number, students.student_number, org_name, contact, post, hours, status, students.class, students.class_number, students.firstname, students.lastname FROM ext_records INNER JOIN students ON ext_records.student_number = students.student_number AND status != ? ORDER BY ext_records.status ASC", ["deleted"])
                for_review = cur.fetchall()
                return render_template("reviewext.html", for_review=for_review, error=error)

            # If status is not changed
            if status == None:

                # If hours also is not changed
                if int(hours) == int(old_hours):
                    error = "There is no change!"
                    cur.execute("SELECT ext_rec_id, ext_records.student_number, students.student_number, org_name, contact, post, hours, status, students.class, students.class_number, students.firstname, students.lastname FROM ext_records INNER JOIN students ON ext_records.student_number = students.student_number AND status != ? ORDER BY ext_records.status ASC", ["deleted"])
                    for_review = cur.fetchall()
                    return render_template("reviewext.html", for_review=for_review, error=error)

                # If only hours is changed
                else:
                    # If the status is endorsed, need to change the total_hours in students table
                    if old_status == "endorsed":
                        student_number = request.form.get("student_number")
                        cur.execute("SELECT * FROM students WHERE student_number = ?", [student_number])
                        rows = cur.fetchall()
                        cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                        teachers = cur.fetchall()
                        teacher_login_id = teachers[0][1]
                        change_in_hours = int(hours) - int(old_hours)
                        total_hours = rows[0][7]
                        total_hours = int(total_hours) + int(change_in_hours)
                        cur.execute("UPDATE ext_records SET hours = ?, handler = ? WHERE ext_rec_id = ?", [int(hours), teacher_login_id, ext_rec_id])
                        cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                        conn.commit()
                        flash("Record updated!")
                        return redirect(url_for("reviewext"))

                    # If the status is pending / rejected, no need to change the total_hours
                    else:
                        cur.execute("UPDATE ext_records SET hours = ?, handler = ? WHERE ext_rec_id = ?", [int(hours), teacher_login_id, ext_rec_id])
                        conn.commit()
                        flash("Record updated!")
                        return redirect(url_for("reviewext"))

            # If status is changed
            else:
                # From pending / rejected to endorsed: Add total_hours
                if status == "endorsed":
                    student_number = request.form.get("student_number")
                    cur.execute("SELECT * FROM students WHERE student_number = ?", [student_number])
                    rows = cur.fetchall()
                    cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                    teachers = cur.fetchall()
                    teacher_login_id = teachers[0][1]
                    total_hours = rows[0][7]
                    total_hours = int(total_hours) + int(hours)
                    cur.execute("UPDATE ext_records SET status = ?, hours = ?, handler = ? WHERE ext_rec_id = ?", [status, int(hours), teacher_login_id, ext_rec_id])
                    cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                    conn.commit()
                    flash("Record updated!")
                    return redirect(url_for("reviewext"))

                # From endorsed to pending / rejected: Deduct total_hours given before
                elif old_status == "endorsed":
                    student_number = request.form.get("student_number")
                    cur.execute("SELECT * FROM students WHERE student_number = ?", [student_number])
                    rows = cur.fetchall()
                    cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                    teachers = cur.fetchall()
                    teacher_login_id = teachers[0][1]
                    total_hours = rows[0][7]
                    total_hours = int(total_hours) - int(hours)
                    cur.execute("UPDATE ext_records SET status = ?, hours = ?, handler = ? WHERE ext_rec_id = ?", [status, int(hours), teacher_login_id, ext_rec_id])
                    cur.execute("UPDATE students SET total_hours = ? WHERE student_number = ?", [total_hours, student_number])
                    conn.commit()
                    flash("Record updated!")
                    return redirect(url_for("reviewext"))

                # From pending to rejected or rejected to pending: No need to change total_hours
                else:
                    cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                    teachers = cur.fetchall()
                    teacher_login_id = teachers[0][1]
                    cur.execute("UPDATE ext_records SET status = ?, hours = ?, handler = ? WHERE ext_rec_id = ?", [status, int(hours), teacher_login_id, ext_rec_id])
                    conn.commit()
                    flash("Record updated!")
                    return redirect(url_for("reviewext"))

        # If the student has just deleted the record:
        else:
            error = "The student has just deleted the record."
            cur.execute("SELECT * FROM ext_records INNER JOIN students ON ext_records.student_number = students.student_number AND status != ? ORDER BY ext_records.status ASC", ["deleted"])
            for_review = cur.fetchall()
            return render_template("reviewext.html", for_review=for_review, error=error)


@app.route("/forgetpw", methods=["GET", "POST"])
def forgetpw():
    # User reaches the route via GET: Go to the page of forgetpw
    if request.method == "GET":
        session.clear()
        return render_template("forgetpw.html")

    # USER post email info
    else:
        error = None
        email = request.form.get("email")
        identity = request.form.get("identity")

        if identity == "teacher":
            cur.execute("SELECT * FROM teachers WHERE email = ?", [email])
            check_teacher = cur.fetchall()
            if len(check_teacher) != 1:
                error = "Sorry, wrong email."
                return render_template("forgetpw.html", error=error)
            else:
                name = check_teacher[0][2]
                identification = check_teacher[0][1]

        if identity == "student":
            cur.execute("SELECT * FROM students WHERE email = ?", [email])
            check_student = cur.fetchall()
            if len(check_student) != 1:
                error = "Sorry, wrong email."
                return render_template("forgetpw.html", error=error)
            else:
                name = check_student[0][4] + " " + check_student[0][3]
                identification = check_student[0][0]

        # Create a security code
        security_code = randint(100000, 999999)

        # Create a table for comparing identification and security code
        cur.execute("CREATE TABLE IF NOT EXISTS resetpw (resetpw_id INTEGER NOT NULL, identity TEXT NOT NULL, identification TEXT NOT NULL, security_code NUMERIC UNIQUE NOT NULL, PRIMARY KEY(resetpw_id))")
        cur.execute("DELETE FROM resetpw WHERE identification = ? AND identity = ?", [identification, identity])
        cur.execute("INSERT INTO resetpw (identification, identity, security_code) VALUES (?, ?, ?)", [identification, identity, security_code])
        conn.commit()

        # Send an email to the user (Ref: https://www.tutorialspoint.com/flask/flask_mail.htm | https://pythonprogramming.net/flask-email-tutorial/)
        resetpw_mail = Message("Service Record - Resetting your password", recipients=[email])
        resetpw_mail.html = render_template("/resetpw_mail.html", name=name, security_code=security_code)
        mail.send(resetpw_mail)
        flash("An email has been sent to you. Please follow the instructions there to reset your password.")
        return redirect(url_for("index"))


@app.route("/resetpw", methods=["GET", "POST"])
def resetpw():
    # User reaches the route via GET (probably from the email): Go to the page of resetpw
    if request.method == "GET":
        session.clear()
        return render_template("resetpw.html")

    # USER post info for resetting pw
    else:
        # Check identity, identification and security code
        identity = request.form.get("identity")
        identification = request.form.get("identification")
        security_code = request.form.get("security_code", type=int)
        cur.execute("SELECT * FROM resetpw WHERE identity = ? AND identification = ?", [identity, identification])
        check_user = cur.fetchall()
        if (len(check_user) == 0) or (security_code != check_user[0][3]):
            flash("Sorry, the information and / or security code is wrong.")
            return render_template("resetpw.html")

        else:
            # Handle password
            error = None

            # Get password created by the user
            password = request.form.get("password")
            if not password:
                error = "Creating a password is a must."

            # Ensure requirement fulfillment (at least one letter and one number)
            counter_letter = 0
            counter_number = 0
            for i in range(len(password)):
                if password[i].isalpha() == True:
                    counter_letter += 1
                if password[i].isdecimal() == True:
                    counter_number += 1
            if (counter_letter == 0) or (counter_number == 0):
                error = "Password does not fulfill all the requirements. Please create another password."

            # Handle password confirmation
            confirm_pw = request.form.get("confirm_pw")
            if not confirm_pw:
                error = "Please confirm your password."
            if confirm_pw != password:
                error = "Password not matched. Please double-check your password."

            # If error:
            if error != None:
                return render_template("resetpw.html", error=error)
            # If no error: Hash the password and add it into the teachers / students table
            else:
                hashed_pw = generate_password_hash(confirm_pw, method='pbkdf2:sha256', salt_length=8)
                if identity == "teacher":
                    cur.execute("UPDATE teachers SET hash = ? WHERE login_id = ?", [hashed_pw, identification])
                    # Remove user's info in the resetpw table (to avoid resetting the password again with the same security code)
                    cur.execute("DELETE FROM resetpw WHERE identity = ? AND identification = ?", [identity, identification])
                    conn.commit()
                    flash("Password reset! Please log in.")
                    return redirect(url_for("index"))
                else:
                    cur.execute("UPDATE students SET hash = ? WHERE student_number = ?", [hashed_pw, identification])
                    # Remove user's info in the resetpw table (to avoid resetting the password again with the same security code)
                    cur.execute("DELETE FROM resetpw WHERE identity = ? AND identification = ?", [identity, identification])
                    conn.commit()
                    flash("Password reset! Please log in.")
                    return redirect(url_for("index"))


@app.route("/changepw", methods=["GET", "POST"])
@login_required
def changepw():
    # User reaches the route via GET: Go to the page
    if request.method == "GET":
        return render_template("changepw.html")

    # User POST information
    else:
        error = None

        # Get old password created by the user
        old_password = request.form.get("old_password")

        # Get password created by the user
        password = request.form.get("password")
        if not password:
            error = "Creating a password is a must."

        # Ensure requirement fulfillment (at least one letter and one number)
        counter_letter = 0
        counter_number = 0
        for i in range(len(password)):
            if password[i].isalpha() == True:
                counter_letter += 1
            if password[i].isdecimal() == True:
                counter_number += 1
        if (counter_letter == 0) or (counter_number == 0):
            error = "Password does not fulfill all the requirements. Please create another password."

        # Handle password confirmation
        confirm_pw = request.form.get("confirm_pw")
        if not confirm_pw:
            error = "Please confirm your password."
        if confirm_pw != password:
            error = "Password not matched. Please double-check your password."

        # If error:
        if error != None:
            return render_template("changepw.html", error=error)

        # If no error: Check old password, hash the new password and add it into the teachers table
        else:

            # If the user is a teacher
            if session.get("teacher_id") != None:
                cur.execute("SELECT * FROM teachers WHERE teacher_id = ?", [session["teacher_id"]])
                rows = cur.fetchall()
                # Check old password
                if check_password_hash(rows[0][3], old_password) == False:
                    error = "Your old password is wrong."
                    return render_template("changepw.html", error=error)
                else:
                    hashed_pw = generate_password_hash(confirm_pw, method='pbkdf2:sha256', salt_length=8)
                    cur.execute("UPDATE teachers SET hash = ? WHERE teacher_id = ?", [hashed_pw, session["teacher_id"]])
                    conn.commit()
                    flash("Password changed!")
                    return redirect(url_for("index"))

            # If the user is a student
            else:
                cur.execute("SELECT * FROM students WHERE student_number = ?", [session["student_number"]])
                rows = cur.fetchall()
                # Check old password
                if check_password_hash(rows[0][6], old_password) == False:
                    error = "Your old password is wrong."
                    return render_template("changepw.html", error=error)
                else:
                    hashed_pw = generate_password_hash(confirm_pw, method='pbkdf2:sha256', salt_length=8)
                    cur.execute("UPDATE students SET hash = ? WHERE student_number = ?", [hashed_pw, session["student_number"]])
                    conn.commit()
                    flash("Password changed!")
                    return redirect(url_for("index"))


@app.route("/man_org", methods=["GET", "POST"])
@login_required
def man_org():
    # User reaches the route via GET: Check whether the user is administrator (teacher_id = 1)
    if request.method == "GET":
        if session.get("teacher_id") != 1:
            flash("You have no access to this.")
            return redirect(url_for("index"))

        else:
            cur.execute("SELECT * FROM organisations INNER JOIN teachers ON organisations.tic1 = teachers.login_id AND organisations.disabled = ? ORDER BY organisations.org_name ASC", [0])
            organisations = cur.fetchall()
            cur.execute("SELECT * FROM organisations INNER JOIN teachers ON organisations.tic1 = teachers.login_id AND organisations.disabled = ? ORDER BY organisations.org_name ASC", [1])
            dis_organisations = cur.fetchall()
            cur.execute("SELECT * FROM teachers WHERE disabled = ? ORDER BY name ASC", [0])
            teachers = cur.fetchall()
            return render_template("man_org.html", organisations=organisations, dis_organisations=dis_organisations, teachers=teachers)

    # User POST information
    else:
        error = None

        # Get information from the form
        org_id = request.form.get("org_id")
        name = request.form.get("name")
        disabled = request.form.get("disabled")

        # Convert teacher name to login ID
        cur.execute("SELECT * FROM teachers WHERE name = ?", [name])
        teacher = cur.fetchall()
        tic = teacher[0][1]

        # Query the information of the organisation
        cur.execute("SELECT * FROM organisations WHERE org_id = ?", [org_id])
        rows = cur.fetchall()
        old_tic = rows[0][2]
        old_disabled = rows[0][3]

        # Handle changes
        if tic != old_tic:
            cur.execute("UPDATE organisations SET tic1 = ? WHERE org_id = ?", [tic, org_id])
            conn.commit()
        if int(disabled) != int(old_disabled):
            cur.execute("UPDATE organisations SET disabled = ? WHERE org_id = ?", [disabled, org_id])
            conn.commit()

        # If no changes at all: Error
        if (tic == old_tic) & (int(disabled) == int(old_disabled)):
            error = "There is no change!"
            cur.execute("SELECT * FROM organisations INNER JOIN teachers ON organisations.tic1 = teachers.login_id AND organisations.disabled = ? ORDER BY organisations.org_name ASC", [0])
            organisations = cur.fetchall()
            cur.execute("SELECT * FROM organisations INNER JOIN teachers ON organisations.tic1 = teachers.login_id AND organisations.disabled = ? ORDER BY organisations.org_name ASC", [1])
            dis_organisations = cur.fetchall()
            cur.execute("SELECT * FROM teachers WHERE disabled = ? ORDER BY name ASC", [0])
            teachers = cur.fetchall()
            return render_template("man_org.html", organisations=organisations, teachers=teachers, dis_organisations=dis_organisations, error=error)
        else:
            flash("Organisation information updated!")
            return redirect(url_for("man_org"))


@app.route("/s1overview")
@login_required
def s1overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["1_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/s2overview")
@login_required
def s2overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["2_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/s3overview")
@login_required
def s3overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["3_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/s4overview")
@login_required
def s4overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["4_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/s5overview")
@login_required
def s5overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["5_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/s6overview")
@login_required
def s6overview():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students WHERE class LIKE ? ORDER BY class, class_number", ["6_"])
        students = cur.fetchall()
        return render_template("overview.html", students=students)


@app.route("/generate")
@login_required
def generate():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students")
        students = cur.fetchall()
        for i in range(len(students)):
            student_number = students[i][0]
            total_hours = int(students[i][7])
            if total_hours >= 100:
                award = "Gold"
            elif total_hours >= 50:
                award = "Silver"
            elif total_hours >= 25:
                award = "Bronze"
            elif total_hours >= 10:
                award = "Merit"
            else:
                award = ""
            cur.execute("UPDATE students SET award = ? WHERE student_number = ?", [award, student_number])
            conn.commit()
        flash("Awards generated!")
        return redirect(url_for("index"))


@app.route("/resetallpw")
@login_required
def resetallpw():
    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        # Handle students' passwords
        cur.execute("SELECT * FROM students")
        students = cur.fetchall()
        for i in range(len(students)):
            student_number = students[i][0]
            # Create a personal code for first-time login
            personal_code = randint(100000, 999999)
            cur.execute("UPDATE students SET hash = ? WHERE student_number = ?", [personal_code, student_number])
            conn.commit()

        # Handle teachers' passwords
        cur.execute("SELECT * FROM teachers")
        teachers = cur.fetchall()
        for j in range(len(teachers)):
            teacher_id = teachers[j][0]
            # Create a personal code for first-time login
            personal_code = randint(100000, 999999)
            cur.execute("UPDATE teachers SET hash = ? WHERE teacher_id = ?", [personal_code, teacher_id])
            conn.commit()

        flash("All passwords reset!")
        return redirect(url_for("index"))


# Reference for letting user download csv file: https://stackoverflow.com/a/28012964/16071474
@app.route("/export_students")
@login_required
def export_students():
    def export_csv(csv_list):
        data = io.StringIO()
        w = csv.writer(data)

        # Write header
        w.writerow(('Student Number', 'Class', 'Class Number', 'Lastname', 'Firstname', 'Total Hours', 'Award'))
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        # Write information of each student
        for item in csv_list:
            w.writerow((item[0], item[1], item[2], item[3], item[4], item[7], item[8]))
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    # Check whether the user is administrator (teacher_id = 1)
    if session.get("teacher_id") != 1:
        flash("You have no access to this.")
        return redirect(url_for("index"))

    else:
        cur.execute("SELECT * FROM students")
        student_list = cur.fetchall()
        response = Response(export_csv(student_list), mimetype='text/csv')
        response.headers.set("Content-Disposition", "attachment", filename="student_list.csv")
        return response