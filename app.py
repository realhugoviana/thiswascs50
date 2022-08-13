from email.mime import application
import os

import sqlite3
from flask import Flask, flash, redirect, render_template, request, session, abort
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import datetime
from functools import wraps

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Connect to sqlite3 database
db = sqlite3.connect("data.db", check_same_thread=False)
db.row_factory = sqlite3.Row

def query_dict(query):
    """Returns data from an SQL query as a list of dicts."""
    try:
        things = db.execute(query).fetchall()
        unpacked = [{k: item[k] for k in item.keys()} for item in things]
        return unpacked
    except Exception as e:
        print(f"Failed to execute. Query: {query}\n with error:\n{e}")
        return []


def convertToBinaryData(filename):
    # Convert digital data to binary format
    with open(filename, 'rb') as file:
        blobData = file.read()
    return blobData


def writeTofile(data, filename):
    # Convert binary data to proper format and write it on Hard Disk
    with open(filename, 'wb') as file:
        file.write(data)


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not request.form.get("search"):
            return redirect("/")
        
        searched = request.form.get("search")

        projects = query_dict(f"SELECT DISTINCT * FROM projects WHERE title LIKE '%{searched}%' OR email IN(SELECT email FROM projects WHERE description LIKE '%{searched}%') OR email IN(SELECT email FROM users WHERE firstname LIKE '%{searched}%') OR email IN(SELECT email FROM users WHERE lastname LIKE '%{searched}%') OR email IN(SELECT email FROM users WHERE location LIKE '%{searched}%')")
        for project in projects:
            email = project["email"]
            user = query_dict(f"SELECT * FROM users WHERE email = '{email}'")
            likes = query_dict(f"SELECT COUNT(*) FROM likes WHERE project_email = '{email}'")
            try:
                browsing = session["user_id"]
                liked = len(query_dict(f"SELECT * FROM likes WHERE user_email = '{browsing}' AND project_email = '{email}'"))
                if liked != 0:
                    project["liked"] = True
                else:
                    project["liked"] = False
            except:
                project["liked"] = False
            project["firstname"] = user[0]["firstname"]
            project["lastname"] = user[0]["lastname"]
            project["location"] = user[0]["location"]
            project["id"] = user[0]["id"]
            project["likes"] = likes[0]["COUNT(*)"]
        return render_template("index.html", projects=projects)

    else:
        projects = query_dict(f"SELECT * FROM projects")
        for project in projects:
            email = project["email"]
            user = query_dict(f"SELECT * FROM users WHERE email = '{email}'")
            likes = query_dict(f"SELECT COUNT(*) FROM likes WHERE project_email = '{email}'")
            try:
                browsing = session["user_id"]
                liked = len(query_dict(f"SELECT * FROM likes WHERE user_email = '{browsing}' AND project_email = '{email}'"))
                print(liked)
                if liked != 0:
                    project["liked"] = True
                else: 
                    project["liked"] = False
            except:
                project["liked"] = False
            print(project["liked"])
            project["firstname"] = user[0]["firstname"]
            project["lastname"] = user[0]["lastname"]
            project["location"] = user[0]["location"]
            project["id"] = user[0]["id"]
            project["likes"] = likes[0]["COUNT(*)"]
        return render_template("index.html", projects=projects)


@app.route("/register-email", methods=["GET", "POST"])
def register():
    # Forget any user_id
    session.clear()

    if request.method == "POST":

        error = None

        # Ensure email adress was submitted
        if not request.form.get("email"):
            error = "must provide email adress"
            return render_template("register-email.html", error=error)

        # Ensure password was submitted
        elif not request.form.get("password"):
            error = "must provide password"
            return render_template("register-email.html", error=error)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            error = "must provide confirmation"
            return render_template("register-email.html", error=error)
        
        email = request.form.get("email")

        # Query database for email
        rows = query_dict(f"SELECT * FROM users WHERE email = '{email}'")

        # Ensure email isn't already used
        if len(rows) != 0:
            error = "This email adress is already used for another account"
            return render_template("register-email.html", error=error)

        # Ensure password matches the confirmation
        if request.form.get("password") != request.form.get("confirmation"):
            error = "The password and the confirmation do not match"
            return render_template("register-email.html", error=error)

        # Insert the new user to the database
        password_hash = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (email, hash) VALUES(?, ?)", (email, password_hash))
        db.commit()

        # Remember which user has logged in
        rows = query_dict(f"SELECT * FROM users WHERE email = '{email}'")
        session["user_id"] = rows[0]["email"]

        return redirect("/register-name")
    else:
        return render_template("register-email.html")


@app.route("/register-name", methods=["GET", "POST"])
@login_required
def name():
    if request.method == "POST":

        error = None

        # Ensure first name was submitted
        if not request.form.get("firstname"):
            error = "must provide first name"
            return render_template("name.html", error=error)

        # Ensure last name was submitted
        elif not request.form.get("lastname"):
            error = "must provide last name"
            return render_template("name.html", error=error)

        firstname = request.form.get("firstname")
        lastname = request.form.get("lastname")

        exists = False
        i = 0
        while not exists:
            if i == 0:
                rows = query_dict(f"SELECT * FROM users WHERE id = '{firstname}{lastname}'")
            else:
                rows = query_dict(f"SELECT * FROM users WHERE id = '{firstname}{lastname}{i}'")
            
            if len(rows) != 0:
                exists = False
            else:
                exists = True
            
            i += 1
        
        if i == 1:    
            id = f"{firstname}_{lastname}"
        else:
            id = f"{firstname}_{lastname}{i - 1}"

        # Insert the new name to the database
        db.execute("UPDATE users SET firstname = ?, lastname = ?, id = ? WHERE email = ?", (firstname, lastname, id, session["user_id"]))
        db.commit()

        return redirect("/register-location")
    else:
        return render_template("name.html")


@app.route("/register-location", methods=["GET", "POST"])
@login_required
def user_location():
    if request.method == "POST":
        # check if location was submitted
        if not request.form.get("location"):
            return redirect("/register-bio")

        user_location = request.form.get("location")

        # Insert the new location to the database
        db.execute("UPDATE users SET location = ? WHERE email = ?", (user_location, session["user_id"]))
        db.commit()

        return redirect("/register-bio")
    else:
        return render_template("location.html")


@app.route("/register-bio", methods=["GET", "POST"])
@login_required
def bio():
    if request.method == "POST":
        # check if bio was submitted
        if not request.form.get("bio"):
            return redirect("/register-project")

        bio = request.form.get("bio")

        # Insert the new bio to the database
        db.execute("UPDATE users SET bio = ? WHERE email = ?", (bio, session["user_id"]))
        db.commit()

        return redirect("/register-picture")
    else:
        return render_template("bio.html")


@app.route("/register-picture", methods=["GET", "POST"])
@login_required
def profile_picture():
    if request.method == "POST":
        error = None

        if not request.files['picture']:
            profile_picture = convertToBinaryData(r"C:\Users\hugo\OneDrive\Bureau\project\static\images\AndreMonster.jpg")
            db.execute("UPDATE users SET profilepicture = ? WHERE email = ?", (profile_picture, session["user_id"]))
            db.commit()
            return redirect('/register-project')

        # Saves the file uploaded
        profile_picture = request.files["picture"]
        if not profile_picture.filename.endswith('.jpg'):
            profile_picture = convertToBinaryData(r"C:\Users\hugo\OneDrive\Bureau\project\static\images\AndreMonster.jpg")
            db.execute("UPDATE users SET profilepicture = ? WHERE email = ?", (profile_picture, session["user_id"]))
            db.commit()
            error = "must upload a jpg file"
            return render_template("profile-picture.html", error=error)
        profile_picture.save(r"C:\Users\hugo\OneDrive\Bureau\project\static\images\profile_picture.jpg")

        try:
            profile_picture = convertToBinaryData(r"C:\Users\hugo\OneDrive\Bureau\project\static\images\profile_picture.jpg")
            db.execute("UPDATE users SET profilepicture = ? WHERE email = ?", (profile_picture, session["user_id"]))
            db.commit()

        except:
            profile_picture = convertToBinaryData(r"C:\Users\hugo\OneDrive\Bureau\project\static\images\AndreMonster.jpg")
            db.execute("UPDATE users SET profilepicture = ? WHERE email = ?", (profile_picture, session["user_id"]))
            db.commit()
            error = "file did not upload"
            return render_template("profile-picture.html", error=error)

        return redirect("/register-project")
    else:
        return render_template("profile-picture.html")


@app.route("/register-project", methods=["GET", "POST"])
@login_required
def register_project():
    email = session["user_id"]
    row = query_dict(f"SELECT * FROM projects WHERE email = '{email}'")
    if request.method == "POST":
        error = None
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") 

        # Ensure title was submitted
        if not request.form.get("title"):
            error = "must provide a title"
            return render_template("create-project.html", error=error)

        # Ensure youtube video was submitted
        elif not request.form.get("video"):
            error = "must provide a link to your youtube video"
            return render_template("create-project.html", error=error)

        title = request.form.get("title")
        video = request.form.get("video")

        # Get the embed url of the video
        video = f"https://www.youtube.com/embed/{video[32:len(video)]}"

        # Insert the new project to the database
        db.execute("INSERT INTO projects (email, title, video, date) VALUES(?, ?, ?, ?)", (email, title, video, date))
        db.commit()

        # Add description to the project
        if request.form.get("description"):
            description = request.form.get("description")
            db.execute("UPDATE projects SET description = ? WHERE email = ?", (description, email))
            db.commit()


        # Add link to the project
        if request.form.get("link"):
            project_link = request.form.get("link")
            db.execute("UPDATE projects SET link = ? WHERE email = ?", (project_link, email))
            db.commit()

        return redirect("/")
    elif len(row) != 0:
        return redirect("/myproject")
    else:
        return render_template("create-project.html")


@app.route("/myproject", methods=["GET"])
@login_required
def my_project():
    email = session["user_id"]
    row = query_dict(f"SELECT * FROM projects WHERE email = '{email}'")

    if len(row) == 0:
        return redirect("/register-project")
    else:
        user = query_dict(f"SELECT * FROM users WHERE email = '{email}'")
        id = user[0]["id"]

        return redirect(f"/project/{id}")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        error = None

        # Ensure email was submitted
        if not request.form.get("email"):
            error = "must provide email adress"
            return render_template("login.html", error=error)

        # Ensure password was submitted
        elif not request.form.get("password"):
            error = "must provide password"
            return render_template("login.html", error=error)
        
        email = request.form.get("email")

        # Query database for email
        rows = query_dict(f"SELECT * FROM users WHERE email = '{email}'")

        # Ensure email exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            error = "invalid username and/or password"
            return render_template("login.html", error=error)

        # Remember which user has logged in
        session["user_id"] = rows[0]["email"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        user_location = request.form.get("location")
        bio = request.form.get("bio")

        # Insert the new location to the database
        db.execute("UPDATE users SET bio = ?, location = ? WHERE email = ?", (bio, user_location, session["user_id"]))
        db.commit()

        return redirect("/account")
    else:
        email = session["user_id"]
        user = query_dict(f"SELECT * FROM users WHERE email = '{email}'")

        with open(r'C:\Users\hugo\OneDrive\Bureau\project\static\images\profile_picture.jpg', 'wb') as file:
            file.write(user[0]["profilepicture"])

        return render_template("account.html", user=user[0])
        


@app.route("/project/<id>", methods=["GET", "POST"])
def project(id):
    user = query_dict(f"SELECT * FROM users WHERE id = '{id}'")
    project_email = user[0]["email"]
    if request.method == "POST":
        if request.form.get("comment"):
            content = request.form.get("comment")
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                comment_email = session["user_id"]
            except:
                db.execute("INSERT INTO comments(project_email, date, content) VALUES(?, ?, ?)", (project_email, date, content))
            else:
                comment_user = query_dict(f"SELECT * FROM users WHERE email = '{comment_email}'")
                db.execute("INSERT INTO comments(project_email, firstname, lastname, date, content) VALUES(?, ?, ?, ?, ?)", (project_email, comment_user[0]['firstname'], comment_user[0]['lastname'], date, content))
            finally:
                db.commit()

            return redirect(f"/project/{id}")
        
        if request.form["like_button"]:
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if request.form["like_button"] == 'like':
                try:
                    like_email = session["user_id"]
                    rows = query_dict(f"SELECT * FROM likes WHERE user_email = '{like_email}' AND project_email = '{project_email}'")
                    if len(rows) != 0:
                        return redirect(f"/project/{id}")
                except:
                    db.execute("INSERT INTO likes(project_email, date) VALUES(?, ?)", (project_email, date))
                else:
                    db.execute("INSERT INTO likes(user_email, project_email, date) VALUES(?, ?, ?)", (like_email, project_email, date))
                finally:
                    db.execute(f"UPDATE projects SET likes = likes + 1 WHERE email = '{project_email}'")
                    db.commit()
                
                return redirect(f"/project/{id}")
    elif len(user) != 1:
        abort(404)
    else:
        project = query_dict(f"SELECT * FROM projects WHERE email = '{project_email}'")
        comments = query_dict(f"SELECT * FROM comments WHERE project_email = '{project_email}' ORDER BY date DESC")
        likes = query_dict(f"SELECT likes FROM projects WHERE email = '{project_email}'")
        
        with open(r'C:\Users\hugo\OneDrive\Bureau\project\static\images\profile_picture.jpg', 'wb') as file:
            file.write(user[0]["profilepicture"])
        try:
            like_email = session["user_id"]
        except:
            like_email = 'bonjour'
        
        rows = query_dict(f"SELECT * FROM likes WHERE user_email = '{like_email}' AND project_email = '{project_email}'")
        if len(rows) != 0:
            return render_template("project.html", user=user[0], project=project[0], comments=comments, liked=True, likes=likes[0]['likes'])
        else:
            return render_template("project.html", user=user[0], project=project[0], comments=comments, likes=likes[0]['likes'])
