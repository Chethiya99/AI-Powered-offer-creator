import streamlit as st
import openai
import json
import re
from datetime import datetime, timedelta
import requests

# Initialize session state
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None
if 'offer_created' not in st.session_state:
    st.session_state.offer_created = False
if 'adjusted_params' not in st.session_state:
    st.session_state.adjusted_params = None
if 'lms_credentials' not in st.session_state:
    st.session_state.lms_credentials = {
        'email': st.secrets["LMS_EMAIL"],
        'password': st.secrets["LMS_PASSWORD"],
        'app': 'lms'
    }

# Helper function for consistent dollar formatting
def format_currency(amount):
    return f"${amount:,.2f}"

# LMS Authentication Functions
def authenticate_user():
    url = 'https://lmsdev.pulseid.com/1.0/auth/login-v2'
    headers = {'Content-Type': 'application/json'}
    payload = {
        'email': st.session_state.lms_credentials['email'],
        'password': st.session_state.lms_credentials['password'],
        'app': st.session_state.lms_credentials['app']
    }

    response = requests.post(url, headers=headers, json=payload)
    if not response.ok:
        raise Exception(f'Authentication failed: {response.text}')

    auth_data = response.json()
    return {
        'permissionToken': auth_data['data']['auth'][0]['permissionToken'],
        'authToken': auth_data['data']['auth'][0]['authToken']
    }

def create_offer(params: dict):
    try:
        auth = authenticate_user()
        url = 'https://lmsdev-marketplace-api.pulseid.com/offer/show-and-save'
        headers = {
            'x-pulse-current-client': '315',
            'x-pulse-token': auth['permissionToken'],
            'Authorization': f'Bearer {auth['authToken']}',
            'Content-Type': 'application/json'
        }

        # Map offer types to LMS expected values
        offer_type_mapping = {
            'cashback': 'CASHBACK',
            'discount': 'DISCOUNT',
            'free_shipping': 'FREE_SHIPPING'
        }
        reward_type = offer_type_mapping.get(params.get('offer_type', 'discount').lower(), 'DISCOUNT')

        # Calculate dates
        start_date = datetime.now().strftime("%Y-%m-%d 00:00:00")
        end_date = (datetime.now() + timedelta(days=params.get('duration_days', 7))).strftime("%Y-%m-%d 23:59:59")

        payload = {
            "merchantInfo": {"merchant": 1361, "locations": []},
            "rules": {
                "reward_type": reward_type,
                "redemption_mechanism": "QR_CODE",
                "code_applicability": "SINGLE_USAGE",
                "upload_mode": "ADD_CODES",
                "store_locations_codes": [],
                "offer_pin_codes": [],
                "reward_limit": params.get('max_redemptions', 100)
            },
            "addRules": {
                "on_publish_date": "NO",
                "no_end_date": "N",
                "start_date": start_date,
                "end_date": end_date,
                "days_of_week": ["EVERYDAY"],
                "timezone": "Asia/Colombo",
                "timezone_name": "Asia/Colombo",
                "purchase_channel": "E-COMMERCE",
                "offer_tags": []
            },
            "content": [{
                "key": 1,
                "language": "en",
                "offer_title": params.get('offer_name', 'Special Offer'),
                "offer_description": params.get('description', 'Limited time offer'),
                "offer_terms_con": "<ul><li>Offer available at participating locations.</li><li>QR code can only be used once per day.</li></ul>",
                "light_theme_image": ["https://lmsvoxstg-catalyst-client-statics.s3.ap-southeast-1.amazonaws.com/1jo1yUCesO/Hirocoffee.jpg"],
                "dark_theme_image": [],
                "isDefault": True
            }],
            "budget": {
                "maximum_redemption": params.get('max_redemptions', None)
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"LMS Error: {str(e)}")
        return None

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English, and let AI create it for you!")

# Initialize OpenAI (using secrets)
try:
    openai_api_key = st.secrets["OPENAI_API_KEY"]
except Exception as e:
    st.error("OpenAI API key not configured in secrets")
    st.stop()

# AI Extraction Function
def extract_offer_parameters(prompt):
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer details as JSON with: offer_type, value_type, 
                    value, min_spend, duration_days, audience, offer_name, max_redemptions, 
                    conditions, description"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return json.loads(re.sub(r'```json\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL))
    except Exception as e:
        st.error(f"AI Error: {str(e)}")
        return None

# User input with better examples
user_prompt = st.text_area(
    "Describe your offer (e.g., 'Give \\$20 cashback for first 10 customers spending \\$500+ in 7 days'):",
    height=100,
    help="Use dollar signs normally - we'll handle the formatting automatically"
)

# Main Workflow
if st.button("Generate Offer") and user_prompt:
    with st.spinner("Creating your offer..."):
        st.session_state.offer_params = extract_offer_parameters(user_prompt)
        if st.session_state.offer_params:
            st.session_state.adjusted_params = st.session_state.offer_params.copy()
            st.session_state.offer_created = True
            st.rerun()

# Display and Edit Offer
if st.session_state.offer_created and st.session_state.adjusted_params:
    params = st.session_state.adjusted_params
    
    # Editor UI
    with st.expander("✏️ Edit Offer Details", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            params["offer_name"] = st.text_input("Offer Name", value=params.get("offer_name", ""))
            params["offer_type"] = st.selectbox(
                "Type",
                ["cashback", "discount", "free_shipping"],
                index=["cashback", "discount", "free_shipping"].index(params.get("offer_type", "cashback"))
            )
            params["value"] = st.number_input(
                "Value", 
                value=params.get("value", 0),
                format="%f" if params.get("value_type") == "percentage" else None
            )
        
        with cols[1]:
            params["min_spend"] = st.number_input("Minimum Spend", value=params.get("min_spend", 0))
            params["duration_days"] = st.number_input("Duration (Days)", value=params.get("duration_days", 7))
            if params.get("max_redemptions"):
                params["max_redemptions"] = st.number_input("Max Redemptions", value=params.get("max_redemptions"))

    # Preview
    st.subheader("🎉 Offer Preview")
    st.json(params)
    
    # Publish Button
    if st.button("🚀 Publish to LMS"):
        with st.spinner("Publishing..."):
            result = create_offer(params)
            if result:
                st.success("✅ Published successfully!")
                st.json(result)
            else:
                st.error("Failed to publish offer")
