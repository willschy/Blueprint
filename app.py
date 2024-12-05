from flask import Flask, request, jsonify, render_template, Response, send_from_directory
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv
import markdown
import bleach
import json
from datetime import datetime
from openai import OpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__, static_url_path='/static')

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

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Sanitize HTML content for safety
def sanitize_html(content):
    allowed_tags = ['h1', 'h2', 'h3', 'h4', 'p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'a', 'div', 'span']
    allowed_attrs = {
        '*': ['class', 'style'],
        'a': ['href', 'title'],
        'div': ['class']
    }
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attrs, strip=True)

@app.route('/')
def index():
    return render_template('branding_form.html')

@app.route('/branding', methods=['GET'])
def branding_page():
    return render_template('branding_form.html')

@app.route('/branding', methods=['POST'])
def branding_form():
    try:
        data = request.get_json()
        
        def generate():
            try:
                company_name = data.get('company_name', '')
                target_audience = data.get('target_audience', '')
                company_description = data.get('company_description', '')
                email = data.get('email', '')

                # Log submission
                import os
                file_path = os.path.join(os.path.dirname(__file__), "submissions.txt")
                with open(file_path, "a") as f:
                    f.write(f"[{datetime.now()}] Name: {company_name}, Email: {email}\n")

                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Changed from gpt-4o-mini to gpt-4
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
                            
                            Format the response in professional Markdown with clear section headings and concise yet thorough recommendations. Fit within 800 tokens. No horizontal lines."""
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
                        
                        progress += 1
                        current_progress = min(90, int(progress * 1.5))
                        
                        if current_progress > last_progress_sent:
                            last_progress_sent = current_progress
                            yield f"data: {json.dumps({'progress': current_progress, 'content': content})}\n\n"
                        else:
                            yield f"data: {json.dumps({'content': content})}\n\n"

                full_content = ''.join(collected_chunks)
                html_content = markdown.markdown(
                    full_content,
                    extensions=['extra', 'nl2br']
                )
                final_content = f'<div class="insight-section">{sanitize_html(html_content)}</div>'
                
                yield f"data: {json.dumps({'progress': 100, 'content': final_content, 'final': True})}\n\n"

            except Exception as e:
                app.logger.error(f"Error generating insights: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        app.logger.error(f"Error: {e}")
        return jsonify({"error": "An error occurred. Please try again."}), 500

@app.route('/email-results', methods=['POST'])
def email_results():
    try:
        data = request.get_json()
        app.logger.info(f"Received email data: {data}")

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # Extract data
        name = data.get("name")
        email = data.get("email")
        insights = data.get("insights")

        # Validate required fields
        if not all([name, email, insights]):
            app.logger.error(f"Missing fields: Name: {name}, Email: {email}, Insights present: {bool(insights)}")
            return jsonify({"error": "Name, email, and insights are required."}), 400

        # Create email message
        msg = Message(
            subject=f"Your Brand Blueprint, {name}",
            recipients=[email],
            html=f"""
                <p>Hi {name},</p>
                <p>Thank you for using Simple Syrup's Branding Blueprint Tool!<br>
                The attached insights were generated by our AI to spark ideas for your branding journey. 
                These are just starting points, and we'd love to help you take them further if you're interested.<br>
                Let us know if you have any questions or want to explore next steps!</p>
                <div>{insights}</div>
                <p>Best,<br>Will Schlesinger<br>Founder, Simple Syrup<br>"Building brands that stick."</p>
            """
        )

        mail.send(msg)
        app.logger.info(f"Email sent to {email}")
        return jsonify({"message": "Email sent successfully!"}), 200

    except Exception as e:
        app.logger.error(f"Error sending email: {str(e)}")
        return jsonify({"error": "Failed to send email. Please try again later."}), 500

if __name__ == '__main__':
    app.run(debug=True)