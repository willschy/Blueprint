from flask import Flask, request, jsonify
from PIL import Image
import os

app = Flask(__name__)

# Temporary folder to store uploaded files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Home route
@app.route('/')
def home():
    return "Welcome to the Instant Logo Evaluator!"

# Upload form route
@app.route('/upload')
def upload_form():
    return '''
    <!doctype html>
    <html>
    <head><title>Upload Logo</title></head>
    <body>
        <h1>Upload Your Logo</h1>
        <form method="POST" action="/evaluate" enctype="multipart/form-data">
            <input type="file" name="logo" required>
            <button type="submit">Evaluate</button>
        </form>
    </body>
    </html>
    '''

# Logo evaluation route
@app.route('/evaluate', methods=['POST'])
def evaluate_logo():
    # Check if a file is uploaded
    if 'logo' not in request.files:
        return jsonify({"error": "No logo file uploaded"}), 400

    file = request.files['logo']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # Call the evaluation function
    score, feedback = evaluate_logo_image(filepath)

    # Clean up the uploaded file
    os.remove(filepath)

    return jsonify({"score": score, "feedback": feedback})

# Function to evaluate the logo image
def evaluate_logo_image(filepath):
    try:
        with Image.open(filepath) as img:
            width, height = img.size

            # Basic evaluation rules
            if width < 500 or height < 500:
                return 60, "Your logo resolution is too low for scalability. Consider redesigning it."
            if img.mode in ['1', 'L']:  # Black and white or grayscale
                return 85, "Your logo is versatile in grayscale but consider adding color for more impact."
            return 90, "Your logo looks professional! It’s scalable and clean."
    except Exception as e:
        return 50, "Could not process the image. Please try again."

if __name__ == '__main__':
    app.run(debug=True)
