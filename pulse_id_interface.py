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

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English, and let AI extract the details for you!")

# Securely input OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

# User input: Natural language description
user_prompt = st.text_area(
    "Describe your offer (e.g., 'I want a 10% cashback for purchases over $50, valid for 7 days'):",
    height=100,
)

if not user_prompt:
    st.warning("Please describe your offer.")
    st.stop()

# Function to extract parameters using OpenAI
def extract_offer_parameters(prompt, api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer parameters from the user's description. Return a JSON object with:
                    {
                        "offer_type": "cashback or discount",
                        "percentage": (if applicable),
                        "amount": (if fixed value),
                        "min_spend": (minimum purchase amount),
                        "duration_days": (how long the offer lasts),
                        "audience": "all or premium",
                        "offer_name": "creative name for the offer"
                    }"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        if response and response.choices:
            content = response.choices[0].message.content.strip()
            content = re.sub(r'```json\n(.*?)\n```', r'\1', content, flags=re.DOTALL)
            return json.loads(content)
        else:
            st.error("Error: OpenAI returned an empty response.")
            return None

    except json.JSONDecodeError:
        st.error("Error: Failed to parse JSON response. OpenAI might not be returning structured data.")
        return None
    except Exception as e:
        st.error(f"Error calling OpenAI: {e}")
        return None

# Function to display offer beautifully
def display_offer_card(params):
    end_date = datetime.now() + timedelta(days=params.get("duration_days", 7))
    
    st.markdown("---")
    st.subheader("🎉 Your Created Offer")
    
    # Offer Card Container
    with st.container():
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Offer icon based on type
            icon = "💰" if params.get("offer_type") == "cashback" else "🏷️"
            st.markdown(f"<h1 style='text-align: center;'>{icon}</h1>", unsafe_allow_html=True)
        
        with col2:
            # Offer details
            st.markdown(f"""
            **✨ {params.get('offer_name', 'Special Offer')}**  
            💵 **{params.get('percentage', params.get('amount', 0))}{'%' if 'percentage' in params else '$'}** {'cashback' if params.get('offer_type') == 'cashback' else 'discount'}  
            🛒 Min. spend: **${params.get('min_spend', 0)}**  
            ⏳ Valid until: **{end_date.strftime('%b %d, %Y')}**  
            👥 For: **{params.get('audience', 'all customers').title()}**
            """)
    
    st.markdown("---")
    st.success("This offer is now active! Copy the code below to share with customers.")
    
    # Offer code (generated automatically)
    offer_code = f"OFFER-{params.get('offer_type', '').upper()[:3]}-{params.get('percentage', params.get('amount', ''))}"
    st.code(offer_code, language="text")

# Extract parameters when user submits
if st.button("Generate Offer"):
    with st.spinner("Extracting offer details..."):
        st.session_state.offer_params = extract_offer_parameters(user_prompt, openai_api_key)

if st.session_state.offer_params:
    st.success("✅ Offer parameters extracted!")
    st.subheader("Extracted Parameters")
    st.json(st.session_state.offer_params)

    # Auto-fill a mock form
    st.subheader("📝 Offer Preview (Auto-Filled)")
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox(
            "Offer Type",
            ["Cashback", "Discount", "Free Shipping"],
            index=["cashback", "discount", "free shipping"].index(st.session_state.offer_params.get("offer_type", "cashback")),
        )
        st.number_input(
            "Percentage (%)" if "percentage" in st.session_state.offer_params else "Amount ($)",
            value=st.session_state.offer_params.get("percentage", st.session_state.offer_params.get("amount", 0)),
        )
    with col2:
        st.number_input(
            "Minimum Spend ($)",
            value=st.session_state.offer_params.get("min_spend", 0),
        )
        st.number_input(
            "Duration (Days)",
            value=st.session_state.offer_params.get("duration_days", 7),
        )

    # Final confirmation - THIS IS THE FIXED BUTTON
    if st.button("🚀 Create Offer"):
        st.session_state.offer_created = True

# Show offer only after creation (persists between reruns)
if st.session_state.offer_created and st.session_state.offer_params:
    display_offer_card(st.session_state.offer_params)
    st.balloons()
