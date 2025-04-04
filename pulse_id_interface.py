import streamlit as st
import openai
import json
import re
from datetime import datetime, timedelta

# Initialize session state
if 'offer_created' not in st.session_state:
    st.session_state.offer_created = False
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None

# Helper function for consistent dollar formatting
def format_currency(amount):
    """Ensures $ signs display properly in Markdown"""
    return f"\\${amount}"  # Escaped for Markdown

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English, and let AI extract the details for you!")

# Securely input OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

# User input with better examples
user_prompt = st.text_area(
    "Describe your offer (e.g., 'Give \\$20 cashback for first 10 customers spending \\$500+ in 7 days'):",
    height=100,
    help="Use dollar signs normally - we'll handle the formatting automatically"
)

if not user_prompt:
    st.warning("Please describe your offer.")
    st.stop()

# Enhanced extraction with currency handling
def extract_offer_parameters(prompt, api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer details and format ALL currency values as numbers (without $ signs). Return JSON with:
                    {
                        "offer_type": "cashback/discount/free_shipping",
                        "value_type": "percentage/fixed",
                        "value": 20 (NOT $20),
                        "min_spend": 500 (NOT $500),
                        "duration_days": 7,
                        "audience": "all/premium/etc",
                        "offer_name": "creative name",
                        "max_redemptions": 10,
                        "conditions": ["first X customers"],
                        "description": "marketing text WITHOUT $ signs"
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
        st.error(f"Error: {str(e)}")
        return None

# Unified currency display in offer card
def display_offer_card(params):
    end_date = datetime.now() + timedelta(days=params.get("duration_days", 7))
    
    # Format all currency values consistently
    value_display = f"{params['value']}%" if params.get('value_type') == 'percentage' else format_currency(params['value'])
    min_spend_display = format_currency(params.get('min_spend', 0))
    
    st.markdown("---")
    st.subheader("🎉 Your Created Offer")
    
    with st.container():
        col1, col2 = st.columns([1, 3])
        
        with col1:
            icon = "🎯" if params.get('max_redemptions') else "💰" if params.get("offer_type") == "cashback" else "🏷️"
            st.markdown(f"<h1 style='text-align: center;'>{icon}</h1>", unsafe_allow_html=True)
        
        with col2:
            # Using st.markdown with escaped $ signs
            st.markdown(f"""
            **✨ {params.get('offer_name', 'Exclusive Offer')}**  
            💵 **{value_display}** {params.get('offer_type').replace('_', ' ')}  
            🛒 Min. spend: **{min_spend_display}**  
            ⏳ Ends: **{end_date.strftime('%b %d, %Y')}**  
            👥 For: **{params.get('audience', 'eligible customers').title()}**
            """, unsafe_allow_html=True)
            
            if params.get('max_redemptions'):
                st.markdown(f"🔢 **First {params['max_redemptions']} customers only**")
            
            if params.get('conditions'):
                st.markdown("📌 **Conditions:**")
                for condition in params['conditions']:
                    st.markdown(f"- {condition.capitalize()}")

    # Clean description rendering
    description = params.get('description', 'Special limited-time offer').replace('$', '\\$')
    st.markdown(f"📝 **Description:** {description}", unsafe_allow_html=True)
    
    st.markdown("---")
    st.success("This offer is now active! Share this code with customers:")
    
    # Generate offer code (no formatting issues here)
    base_code = f"OFFER-{params.get('offer_type', '').upper()[:4]}"
    if params.get('max_redemptions'):
        base_code += f"-LIM{params['max_redemptions']}"
    st.code(f"{base_code}-{params['value']}{'P' if params.get('value_type') == 'percentage' else 'F'}")

# Processing flow
if st.button("Generate Offer"):
    with st.spinner("Analyzing your offer..."):
        st.session_state.offer_params = extract_offer_parameters(user_prompt, openai_api_key)

if st.session_state.offer_params:
    st.success("✅ Offer parameters extracted!")
    
    # Display raw parameters (with formatted currency)
    params_display = st.session_state.offer_params.copy()
    if 'min_spend' in params_display:
        params_display['min_spend'] = format_currency(params_display['min_spend'])
    st.json(params_display)

    # Form preview with consistent formatting
    st.subheader("📝 Offer Preview")
    cols = st.columns(2)
    with cols[0]:
        st.text_input("Offer Name", value=st.session_state.offer_params.get('offer_name', ''))
        offer_type = st.session_state.offer_params.get("offer_type", "cashback")
        st.selectbox("Type", ["Cashback", "Discount", "Free Shipping"], 
                    index=["cashback", "discount", "free_shipping"].index(offer_type))
        
        value_label = "Percentage (%)" if st.session_state.offer_params.get('value_type') == 'percentage' else f"Amount ({format_currency(0)[:-1]})"
        st.number_input(value_label, value=st.session_state.offer_params.get('value', 0))
        
    with cols[1]:
        st.number_input(f"Min. Spend ({format_currency(0)[:-1]})", 
                      value=st.session_state.offer_params.get('min_spend', 0))
        st.number_input("Duration (Days)", value=st.session_state.offer_params.get('duration_days', 7))
        if st.session_state.offer_params.get('max_redemptions'):
            st.number_input("Max Redemptions", value=st.session_state.offer_params['max_redemptions'])

    if st.button("🚀 Create Offer Now"):
        st.session_state.offer_created = True

if st.session_state.offer_created and st.session_state.offer_params:
    display_offer_card(st.session_state.offer_params)
    st.balloons()
    
