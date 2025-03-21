import json
import math
import os
from datetime import timedelta, datetime, timezone  # Added timezone

import bcrypt
import psycopg2
from PIL import Image
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, decode_token
from werkzeug.utils import secure_filename

import AI_API as api
from controllers.emailController import send_reset_email

app = Flask(__name__, static_folder='assets')
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def get_db_connection():
    db_config = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", 5432)  # Default to 5432 if not set
    }

    if not all(db_config.values()):
        raise Exception("Database configuration is incomplete. Check .env file.")

    return psycopg2.connect(**db_config)


JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise Exception("JWT secret not found.")

app.config['JWT_SECRET_KEY'] = JWT_SECRET
jwt_manager = JWTManager(app)


# Backend server can be headless, might not need
@app.route('/')
def serve_index():
    return render_template('invalidToken.html', message="Backend up"), 200


@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return jsonify({"error": "Missing username, email, or password"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()
        if existing:
            cur.close()
            conn.close()
            return jsonify({"error": "User already exists"}), 400

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cur.execute("""
            INSERT INTO users (username, email, password)
            VALUES (%s, %s, %s)
            RETURNING id, username, email
        """, (username, email, hashed_password))
        new_user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "User created successfully",
            "user": {
                "id": new_user[0],
                "username": new_user[1],
                "email": new_user[2]
            }
        }), 201

    except Exception as e:
        print("Error during signup:", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, email, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({"error": "Invalid email or password"}), 401

        user_id, user_email, hashed_password = user

        is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        if not is_valid:
            cur.close()
            conn.close()
            return jsonify({"error": "Invalid email or password"}), 401

        token = create_access_token(identity=str(user_id), expires_delta=timedelta(hours=2))

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "token": token
        }), 200

    except Exception as e:
        print("Error during login:", e)
        return jsonify({"error": "Server error"}), 500


@app.route('/api/auth-check', methods=['GET'])
@jwt_required()
def auth_check():
    return jsonify({"message": "Valid token", "user": get_jwt_identity()}), 200


@app.route('/api/analyze-image', methods=['POST'])
@jwt_required()
def analyze_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No file selected."}), 400

        filename = secure_filename(file.filename)
        filename_without_ext = os.path.splitext(filename)[0]
        jpeg_filename = f"{filename_without_ext}.jpeg"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], jpeg_filename)
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        file.save(original_path)

        try:
            img = Image.open(original_path)
            if img.mode == "RGBA":
                new_img = Image.new("RGB", img.size, (255, 255, 255))
                new_img.paste(img, mask=img.split()[3])
                img = new_img
            img = img.convert("RGB")
            img.save(image_path, "JPEG")
            os.remove(original_path)
        except Exception as e:
            return jsonify({"error": "Image processing failed.", "details": str(e)}), 500

        results = []
        for i in range(4):
            try:
                print(f"Processing image: {image_path}")  # Debug
                prompt = api.generate_gpt_prompt(image_path)
                print(f"Calling GPT API with prompt: {prompt}")  # Debug
                result = api.GPT_Analyze(prompt, image_path)
                json_data = api.convert_to_json(result)
                results.append(json_data)
            except Exception as e:
                return jsonify({"error": f"AI API call failed on iteration {i + 1}", "details": str(e)}), 500

        if not results:
            return jsonify({"error": "AI API did not return any results."}), 500

        averaged_result = {}
        try:
            for key in results[0]:
                values = [res[key] for res in results if isinstance(res[key], (int, float))]
                if values:
                    averaged_result[key] = math.ceil(sum(values) / len(values))
                else:
                    averaged_result[key] = results[0][key]
        except Exception as e:
            return jsonify({"error": "Averaging process failed", "details": str(e)}), 500

        return jsonify(averaged_result)
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


@app.route('/history', methods=['GET', 'POST'])
@jwt_required()
def manage_history():
    user_id = get_jwt_identity()

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'GET':
        try:
            cur.execute("""
                SELECT history_entry
                FROM history
                WHERE user_id = %s
            """, (user_id,))
            result = cur.fetchall()

            cur.close()
            conn.close()

            history_list = [row[0] for row in result] if result else []
            return jsonify({"history": history_list}), 200

        except Exception as e:
            print(f"Error fetching user history: {e}")
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()
            return jsonify({"error": "Failed to fetch history"}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json()
            new_entry = data.get("history_entry")
            if not new_entry or not isinstance(new_entry, dict):
                cur.close()
                conn.close()
                return jsonify({"error": "Invalid history_entry: must be a JSON object"}), 400

            cur.execute("""
                INSERT INTO history (user_id, history_entry)
                VALUES (%s, %s)
                RETURNING history_entry
            """, (user_id, json.dumps(new_entry)))
            new_entry_result = cur.fetchone()

            conn.commit()
            cur.close()
            conn.close()

            return jsonify({"message": "History entry added", "entry": new_entry_result[0]}), 201

        except Exception as e:
            print(f"Error adding user history: {e}")
            if 'conn' in locals():
                conn.rollback()
                if 'cur' in locals():
                    cur.close()
                conn.close()
            return jsonify({"error": "Failed to add history"}), 500


@app.route('/wipe', methods=['GET'])
@jwt_required()
def wipe_history():
    user_id = get_jwt_identity()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM history WHERE user_id = %s", (user_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "success"}), 200

    except Exception as e:
        print(f"Error wiping user history: {e}")
        if 'conn' in locals():
            conn.rollback()
            cur.close()
            conn.close()
        return jsonify({"error": "Failed to wipe history"}), 500


@app.route('/reset-link', methods=['POST'])
def reset_link():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            cur.close()
            conn.close()
            return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200

        user_id, user_email = user

        reset_token = create_access_token(identity=str(user_id), expires_delta=timedelta(hours=1))
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)  # Updated to UTC

        cur.execute("""
            UPDATE users
            SET reset_token = %s, reset_expiry = %s
            WHERE id = %s
        """, (reset_token, expiry, user_id))
        conn.commit()

        send_reset_email(user_email, f'https://macrometer-backend.onrender.com/reset-password?token={reset_token}')

        cur.close()
        conn.close()
        return jsonify({'message': 'If the email exists, a reset link has been sent'}), 200

    except Exception as e:
        print(f"Error in reset_password: {e}")
        if 'conn' in locals():
            conn.rollback()
            if 'cur' in locals():
                cur.close()
            conn.close()
        return jsonify({'error': 'Failed to process reset request'}), 500


@app.route('/reset-password', methods=['GET'])
def reset_password():
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'Token is required'}), 401

    try:
        user_id = decode_token(token)['sub']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reset_expiry
            FROM users
            WHERE reset_token = %s AND id = %s
        """, (token, user_id))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return render_template('invalidToken.html', message="Invalid token or user not found"), 403

        user_id_db, reset_expiry = user
        expiry_dt = datetime.fromisoformat(str(reset_expiry).replace('Z', '+00:00'))
        if expiry_dt < datetime.now(timezone.utc):  # Updated to UTC
            cur.close()
            conn.close()
            return render_template('invalidToken.html', message="Token has expired"), 498

        cur.close()
        conn.close()
        return render_template('resetPassword.html', token=token)

    except Exception as e:
        print(f"Error verifying reset token: {e}")
        if 'conn' in locals():
            if 'cur' in locals():
                cur.close()
            conn.close()
        return render_template('invalidToken.html', message="Invalid token or user not found"), 500


@app.route('/update-password', methods=['POST'])
def update_password():
    token = request.form.get('token')
    new_password = request.form.get('password')
    if not token or not new_password:
        return "Token and password required", 400

    try:
        user_id = decode_token(token)['sub']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reset_expiry
            FROM users
            WHERE reset_token = %s AND id = %s
        """, (token, user_id))
        user = cur.fetchone()
        if not user or datetime.fromisoformat(str(user[1]).replace('Z', '+00:00')) < datetime.now(timezone.utc):  # Updated to UTC
            cur.close()
            conn.close()
            return "Invalid or expired token", 400

        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute("""
            UPDATE users
            SET password = %s, reset_token = NULL, reset_expiry = NULL
            WHERE id = %s
        """, (hashed_password, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return "Password reset successfully!"

    except Exception as e:
        print(f"Error in update_password: {e}")
        if 'conn' in locals():
            conn.rollback()
            if 'cur' in locals():
                cur.close()
            conn.close()
        return "Failed to reset password", 500


@app.route('/feedback', methods=['POST'])
def store_feedback():
    try:
        data = request.get_json()
        feedback_text = data.get("feedback")
        rating = data.get("stars")

        if not feedback_text or rating is None:
            return jsonify({"error": "Missing feedback, rating out of 5, or rating message"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO feedback (feedback, rating, created_at)
            VALUES (%s, %s, NOW())
        """, (feedback_text, rating))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Feedback submitted successfully",
        }), 201
    except Exception as e:
        print(f"Error storing feedback: {e}")
        if 'conn' in locals():
            conn.rollback()
            cur.close()
            conn.close()
        return jsonify({"error": "Failed to store feedback"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)