from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

import os
from pathlib import Path
from io import BytesIO

from dotenv import load_dotenv
from supabase import create_client, Client

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "department_elective_secret_key"
)


# ============================================================
# SUPABASE DATABASE
# ============================================================

# Load the Supabase Secret key specifically.
# Do NOT use SUPABASE_KEY here, because an old Windows environment
# variable with that name may contain the publishable key.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SECRET_KEY is missing. Check your .env file."
    )

if not SUPABASE_KEY.startswith("sb_secret_"):
    raise RuntimeError(
        "SUPABASE_SECRET_KEY must be your Supabase Secret key (starts with sb_secret_)."
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

print("Supabase connected using Secret key.")


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


    # ========================================================
    # SAVE STUDENT TO SUPABASE
    # ========================================================

    try:

        supabase.table("student").insert({

            "register_no": register_no,

            "student_name": student_name,

            "department": department,

            "semester": semester,

            "electives": electives_text

        }).execute()

    except Exception as e:

        print("SUPABASE INSERT ERROR:", e)

        return render_template(
            "error.html",
            message="Unable to save student data. Please try again."
        )


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


        admin_username = os.environ.get(
            "ADMIN_USERNAME",
            "admin"
        )

        admin_password = os.environ.get(
            "ADMIN_PASSWORD",
            "admin123"
        )


        if username == admin_username and password == admin_password:

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


    try:

        response = (
            supabase
            .table("student")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        students = response.data or []

    except Exception as e:

        print("SUPABASE SELECT ERROR:", e)

        return render_template(
            "error.html",
            message="Unable to load student records."
        )


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


    # ========================================================
    # GET STUDENT FROM SUPABASE
    # ========================================================

    try:

        response = (
            supabase
            .table("student")
            .select("*")
            .eq("id", student_id)
            .execute()
        )

        students = response.data or []

        student = students[0] if students else None

    except Exception as e:

        print("SUPABASE SELECT ERROR:", e)

        return render_template(
            "error.html",
            message="Unable to retrieve student record."
        )


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


    # ========================================================
    # GET ALL STUDENTS FROM SUPABASE
    # ========================================================

    try:

        response = (
            supabase
            .table("student")
            .select("*")
            .order("department")
            .order("register_no")
            .execute()
        )

        students = response.data or []

    except Exception as e:

        print("SUPABASE SELECT ERROR:", e)

        return render_template(
            "error.html",
            message="Unable to retrieve student records."
        )


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
