from flask import Flask, request, jsonify, send_file
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
import os
import pandas as pd
from bson import ObjectId

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['MONGO_URI'] = os.getenv("MONGODB_URL")
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
MONGO_URI = app.config['MONGO_URI']
client = MongoClient(MONGO_URI)
db = client["attendance_system"]  # Change to your actual database name
bcrypt = Bcrypt(app)
jwt = JWTManager(app)



# Test MongoDB connection
try:
    db.admins.find_one()
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print("❌ MongoDB Connection Failed:", e)


# Admin Registration
@app.route('/register_admin', methods=['POST'])
def register_admin():
    data = request.json
    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    admin = {"email": data['email'], "password": hashed_pw, "school": data['school']}
    db.admins.insert_one(admin)
    return jsonify({"message": "Admin registered successfully"}), 201

# Admin Login
@app.route('/login_admin', methods=['POST'])
def login_admin():
    data = request.json
    admin = db.admins.find_one({"email": data['email']})
    if admin and bcrypt.check_password_hash(admin['password'], data['password']):
        token = create_access_token(identity={"email": data['email'], "school": admin['school']})
        return jsonify({"token": token})
    return jsonify({"message": "Invalid credentials"}), 401

# Add Student
@app.route('/add_student', methods=['POST'])
@jwt_required()
def add_student():
    data = request.json
    school = get_jwt_identity()['school']
    student = {"name": data['name'], "roll_no": data['roll_no'], "school": school}
    db.students.insert_one(student)
    return jsonify({"message": "Student added successfully"})

# Fetch Students (Admin only)
@app.route('/students', methods=['GET'])
@jwt_required()
def get_students():
    school = get_jwt_identity()['school']
    students = list(db.students.find({"school": school}, {"_id": 0}))
    return jsonify(students)

# Add Attendance (Name-wise & Subject-wise)
@app.route('/add_attendance', methods=['POST'])
@jwt_required()
def add_attendance():
    data = request.json
    student = db.students.find_one({"_id": ObjectId(data['student_id'])})

    if not student:
        return jsonify({"message": "Student not found"}), 404

    attendance = {
        "student_id": data['student_id'],
        "name": student["name"],  # Fetch student name
        "subject": data['subject'],  # Include subject
        "date": data['date'],
        "status": data['status']
    }

    # Prevent duplicate attendance for the same student, subject, and date
    existing = db.attendance.find_one({
        "name": data['name'],
        "subject": data['subject'],
        "date": data['date']
    })
    
    if existing:
        return jsonify({"message": "Attendance already recorded for this student in this subject on this date"}), 400

    db.attendance.insert_one(attendance)
    return jsonify({"message": "Attendance recorded successfully"})


# Get Attendance (Admin)
# Get Attendance (Filtered by Subject & Date)
@app.route('/attendance/<date>', methods=['GET'])
@jwt_required()
def get_attendance(date):
    subject = request.args.get("subject")  # Optional subject filter
    query = {"date": date}
    
    if subject:
        query["subject"] = subject

    attendance = list(db.attendance.find(query))
    return jsonify([{**att, "_id": str(att["_id"])} for att in attendance])

# Get Student Attendance
@app.route('/student_attendance/<student_id>', methods=['GET'])
@jwt_required()
def student_attendance(student_id):
    attendance = list(db.attendance.find({"student_id": student_id}))
    return jsonify([{**att, "_id": str(att["_id"])} for att in attendance])

# Download Attendance Report
@app.route('/download_report/<date>', methods=['GET'])
@jwt_required()
def download_report(date):
    attendance = list(db.attendance.find({"date": date}))
    df = pd.DataFrame(attendance)
    file_path = f"attendance_{date}.csv"
    df.to_csv(file_path, index=False)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
