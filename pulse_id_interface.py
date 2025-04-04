import streamlit as st
import openai
import json
import re
from datetime import datetime, timedelta

# Initialize session state
if 'offer_params' not in st.session_state:
    st.session_state.offer_params = None
if 'offer_created' not in st.session_state:
    st.session_state.offer_created = False
if 'adjusted_params' not in st.session_state:
    st.session_state.adjusted_params = None

# Enhanced currency formatting helper
def format_currency(amount, escape=True):
    """Handles dollar signs consistently throughout the app"""
    if escape:
        return f"\\${amount}"  # Escaped for Markdown
    return f"${amount}"  # For non-Markdown contexts

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")

# Input section with proper dollar sign examples
with st.expander("💡 How to describe offers", expanded=True):
    st.markdown("""
    Examples:
    - `Give 10% cashback for orders over \\$50`
    - `\\$20 fixed discount for first 100 customers`
    - `15% off for premium members spending \\$200+`
    """)

# Securely input OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

# User input with safe rendering
user_prompt = st.text_area(
    "Describe your offer:",
    height=100,
    help="Include amounts like $20 or percentages like 10%"
)

# Enhanced extraction with dollar sign sanitization
def extract_offer_parameters(prompt, api_key):
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer details. NEVER include $ signs in JSON values. Return:
                    {
                        "offer_type": "cashback/discount/free_shipping",
                        "value_type": "percentage/fixed",
                        "value": 20, // NEVER $20
                        "min_spend": 50, // NEVER $50
                        "duration_days": 7,
                        "audience": "all/premium/etc",
                        "offer_name": "name",
                        "max_redemptions": null,
                        "conditions": [],
                        "description": "text WITHOUT $ signs"
                    }"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        if response and response.choices:
            content = response.choices[0].message.content.strip()
            content = re.sub(r'```json\n?(.*?)\n?```', r'\1', content, flags=re.DOTALL)
            # Remove any remaining $ signs in values
            content = re.sub(r'"(\$?)(\d+)"', r'"\2"', content)
            return json.loads(content)
        return None
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# Form builder with safe dollar rendering
def build_offer_form(params):
    cols = st.columns(2)
    with cols[0]:
        params["offer_name"] = st.text_input(
            "Offer Name", 
            value=params.get("offer_name", ""),
            key="offer_name_input"
        )
        params["offer_type"] = st.selectbox(
            "Type",
            ["cashback", "discount", "free_shipping"],
            index=["cashback", "discount", "free_shipping"].index(
                params.get("offer_type", "cashback")
            ),
            key="offer_type_input"
        )
        
        # Dynamic value input
        value_label = "Percentage (%)" if params.get("value_type") == "percentage" else f"Amount ({format_currency(0, escape=False)})"
        params["value"] = st.number_input(
            value_label,
            value=params.get("value", 0),
            key="value_input"
        )
    
    with cols[1]:
        params["min_spend"] = st.number_input(
            f"Minimum Spend ({format_currency(0, escape=False)})",
            value=params.get("min_spend", 0),
            key="min_spend_input"
        )
        params["duration_days"] = st.number_input(
            "Duration (Days)",
            value=params.get("duration_days", 7),
            key="duration_input"
        )
        if params.get("max_redemptions"):
            params["max_redemptions"] = st.number_input(
                "Max Redemptions",
                value=params.get("max_redemptions"),
                key="max_redemptions_input"
            )

# Offer display with perfect dollar handling
def display_offer(params):
    end_date = datetime.now() + timedelta(days=params.get("duration_days", 7))
    value_display = (
        f"{params['value']}%" 
        if params.get("value_type") == "percentage" 
        else format_currency(params['value'])
    )
    
    with st.container():
        st.markdown("---")
        st.subheader("🎉 Final Offer")
        
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
                    st.markdown(f"- {condition.replace('$', '\\$')}")
    
    st.markdown("---")
    st.success("Offer is ready to use!")

# Main workflow
if st.button("Generate Offer") and user_prompt:
    with st.spinner("Creating your offer..."):
        st.session_state.offer_params = extract_offer_parameters(user_prompt, openai_api_key)
        if st.session_state.offer_params:
            st.session_state.adjusted_params = json.loads(json.dumps(st.session_state.offer_params))  # Deep copy
            st.session_state.offer_created = True
            st.rerun()

if st.session_state.offer_created and st.session_state.adjusted_params:
    st.success("✅ Adjust your offer below:")
    
    # Build the editing form
    build_offer_form(st.session_state.adjusted_params)
    
    # Display the current offer (updates live)
    display_offer(st.session_state.adjusted_params)
    
    # Debug view (optional)
    with st.expander("Debug: Current Offer Data"):
        st.json(st.session_state.adjusted_params)
