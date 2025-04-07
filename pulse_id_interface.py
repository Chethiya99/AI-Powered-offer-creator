import streamlit as st
import openai
import json
import re
import requests
from datetime import datetime, timedelta

# Initialize session state
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None
if 'lms_auth' not in st.session_state:
    st.session_state.lms_auth = {
        'auth_token': None,
        'permission_token': None,
        'last_refreshed': None
    }

# LMS Configuration
LMS_CONFIG = {
    'AUTH_URL': "https://lmsdev.pulseid.com/1.0/auth/login-v2",
    'OFFER_URL': "https://lmsdev-marketplace-api.pulseid.com/offer/show-and-save",
    'CLIENT_ID': "315",
    'MERCHANT_ID': 1361,
    'CREDENTIALS': {
        "email": "randil+offeragent@pulseid.com",
        "password": "Test@123",  # Replace with st.secrets in production
        "app": "lms"
    }
}

# Auth Management
def refresh_lms_tokens():
    """Get fresh LMS tokens with error handling"""
    try:
        response = requests.post(
            LMS_CONFIG['AUTH_URL'],
            json=LMS_CONFIG['CREDENTIALS'],
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.lms_auth = {
                'auth_token': data["authToken"],
                'permission_token': data["permissionToken"],
                'last_refreshed': datetime.now()
            }
            return True
        else:
            st.error(f"Auth Failed (HTTP {response.status_code}): {response.text}")
    except Exception as e:
        st.error(f"Auth Connection Error: {str(e)}")
    return False

def get_valid_tokens():
    """Returns valid tokens, refreshing if needed"""
    if not st.session_state.lms_auth['auth_token']:
        if not refresh_lms_tokens():
            return None, None
    
    # Optional: Add token expiration check here if LMS provides expires_in
    return (
        st.session_state.lms_auth['auth_token'],
        st.session_state.lms_auth['permission_token']
    )

# Offer Transformation
def build_lms_payload(offer_params):
    """Convert our format to LMS API spec"""
    end_date = datetime.now() + timedelta(days=offer_params.get("duration_days", 7))
    
    return {
        "merchantInfo": {
            "merchant": LMS_CONFIG['MERCHANT_ID'],
            "locations": []
        },
        "rules": {
            "reward_type": "CASHBACK" if offer_params["offer_type"] == "cashback" else "DISCOUNT",
            "redemption_mechanism": "QR_CODE",
            "code_applicability": "SINGLE_USAGE",
            "reward_limit": offer_params.get("max_redemptions", 100),
            "store_locations_codes": []
        },
        "addRules": {
            "no_end_date": "N",
            "start_date": datetime.now().strftime("%Y-%m-%d 00:00:00"),
            "end_date": end_date.strftime("%Y-%m-%d 23:59:59"),
            "timezone": "Asia/Colombo",
            "purchase_channel": "E-COMMERCE"
        },
        "content": [{
            "language": "en",
            "offer_title": offer_params.get("offer_name", "Special Offer"),
            "offer_description": build_offer_description(offer_params),
            "offer_terms_con": build_offer_terms(offer_params)
        }]
    }

def build_offer_description(params):
    """Generate marketing-friendly description"""
    value_part = f"{params['value']}%" if params["value_type"] == "percentage" else f"${params['value']}"
    return f"{value_part} {params['offer_type']} on orders over ${params.get('min_spend', 0)}"

def build_offer_terms(params):
    """Generate formatted terms"""
    terms = [
        f"Valid until {(datetime.now() + timedelta(days=params.get('duration_days', 7)):%b %d, %Y}",
        f"Min. spend: ${params.get('min_spend', 0)}"
    ]
    if params.get("max_redemptions"):
        terms.append(f"First {params['max_redemptions']} customers only")
    return "\n".join([f"• {term}" for term in terms])

# Streamlit UI
st.set_page_config(page_title="LMS Offer Creator", page_icon="✨")
st.title("🚀 LMS Offer Creator")

# 1. Authentication Section
with st.expander("🔐 LMS Authentication", expanded=True):
    if st.button("Authenticate with LMS"):
        if refresh_lms_tokens():
            st.success("Successfully authenticated with LMS!")
    
    if st.session_state.lms_auth['auth_token']:
        st.info(f"Last authenticated: {st.session_state.lms_auth['last_refreshed']:%Y-%m-%d %H:%M}")
    else:
        st.warning("Not authenticated with LMS")

# 2. Offer Creation
openai_api_key = st.text_input("OpenAI API Key:", type="password")
user_prompt = st.text_area("Describe your offer:", height=100)

if st.button("Generate Offer") and user_prompt and openai_api_key:
    with st.spinner("Analyzing your offer..."):
        try:
            client = openai.OpenAI(api_key=openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "system",
                    "content": """Extract offer details as JSON with:
                    offer_type, value_type, value, min_spend, duration_days, 
                    offer_name, max_redemptions, conditions"""
                }, {"role": "user", "content": user_prompt}],
                temperature=0.2
            )
            content = re.sub(r'```json\n?(.*?)\n?```', r'\1', response.choices[0].message.content, flags=re.DOTALL)
            st.session_state.offer_params = json.loads(content)
            st.success("Offer parameters extracted!")
        except Exception as e:
            st.error(f"Error generating offer: {str(e)}")

# 3. Offer Preview & Publishing
if st.session_state.offer_params:
    st.subheader("📝 Offer Preview")
    
    # Editable Fields
    cols = st.columns(2)
    with cols[0]:
        st.session_state.offer_params["offer_name"] = st.text_input(
            "Offer Name", 
            value=st.session_state.offer_params.get("offer_name", "Special Offer")
        )
        st.session_state.offer_params["value"] = st.number_input(
            "Value", 
            value=st.session_state.offer_params["value"]
        )
        
    with cols[1]:
        st.session_state.offer_params["min_spend"] = st.number_input(
            "Minimum Spend", 
            value=st.session_state.offer_params.get("min_spend", 0)
        )
        st.session_state.offer_params["duration_days"] = st.number_input(
            "Duration (Days)", 
            value=st.session_state.offer_params.get("duration_days", 7)
        )
    
    # Publish Button
    if st.button("🚀 Publish to LMS"):
        auth_token, perm_token = get_valid_tokens()
        
        if not auth_token:
            st.error("Cannot publish - authentication required")
            st.stop()
            
        lms_payload = build_lms_payload(st.session_state.offer_params)
        
        with st.spinner("Publishing offer..."):
            try:
                response = requests.post(
                    LMS_CONFIG['OFFER_URL'],
                    json=lms_payload,
                    headers={
                        "x-pulse-current-client": LMS_CONFIG['CLIENT_ID'],
                        "x-pulse-token": perm_token,
                        "Authorization": f"Bearer {auth_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    st.balloons()
                    st.success("Successfully published to LMS!")
                    st.json(response.json())
                else:
                    st.error(f"Publish failed (HTTP {response.status_code}): {response.text}")
                    # Auto-refresh tokens on auth errors
                    if response.status_code in [401, 403]:
                        st.info("Attempting to refresh tokens...")
                        if refresh_lms_tokens():
                            st.rerun()
            except requests.Timeout:
                st.error("Request timeout - please try again")
            except Exception as e:
                st.error(f"Publish error: {str(e)}")
    
    # Offer Preview
    st.markdown("---")
    st.markdown(f"### {st.session_state.offer_params['offer_name']}")
    st.markdown(f"**Value:** {st.session_state.offer_params['value']}{'%' if st.session_state.offer_params['value_type'] == 'percentage' else '$'}") 
    st.markdown(f"**Minimum Spend:** ${st.session_state.offer_params.get('min_spend', 0)}")
    st.markdown(f"**Duration:** {st.session_state.offer_params.get('duration_days', 7)} days")
