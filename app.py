from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import sqlite3
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = "department_elective_secret_key"


# ============================================================
# DATABASE
# ============================================================

DATABASE = "database.db"


def get_db_connection():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


def create_database():

    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_no TEXT NOT NULL,
            student_name TEXT NOT NULL,
            department TEXT NOT NULL,
            semester TEXT NOT NULL,
            electives TEXT NOT NULL
        )
    """)

    conn.commit()

    conn.close()


create_database()


# ============================================================
# ELECTIVE COURSES
# ============================================================

ELECTIVES = {

    "CS501": "Machine Learning",

    "CS502": "Cloud Computing",

    "CS503": "Cyber Security",

    "CS504": "Data Mining"

}


# ============================================================
# STUDENT HOME PAGE
# ============================================================

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        register_no = request.form.get("register_no")

        student_name = request.form.get("student_name")

        department = request.form.get("department")

        semester = request.form.get("semester")


        if not register_no or not student_name or not department or not semester:

            return render_template(
                "error.html",
                message="Please fill all student details."
            )


        return render_template(
            "electives.html",
            register_no=register_no,
            student_name=student_name,
            department=department,
            semester=semester,
            electives=ELECTIVES
        )


    return render_template("index.html")


# ============================================================
# STUDENT ELECTIVE SUBMISSION
# ============================================================

@app.route("/submit-selection", methods=["POST"])
def submit_selection():

    register_no = request.form.get("register_no")

    student_name = request.form.get("student_name")

    department = request.form.get("department")

    semester = request.form.get("semester")

    selected_codes = request.form.getlist("electives")


    if not register_no or not student_name or not department or not semester:

        return render_template(
            "error.html",
            message="Student information is missing."
        )


    if not selected_codes:

        return render_template(
            "error.html",
            message="Please select at least one elective course."
        )


    selected_courses = []


    for code in selected_codes:

        if code in ELECTIVES:

            selected_courses.append(
                (code, ELECTIVES[code])
            )


    if not selected_courses:

        return render_template(
            "error.html",
            message="Invalid elective selection."
        )


    electives_text = ", ".join(
        f"{code} - {name}"
        for code, name in selected_courses
    )


    conn = get_db_connection()


    conn.execute("""
        INSERT INTO students (
            register_no,
            student_name,
            department,
            semester,
            electives
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        register_no,
        student_name,
        department,
        semester,
        electives_text
    ))


    conn.commit()

    conn.close()


    return render_template(
        "confirmation.html",
        register_no=register_no,
        student_name=student_name,
        department=department,
        semester=semester,
        selected_courses=selected_courses
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username")

        password = request.form.get("password")


        if username == "admin" and password == "admin123":

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_dashboard")
            )


        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )


    return render_template("admin_login.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()


    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY id DESC
    """).fetchall()


    conn.close()


    return render_template(
        "admin_dashboard.html",
        students=students
    )


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout", methods=["GET"])
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )


    return redirect(
        url_for("admin_login")
    )


# ============================================================
# GENERATE PDF FOR ONE STUDENT
# ============================================================

@app.route(
    "/admin/generate-pdf/<int:student_id>",
    methods=["GET"]
)
def generate_student_pdf(student_id):

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()


    student = conn.execute("""
        SELECT *
        FROM students
        WHERE id = ?
    """, (student_id,)).fetchone()


    conn.close()


    if student is None:

        return render_template(
            "error.html",
            message="Student record not found."
        )


    # ========================================================
    # CREATE PDF
    # ========================================================

    buffer = BytesIO()


    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )


    width, height = A4


    # ========================================================
    # HEADER
    # ========================================================

    pdf.setFont(
        "Helvetica-Bold",
        20
    )


    pdf.drawCentredString(
        width / 2,
        height - 40 * mm,
        "DEPARTMENT ELECTIVE SELECTION"
    )


    pdf.setFont(
        "Helvetica",
        11
    )


    pdf.drawCentredString(
        width / 2,
        height - 48 * mm,
        "Student Elective Course Selection Record"
    )


    pdf.setStrokeColor(colors.grey)


    pdf.line(
        20 * mm,
        height - 55 * mm,
        width - 20 * mm,
        height - 55 * mm
    )


    # ========================================================
    # STUDENT DETAILS
    # ========================================================

    y = height - 75 * mm


    pdf.setFont(
        "Helvetica-Bold",
        12
    )


    pdf.drawString(
        25 * mm,
        y,
        "Student Details"
    )


    y -= 12 * mm


    details = [

        ("Register Number", student["register_no"]),

        ("Student Name", student["student_name"]),

        ("Department", student["department"]),

        ("Semester", student["semester"])

    ]


    for label, value in details:

        pdf.setFont(
            "Helvetica-Bold",
            10
        )


        pdf.drawString(
            30 * mm,
            y,
            label + ":"
        )


        pdf.setFont(
            "Helvetica",
            10
        )


        pdf.drawString(
            75 * mm,
            y,
            str(value)
        )


        y -= 9 * mm


    # ========================================================
    # SELECTED ELECTIVES
    # ========================================================

    y -= 10 * mm


    pdf.setFont(
        "Helvetica-Bold",
        12
    )


    pdf.drawString(
        25 * mm,
        y,
        "Selected Elective Courses"
    )


    y -= 12 * mm


    pdf.setFont(
        "Helvetica",
        10
    )


    courses = student["electives"].split(", ")


    for course in courses:

        pdf.drawString(
            35 * mm,
            y,
            "- " + course
        )


        y -= 9 * mm


    # ========================================================
    # FOOTER
    # ========================================================

    pdf.setFont(
        "Helvetica",
        9
    )


    pdf.drawCentredString(
        width / 2,
        20 * mm,
        "Generated by Department Elective Selection System"
    )


    pdf.save()


    buffer.seek(0)


    filename = f"elective_{student['register_no']}.pdf"


    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# ============================================================
# GENERATE PDF FOR ALL STUDENTS
# ============================================================

@app.route(
    "/admin/generate-all-pdf",
    methods=["GET"]
)
def generate_all_pdf():

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("admin_login")
        )


    conn = get_db_connection()


    students = conn.execute("""
        SELECT *
        FROM students
        ORDER BY department, register_no
    """).fetchall()


    conn.close()


    if not students:

        return render_template(
            "error.html",
            message="No student records available."
        )


    # ========================================================
    # CREATE PDF
    # ========================================================

    buffer = BytesIO()


    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )


    width, height = A4


    # ========================================================
    # HEADER
    # ========================================================

    pdf.setFont(
        "Helvetica-Bold",
        18
    )


    pdf.drawCentredString(
        width / 2,
        height - 30 * mm,
        "DEPARTMENT ELECTIVE SELECTION"
    )


    pdf.setFont(
        "Helvetica",
        10
    )


    pdf.drawCentredString(
        width / 2,
        height - 38 * mm,
        "Student Elective Selection Report"
    )


    y = height - 55 * mm


    # ========================================================
    # TABLE HEADER
    # ========================================================

    pdf.setFont(
        "Helvetica-Bold",
        8
    )


    pdf.drawString(
        12 * mm,
        y,
        "Reg. No."
    )


    pdf.drawString(
        45 * mm,
        y,
        "Student Name"
    )


    pdf.drawString(
        85 * mm,
        y,
        "Department"
    )


    pdf.drawString(
        130 * mm,
        y,
        "Semester"
    )


    pdf.drawString(
        160 * mm,
        y,
        "Electives"
    )


    y -= 5 * mm


    pdf.line(
        10 * mm,
        y,
        width - 10 * mm,
        y
    )


    y -= 8 * mm


    # ========================================================
    # STUDENT DATA
    # ========================================================

    pdf.setFont(
        "Helvetica",
        7
    )


    for student in students:

        if y < 25 * mm:

            pdf.showPage()


            y = height - 25 * mm


            pdf.setFont(
                "Helvetica-Bold",
                12
            )


            pdf.drawCentredString(
                width / 2,
                y,
                "Department Elective Selection Report"
            )


            y -= 15 * mm


            pdf.setFont(
                "Helvetica",
                7
            )


        pdf.drawString(
            12 * mm,
            y,
            str(student["register_no"])[:18]
        )


        pdf.drawString(
            45 * mm,
            y,
            str(student["student_name"])[:20]
        )


        pdf.drawString(
            85 * mm,
            y,
            str(student["department"])[:22]
        )


        pdf.drawString(
            130 * mm,
            y,
            str(student["semester"])[:15]
        )


        pdf.drawString(
            160 * mm,
            y,
            str(student["electives"])[:32]
        )


        y -= 10 * mm


    # ========================================================
    # FOOTER
    # ========================================================

    pdf.setFont(
        "Helvetica",
        8
    )


    pdf.drawCentredString(
        width / 2,
        12 * mm,
        "Generated by Department Elective Selection System"
    )


    pdf.save()


    buffer.seek(0)


    return send_file(
        buffer,
        as_attachment=True,
        download_name="all_student_elective_selections.pdf",
        mimetype="application/pdf"
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )