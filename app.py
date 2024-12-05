from flask import Flask, render_template, request, jsonify, Response
from flask_mail import Mail, Message
import os
from openai import OpenAI
from dotenv import load_dotenv
import markdown
import bleach
import json
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask-Mail
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv('MAIL_USERNAME', 'will@simplesyrup.studio'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=('Will Schlesinger', 'will@simplesyrup.studio')
)

mail = Mail(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def store_submission(data):
    """Store form submission data in a text file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "submissions.txt"
    
    with open(filename, 'a') as file:
        file.write(f"Submission Time: {timestamp}\n")
        file.write(f"Company Name: {data.get('company_name', '')}\n")
        file.write(f"Target Audience: {data.get('target_audience', '')}\n")
        file.write(f"Company Description: {data.get('company_description', '')}\n")
        file.write(f"Email: {data.get('email', '')}\n")
        file.write("-" * 50 + "\n\n")  # Separator between entries

# Sanitize HTML content for safety
def sanitize_html(content):
    allowed_tags = ['h1', 'h2', 'h3', 'h4', 'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'div', 'span']
    allowed_attrs = {
        '*': ['class', 'style'],
        'a': ['href', 'title'],
        'div': ['class']
    }
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, strip=True)

@app.route('/', methods=['GET'])
def index():
    return render_template('branding_form.html')

@app.route('/branding', methods=['GET', 'POST'])
def branding_form():
    if request.method == 'POST':
        try:
            data = request.get_json()
            company_name = data.get("company_name", "").strip()
            target_audience = data.get("target_audience", "").strip()
            company_description = data.get("company_description", "").strip()
            email = data.get("email", "").strip()

            if not company_name or not target_audience or not company_description:
                return jsonify({"error": "All fields are required. Please fill out the entire form."}), 400

            # Store the submission data
            store_submission(data)
            
            return generate_branding_insights(company_name, target_audience, company_description)
            
        except Exception as e:
            app.logger.error(f"Error processing request: {str(e)}")
            return jsonify({"error": "An error occurred while generating insights. Please try again later."}), 500

    return render_template("branding_form.html")

def generate_branding_insights(company_name, target_audience, company_description):
    def generate():
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Keep your model as-is
                messages=[
                    {
                        "role": "system",
                        "content": """Create a detailed branding insights report tailored to a small or growing business in the creative or service industries. The report should focus on building a brand that is ownable, scalable, and timeless, in line with Simple Syrup's branding philosophy. Break the report into the following sections, and provide actionable, specific insights in each:
                            1. Brand Positioning Strategy: Define a distinct market position, highlighting differentiation points, competitive advantages, and how the brand can achieve relevance and resonance with its target audience.
                            2. Target Audience Analysis: Describe the ideal customer profile, including demographic, psychographic, and behavioral traits. Explain how these traits inform branding decisions and how to appeal to their needs and desires.
                            3. Messaging Framework: Craft a foundational messaging guide with a suggested mission statement, vision, core values, and a tagline. Include ideas for key messages and elevator pitches that resonate with the audience.
                            4. Visual Identity Possibilities: Suggest ideas for logos, color palettes, typography, and graphic styles that align with the brand's positioning and appeal to the target audience.
                            5. Brand Voice & Tone: Describe the personality of the brand in terms of voice and tone, with examples of how it can adapt across different communication channels while maintaining consistency.
                            6. Marketing Channel Strategy: Recommend the most effective marketing channels for reaching the target audience (e.g., social media, email, events), along with initial ideas for campaigns or strategies to build engagement and growth.
                            
                            Format the response in professional Markdown with clear section headings and concise yet thorough recommendations. Use list format. Fit within 800 tokens. No horizontal lines."""
                    },
                    {
                        "role": "user",
                        "content": f"""
                            Company Name: {company_name}
                            Target Audience: {target_audience}
                            Company Description: {company_description}
                            
                            Please provide detailed, actionable branding recommendations.
                        """
                    }
                ],
                stream=True
            )

            collected_chunks = []
            progress = 0
            last_progress_sent = 0

            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_chunks.append(content)
                    
                    # Send both content and progress updates
                    progress += 1
                    current_progress = min(90, int(progress * 1.5))
                    
                    if current_progress > last_progress_sent:
                        last_progress_sent = current_progress
                        yield f"data: {json.dumps({'progress': current_progress, 'content': content})}\n\n"
                    else:
                        yield f"data: {json.dumps({'content': content})}\n\n"

            # Complete the progress and send final formatted content
            full_content = ''.join(collected_chunks)
            html_content = markdown.markdown(
                full_content,
                extensions=['extra', 'nl2br']  # Add markdown extensions
            )
            final_content = f'<div class="insight-section">{sanitize_html(html_content)}</div>'
            
            yield f"data: {json.dumps({'progress': 100, 'content': final_content, 'final': True})}\n\n"

        except Exception as e:
            app.logger.error(f"Error generating insights: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/email-results', methods=['POST'])
def email_results():
    try:
        data = request.get_json()
        app.logger.info(f"Received email data: {data}")  # Log received data

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # Extract data
        name = data.get("name")
        email = data.get("email")
        insights = data.get("insights")

        # Validate required fields
        if not all([name, email, insights]):
            app.logger.error(f"Missing fields: Name: {name}, Email: {email}, Insights: {insights}")
            return jsonify({"error": "Name, email, and insights are required."}), 400

        # Create email message
        msg = Message(
            subject=f"Your Brand Blueprint, {name}",
            recipients=[email],
            html=f"""
                <p>Hi {name},</p>
                <p>Thank you for using Simple Syrup's Branding Blueprint Tool!<br>The attached insights were generated by our AI to spark ideas for your branding journey. These are just starting points, and we'd love to help you take them further if you're interested.<br>Let us know if you have any questions or want to explore next steps!</p>
                <div>{insights}</div>
                <p>Best,<br>Will Schlesinger<br>Founder, Simple Syrup<br>"Building brands that stick."</p>
            """
        )

        mail.send(msg)  # Send email
        app.logger.info(f"Email sent to {email}")
        return jsonify({"message": "Email sent successfully!"}), 200

    except Exception as e:
        app.logger.error(f"Error sending email: {str(e)}")  # Log error
        return jsonify({"error": "Failed to send email. Please try again later."}), 500

if __name__ == '__main__':
    app.run(debug=True)