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
        'email': st.secrets.get("LMS_EMAIL", ""),
        'password': st.secrets.get("LMS_PASSWORD", ""),
        'app': 'lms'
    }

# Helper function for consistent dollar formatting
def format_currency(amount):
    return f"\\${amount}"  # Escaped for Markdown

# LMS Authentication Functions
def authenticate_user(email: str, password: str, app: str):
    url = 'https://lmsdev.pulseid.com/1.0/auth/login-v2'
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        'email': email,
        'password': password,
        'app': app
    }
    response = requests.post(url, headers=headers, json=payload)
    print("authResponse:", response)
    if not response.ok:
        raise Exception('Authentication failed')
    auth_data = response.json()
    print("authData:", auth_data['data']['auth'][0])
    return {
        'permissionToken': auth_data['data']['auth'][0]['permissionToken'],
        'authToken': auth_data['data']['auth'][0]['authToken']
    }

def create_offer(permission_token: str, auth_token: str, params: dict):
    url = 'https://lmsdev-marketplace-api.pulseid.com/offer/show-and-save'
    headers = {
        'x-pulse-current-client': '315',
        'x-pulse-token': permission_token,
        'Authorization': f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }
    print("offer expiry:", params.get('offer_expiry'))
    # Calculate dates based on duration_days
    start_date = datetime.now().strftime("%Y-%m-%d 00:00:00")
    end_date = (datetime.now() + timedelta(days=params.get('duration_days', 7))).strftime("%Y-%m-%d 23:59:59")
    payload = {
        "merchantInfo": {
            "merchant": 1361,
            "locations": []
        },
        "rules": {
            "reward_type": params.get('offer_type', 'DISCOUNT').upper(),
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
        "content": [
            {
                "key": 1,
                "language": "en",
                "offer_title": params.get('offer_name', 'Special Offer'),
                "offer_description": params.get('description', 'Limited time offer'),
                "offer_terms_con": "<ul><li>Offer available at participating locations.</li><li>QR code can only be used once per day.</li></ul>",
                "light_theme_image": [
                    "https://lmsvoxstg-catalyst-client-statics.s3.ap-southeast-1.amazonaws.com/1jo1yUCesO/Hirocoffee.jpg"
                ],
                "dark_theme_image": [],
                "isDefault": True,
                "additional_link": "NO",
                "additional_link_text": "",
                "additional_link_url": "",
                "offer_logo": ""
            }
        ],
        "budget": {
            "maximum_redemption": params.get('max_redemptions', None)
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    print("offerResponse:", response.status_code, response.text)
    return response.json()

def publish_to_lms(params: dict):
    try:
        auth = authenticate_user(
            email=st.session_state.lms_credentials['email'],
            password=st.session_state.lms_credentials['password'],
            app=st.session_state.lms_credentials['app']
        )
        result = create_offer(auth['permissionToken'], auth['authToken'], params)
        return result
    except Exception as e:
        st.error(f"LMS Publishing Error: {str(e)}")
        return None

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English, and let AI extract the details for you!")

# Get OpenAI API key from secrets
openai_api_key = st.secrets.get("OPENAI_API_KEY", "")
if not openai_api_key:
    st.error("OpenAI API key not found in secrets. Please configure the secrets.toml file.")
    st.stop()

# # LMS Credentials Section (display only, not editable)
# with st.expander("LMS Credentials (Configured in secrets.toml)"):
#     st.info(f"LMS Email: {st.session_state.lms_credentials['email']}")
#     st.info("LMS Password: **********")  # Don't show actual password

# User input with better examples
user_prompt = st.text_area(
    "Describe your offer (e.g., 'Give \\$20 cashback for first 10 customers spending \\$500+ in 7 days'):",
    height=100,
    help="Use dollar signs normally - we'll handle the formatting automatically"
)

# Enhanced extraction function
def extract_offer_parameters(prompt, api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer details. Return JSON with:
                    {
                        "offer_type": "cashback/discount/free_shipping",
                        "value_type": "percentage/fixed",
                        "value": 20,
                        "min_spend": 500,
                        "duration_days": 7,
                        "audience": "all/premium/etc",
                        "offer_name": "creative name",
                        "max_redemptions": null,
                        "conditions": [],
                        "description": "marketing text"
                    }"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        if response and response.choices:
            content = response.choices[0].message.content.strip()
            content = re.sub(r'```json\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL)
            return json.loads(content)
        return None
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# Dynamic offer editor - NOW UPDATES SESSION STATE DIRECTLY
def offer_editor():
    cols = st.columns(2)
    with cols[0]:
        st.session_state.adjusted_params["offer_name"] = st.text_input(
            "Offer Name",
            value=st.session_state.adjusted_params.get("offer_name", "")
        )
        st.session_state.adjusted_params["offer_type"] = st.selectbox(
            "Type",
            ["cashback", "discount", "free_shipping"],
            index=["cashback", "discount", "free_shipping"].index(
                st.session_state.adjusted_params.get("offer_type", "cashback")
            )
        )
        st.session_state.adjusted_params["value"] = st.number_input(
            "Percentage (%)" if st.session_state.adjusted_params.get("value_type") == "percentage" else "Amount ($)",
            value=st.session_state.adjusted_params.get("value", 0),
            key="value_input"
        )
    with cols[1]:
        st.session_state.adjusted_params["min_spend"] = st.number_input(
            "Minimum Spend ($)",
            value=st.session_state.adjusted_params.get("min_spend", 0),
            key="min_spend_input"
        )
        st.session_state.adjusted_params["duration_days"] = st.number_input(
            "Duration (Days)",
            value=st.session_state.adjusted_params.get("duration_days", 7),
            key="duration_input"
        )
        if st.session_state.adjusted_params.get("max_redemptions"):
            st.session_state.adjusted_params["max_redemptions"] = st.number_input(
                "Max Redemptions",
                value=st.session_state.adjusted_params.get("max_redemptions"),
                key="max_redemptions_input"
            )

# Offer display component
def display_offer(params):
    end_date = datetime.now() + timedelta(days=params.get("duration_days", 7))
    value_display = f"{params['value']}%" if params.get("value_type") == "percentage" else format_currency(params['value'])
    with st.container():
        st.markdown("---")
        st.subheader("🎉 Your Created Offer")
        cols = st.columns([1, 3])
        with cols[0]:
            icon = "💰" if params.get("offer_type") == "cashback" else "🏷️"
            st.markdown(f"<h1 style='text-align: center;'>{icon}</h1>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"""
            **✨ {params.get('offer_name', 'Special Offer')}**  
            💵 **{value_display}** {params.get('offer_type')}  
            🛒 Min. spend: **{format_currency(params.get('min_spend', 0))}**  
            ⏳ Valid until: **{end_date.strftime('%b %d, %Y')}**  
            👥 For: **{params.get('audience', 'all customers').title()}**
            """, unsafe_allow_html=True)
            if params.get("conditions"):
                st.markdown("**Conditions:**")
                for condition in params["conditions"]:
                    st.markdown(f"- {condition}")
    st.markdown("---")
    # Add publish button only when we have LMS credentials
    if st.session_state.lms_credentials['email'] and st.session_state.lms_credentials['password']:
        if st.button("🚀 Publish to LMS"):
            with st.spinner("Publishing offer to LMS..."):
                result = publish_to_lms(st.session_state.adjusted_params)
                if result:
                    st.success("✅  Offer published to LMS successfully!")
                    st.json(result)
                else:
                    st.error("Failed to publish offer to LMS")
    else:
        st.error("LMS credentials not configured in secrets.toml. Cannot publish to LMS.")

# Main workflow
if st.button("Generate Offer") and user_prompt:
    with st.spinner("Creating your offer..."):
        st.session_state.offer_params = extract_offer_parameters(user_prompt, openai_api_key)
        st.session_state.adjusted_params = st.session_state.offer_params.copy()
        st.session_state.offer_created = True
        st.rerun()

if st.session_state.offer_params:
    st.success("✅  Offer parameters extracted!")
    # Display raw parameters (with formatted currency)
    params_display = st.session_state.offer_params.copy()
    if 'min_spend' in params_display:
        params_display['min_spend'] = format_currency(params_display['min_spend'])
    st.json(params_display)

if st.session_state.offer_created and st.session_state.adjusted_params:
    st.success(":white_check_mark: Adjust the offer below and see changes in real-time:")
    # Edit form - NOW DIRECTLY MODIFIES SESSION STATE
    offer_editor()
    # Display the CURRENTLY EDITED offer (not the original)
    display_offer(st.session_state.adjusted_params)
    if st.button("🔄 Refresh Preview"):
        st.rerun()
