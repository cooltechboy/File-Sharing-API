from flask import *
from distutils.log import debug
from fileinput import filename
from werkzeug.utils import secure_filename
import sqlite3
import os
from functools import wraps
import jwt
import datetime
import collections
import collections.abc

app = Flask(__name__)

conn = sqlite3.connect("database.db")
print("Database connected successfully")

UPLOAD_FOLDER = "stored_files"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'mp3', 'mp4'}

app.config['SECRET_KEY'] = "very_secret"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Handles token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        headers = request.headers
        bearer = headers.get('Authorization')
        if bearer:    # Bearer YourTokenHere
            token = bearer.split()[0]
            if not token:
                return jsonify({"message" : "Token is required to proceed!"}), 403
            else:
                try:
                    data = jwt.decode(token, app.config['SECRET_KEY'])
                except:
                    return jsonify({"message" : "Token is invalid!"}), 403
                return f(data, *args, **kwargs)
        else:
            return "You need to provide token to use the function!"
    return decorated

# Checks if file is in correct format
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# This route connects with the homepage of the app
@app.route("/")
def main():
    return render_template("index.html")

# Handles signup
@app.route("/signup")
def signup():
    Name = request.form['name']
    Username = request.form['username']
    Password = request.form['password']
    conn = sqlite3.connect("database.db")
    Existing_Usernames = json.dumps(conn.execute("SELECT Username FROM User_Details").fetchall())
    if Username != "":
        if Username in Existing_Usernames:
            return "Username already exists!"
        else:
            if Password != "":
                conn.execute("INSERT INTO User_Details (Name, Username, Password) VALUES ('{n}', '{u}', '{p}')".format(n = Name, u = Username, p = Password))
            else:
                return "Please enter password!"
        conn.commit()
    else:
        return "Please enter Username!"
    return "Signed Up successfully!"

# Handles login
@app.route("/login")
def login():
    auth = request.authorization
    Username = auth.username
    conn = sqlite3.connect("database.db")
    Usernames = json.dumps(conn.execute("SELECT Username FROM User_Details").fetchall())
    if Username != "":
        if Username in Usernames:
            Password = json.dumps(conn.execute("SELECT Password FROM User_Details WHERE Username = '{n}'".format(n = Username)).fetchall())
            conn.commit()
            if auth.password != "":
                if auth and auth.password in Password:
                    token = jwt.encode({'user' : auth.username, 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=60)}, app.config['SECRET_KEY'])
                    return jsonify({'token' : token.decode('UTF-8')})
                else:
                    return "Incorrect password!"
            else:
                return "Please enter password!"
        else:
            return "Incorrect username or password!"
    else:
        return "Please enter username!"

# Shows files uploaded by the user
@app.route("/files/myuploads", methods = ['GET'])
@token_required
def showAll(data):
    username = data['user']
    conn = sqlite3.connect("database.db")
    table = conn.execute("SELECT * FROM Records WHERE UploaderName = '{n}'".format(n = username))
    conn.commit()
    return table.fetchall()

# Lets the user upload a file along with sharing it with other users
@app.route("/files/upload", methods = ['GET', 'POST'])
@token_required
def uploadFile(data):
    if request.method == 'POST':
        file = request.files['file']
        uploader = data['user']
        sharedWith = request.form['sharedWith']
        if 'file' not in request.files:
            return "No files detected!"
        if file.filename == '':
            return "Cannot add a file with no name!"
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"{uploader}-{datetime.datetime.utcnow().strftime('%B-%d-%Y-%H-%M-%S')}-{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn = sqlite3.connect("database.db")
            conn.execute("INSERT INTO Records (UploaderName, UploadedFile, FileStatus) Values ('{n}', '{p}', 'Active')".format(n = str(uploader), p = str(filename)))
        if list(sharedWith.split(','))[0] != "":
            for item in list(sharedWith.split(',')):
                conn.execute("INSERT INTO Sharing_Table (Name, SharedFile, FileStatus) Values ('{n}', '{p}', 'Active')".format(n = str(item), p = str(filename)))
        else:
            pass
        conn.commit()
    return "File saved successfully!"

# Lets the user download a file uploaded by him/her
@app.route('/files/download')
@token_required
def download_file(data):
    username = data['user']
    filename = request.form["filename"]
    conn = sqlite3.connect("database.db")
    accessible_data = json.dumps(conn.execute("SELECT UploadedFile FROM Records WHERE UploaderName = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
    conn.commit()
    if filename != "":
        if filename in accessible_data:
                return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
        else:
            return "No such file was uploaded by you!"
    else:
        return "Please provide filename to download it!"
    

# Lets the user view the files shared with him/her    
@app.route('/files/view/shared-files', methods = ['GET'])
@token_required
def view_shared_files(data):
    if request.method == 'GET':
        username = data['user']
        conn = sqlite3.connect("database.db")
        users_having_shared_files = json.dumps(conn.execute("SELECT Name FROM Sharing_Table").fetchall())
        if username in users_having_shared_files:
            shared_files = conn.execute("SELECT * FROM Sharing_Table WHERE Name = '{n}'".format(n = username)).fetchall()
        else:
            return "You have no shared files!"
        conn.commit()
    return shared_files

# Lets the user download a file shared with him/her      
@app.route('/files/download/shared-files')
@token_required
def download_shared_file(data):
    username = data['user']
    filename = request.form['filename']
    conn = sqlite3.connect("database.db")
    users_having_shared_files = json.dumps(conn.execute("SELECT Name FROM Sharing_Table").fetchall())
    accessible_data = json.dumps(conn.execute("SELECT SharedFile FROM Sharing_Table WHERE Name = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
    if filename != "":
        if username in users_having_shared_files:
            if filename in accessible_data:
                return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
            else:
                return "File does not exist!"
        else:
            return "You have no shared files!"
    else:
        return "Please enter filename to download it!"
    
# Lets the user delete a file uploaded by him/her
@app.route('/files/delete', methods = ['DELETE'])
@token_required
def delete_file(data):
    if request.method == 'DELETE':
        username = data['user']
        filename = request.form['filename']
        conn = sqlite3.connect("database.db")
        users_having_uploaded_files = json.dumps(conn.execute("SELECT UploaderName FROM Records").fetchall())
        accessible_data = json.dumps(conn.execute("SELECT UploadedFile FROM Records WHERE UploaderName = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
        if filename != "":
            if len(accessible_data) != 0:
                if username in users_having_uploaded_files:
                    if filename in accessible_data:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        conn.execute("UPDATE Records SET FileStatus = 'Inactive' WHERE UploaderName = '{n}' AND UploadedFile = '{f}'".format(n = username, f = filename))
                        conn.execute("UPDATE Sharing_Table SET FileStatus = 'Inactive' WHERE SharedFile = '{f}'".format(f = filename))
                    else:
                        return "You haven't uploaded any file with the name entered by you or it is already deleted by you!"
                else:
                    return "You haven't uploaded any file yet!"
            else:
                return "You don't have any active file!"
            conn.commit()
        else:
            return "Please provide filename to delete it!"
    return "File is deleted successfully!"

# Lets the user share an already uploaded file with other users
@app.route('/files/update/add-share', methods = ['PUT'])
@token_required
def addShare(data):
    if request.method == 'PUT':
        username = data['user']
        sharedWith = request.form['sharedWith']
        filename = request.form['filename']
        conn = sqlite3.connect("database.db")
        Available_Files = json.dumps(conn.execute("SELECT UploadedFile FROM Records WHERE UploaderName = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
        if filename != "":
            if filename in Available_Files:
                if list(sharedWith.split(','))[0] != "":
                    for item in list(sharedWith.split(',')):
                        conn.execute("INSERT INTO Sharing_Table (Name, SharedFile, FileStatus) Values ('{n}', '{p}', 'Active')".format(n = item, p = filename))
                    conn.commit()
                    return "File shared successfully!"
                else:
                    return "You haven't added any name to share with!"
            else:
                return "You haven't uploaded the file yet! Upload it first! You can share it from there too!"
        else:
            return "You haven't added the name of the file!"

# Lets the user revoke the shared access for an already uploaded file for other users            
@app.route('/files/update/remove-share', methods = ['PUT'])
@token_required
def removeShare(data):
    if request.method == 'PUT':
        username = data['user']
        unsharedWith = request.form['unsharedWith']
        filename = request.form['filename']
        conn = sqlite3.connect("database.db")
        Available_Files = json.dumps(conn.execute("SELECT UploadedFile FROM Records WHERE UploaderName = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
        if filename != "":
            if filename in Available_Files:
                if list(unsharedWith.split(','))[0] != "":
                    for item in list(unsharedWith.split(',')):
                        conn.execute("UPDATE Sharing_Table SET FileStatus = 'Inactive' WHERE Name = '{n}' AND SharedFile = '{p}'".format(n = item, p = filename))
                    conn.commit()
                    return "File sharing revoked successfully!"
                else:
                    return "You haven't added any name to remove sharing access!"
            else:
                return "You haven't uploaded any such file!"
        else:
            return "You haven't added the name of the file!"

# Lets the user give up access to a file shared with him/her        
@app.route('/files/shared-files/give-up-access')
@token_required
def give_up_access(data):
    username = data['user']
    filename = request.form['filename']
    conn = sqlite3.connect("database.db")
    users_having_shared_files = json.dumps(conn.execute("SELECT Name FROM Sharing_Table").fetchall())
    accessible_data = json.dumps(conn.execute("SELECT SharedFile FROM Sharing_Table WHERE Name = '{n}' AND FileStatus = 'Active'".format(n = username)).fetchall())
    if username in users_having_shared_files:
        if filename != "":
            if filename in accessible_data:
                conn.execute("UPDATE Sharing_Table SET FileStatus = 'Inactive' WHERE Name = '{n}' AND SharedFile = '{p}'".format(n = username, p = filename))
            else:
                return "File does not exist or you have already given up access to it!"
        else:
            return "Please enter name of the file!"
    else:
        return "You have no shared files!"
    conn.commit()
    return "You have successfully given up the access to the file!"


if __name__ == '__main__':
    app.run(debug=True)