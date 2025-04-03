import streamlit as st
import openai
import json

# Streamlit UI Setup
st.set_page_config(page_title="AI-Powered Offer Creator", page_icon="✨")
st.title("💡 AI-Powered Offer Creator")
st.markdown("Describe your offer in plain English, and let AI extract the details for you!")

# Securely input OpenAI API key
openai_api_key = st.text_input("Enter your OpenAI API Key:", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API key to proceed.")
    st.stop()

openai.api_key = openai_api_key

# User input: Natural language description
user_prompt = st.text_area(
    "Describe your offer (e.g., 'I want a 10% cashback for purchases over $50, valid for 7 days'):",
    height=100,
)

if not user_prompt:
    st.warning("Please describe your offer.")
    st.stop()

# Function to extract parameters using OpenAI
def extract_offer_parameters(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """Extract offer parameters from the user's description. Return a JSON with:
- "offer_type" (e.g., "cashback", "discount")
- "percentage" (if applicable)
- "amount" (if fixed value)
- "min_spend" (minimum purchase amount)
- "duration_days" (how long the offer lasts)
- "audience" (e.g., "all", "premium")""",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return json.loads(response.choices[0].message["content"])
    except Exception as e:
        st.error(f"Error calling OpenAI: {e}")
        return None

# Extract parameters when user submits
if st.button("Generate Offer"):
    with st.spinner("Extracting offer details..."):
        offer_params = extract_offer_parameters(user_prompt)

    if offer_params:
        st.success("✅ Offer parameters extracted!")
        st.subheader("Extracted Parameters")
        st.json(offer_params)

        # Auto-fill a mock form
        st.subheader("📝 Offer Preview (Auto-Filled)")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox(
                "Offer Type",
                ["Cashback", "Discount", "Free Shipping"],
                index=0 if offer_params.get("offer_type") == "cashback" else 1,
            )
            st.number_input(
                "Percentage (%)" if offer_params.get("percentage") else "Amount ($)",
                value=offer_params.get("percentage") or offer_params.get("amount"),
            )
        with col2:
            st.number_input(
                "Minimum Spend ($)",
                value=offer_params.get("min_spend", 0),
            )
            st.number_input(
                "Duration (Days)",
                value=offer_params.get("duration_days", 7),
            )

        # Final confirmation
        if st.button("🚀 Create Offer"):
            st.balloons()
            st.success("Offer created successfully! (Demo)")
    else:
        st.error("Failed to extract parameters. Try a clearer description.")
