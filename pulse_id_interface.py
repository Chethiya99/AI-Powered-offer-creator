import streamlit as st
import openai
import json
import re
import requests
from datetime import datetime, timedelta

# Initialize session state
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None
if 'offer_created' not in st.session_state:
    st.session_state.offer_created = False
if 'lms_tokens' not in st.session_state:
    st.session_state.lms_tokens = None

# LMS API Configuration
LMS_AUTH_URL = "https://lmsdev.pulseid.com/1.0/auth/login-v2"
LMS_OFFER_URL = "https://lmsdev-marketplace-api.pulseid.com/offer/show-and-save"
LMS_CREDENTIALS = {
    "email": "randil+offeragent@pulseid.com",
    "password": "Test@123",
    "app": "lms"
}

# Helper functions
def format_currency(amount, escape=True):
    return f"\\${amount}" if escape else f"${amount}"

def get_lms_tokens():
    try:
        response = requests.post(LMS_AUTH_URL, json=LMS_CREDENTIALS)
        if response.status_code == 200:
            data = response.json()
            return data["authToken"], data["permissionToken"]
        st.error(f"Auth failed: {response.text}")
        return None, None
    except Exception as e:
        st.error(f"Auth error: {str(e)}")
        return None, None

def transform_to_lms_format(params):
    """Convert our offer format to LMS API format"""
    return {
        "merchantInfo": {
            "merchant": 1361,
            "locations": []
        },
        "rules": {
            "reward_type": "CASHBACK" if params["offer_type"] == "cashback" else "DISCOUNT",
            "redemption_mechanism": "QR_CODE",
            "code_applicability": "SINGLE_USAGE",
            "upload_mode": "ADD_CODES",
            "reward_limit": params.get("max_redemptions", 100)
        },
        "addRules": {
            "no_end_date": "N",
            "start_date": datetime.now().strftime("%Y-%m-%d 00:00:00"),
            "end_date": (datetime.now() + timedelta(days=params.get("duration_days", 7))).strftime("%Y-%m-%d 23:59:59"),
            "days_of_week": ["EVERYDAY"],
            "timezone": "Asia/Colombo",
            "purchase_channel": "E-COMMERCE"
        },
        "content": [{
            "language": "en",
            "offer_title": params.get("offer_name", "Special Offer"),
            "offer_description": f"{params['value']}% {params['offer_type']}" if params.get("value_type") == "percentage" else f"{format_currency(params['value'], False)} {params['offer_type']}",
            "offer_terms_con": f"Min. spend: {format_currency(params.get('min_spend', 0), False)} | Valid for {params.get('duration_days', 7)} days"
        }]
    }

# Streamlit UI
st.set_page_config(page_title="AI Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")

# API Key Input
openai_api_key = st.text_input("OpenAI API Key:", type="password")
if not openai_api_key:
    st.warning("Please enter your OpenAI API key")
    st.stop()

# Offer Description
user_prompt = st.text_area(
    "Describe your offer:",
    height=100,
    placeholder="E.g., 'Give $20 cashback for first 10 customers spending $500+ in 7 days'"
)

# AI Extraction Function
def extract_offer_params(prompt):
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": """Extract offer details as JSON with:
                {
                    "offer_type": "cashback/discount",
                    "value_type": "percentage/fixed",
                    "value": 20,
                    "min_spend": 50,
                    "duration_days": 7,
                    "offer_name": "name",
                    "max_redemptions": null,
                    "conditions": []
                }"""
            }, {"role": "user", "content": prompt}],
            temperature=0.2
        )
        content = response.choices[0].message.content
        return json.loads(re.sub(r'```json\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL))
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# Main Workflow
if st.button("Generate Offer") and user_prompt:
    with st.spinner("Creating your offer..."):
        st.session_state.offer_params = extract_offer_params(user_prompt)
        if st.session_state.offer_params:
            st.session_state.lms_tokens = get_lms_tokens()

if st.session_state.offer_params:
    # Display Editable Preview
    st.success("✅ Offer created! Review and publish:")
    
    cols = st.columns(2)
    with cols[0]:
        st.session_state.offer_params["offer_name"] = st.text_input(
            "Offer Name", 
            value=st.session_state.offer_params.get("offer_name", "")
        )
        st.session_state.offer_params["value"] = st.number_input(
            "Percentage (%)" if st.session_state.offer_params.get("value_type") == "percentage" else "Amount ($)",
            value=st.session_state.offer_params.get("value", 0)
        )
        
    with cols[1]:
        st.session_state.offer_params["min_spend"] = st.number_input(
            "Minimum Spend ($)",
            value=st.session_state.offer_params.get("min_spend", 0)
        )
        st.session_state.offer_params["duration_days"] = st.number_input(
            "Duration (Days)",
            value=st.session_state.offer_params.get("duration_days", 7)
        )

    # Publish to LMS
    if st.session_state.lms_tokens and st.button("🚀 Publish to LMS"):
        auth_token, perm_token = st.session_state.lms_tokens
        lms_data = transform_to_lms_format(st.session_state.offer_params)
        
        headers = {
            "x-pulse-current-client": "315",
            "x-pulse-token": perm_token,
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        
        with st.spinner("Publishing..."):
            response = requests.post(LMS_OFFER_URL, json=lms_data, headers=headers)
            
            if response.status_code == 200:
                st.balloons()
                st.success("Offer published to LMS!")
                st.json(response.json())
            else:
                st.error(f"Publish failed: {response.text}")

    # Offer Preview Card
    st.markdown("---")
    st.subheader("Offer Preview")
    value_display = f"{st.session_state.offer_params['value']}%" if st.session_state.offer_params.get("value_type") == "percentage" else format_currency(st.session_state.offer_params['value'])
    
    st.markdown(f"""
    **✨ {st.session_state.offer_params.get('offer_name', 'Special Offer')}**  
    💵 **{value_display}** {st.session_state.offer_params['offer_type']}  
    🛒 Min. spend: **{format_currency(st.session_state.offer_params.get('min_spend', 0))}**  
    ⏳ Valid for: **{st.session_state.offer_params.get('duration_days', 7)} days**
    """, unsafe_allow_html=True)
