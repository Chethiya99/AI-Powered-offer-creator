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
                        "audience": "all or premium"
                    }"""
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        # DEBUG: Print raw API response (temporarily)
        st.write("Raw API Response:", response)

        # Extract content safely
        if response and response.choices:
            content = response.choices[0].message.content.strip()
            return json.loads(content)  # Convert string to dictionary
        else:
            st.error("Error: OpenAI returned an empty response.")
            return None

    except json.JSONDecodeError:
        st.error("Error: Failed to parse JSON response. OpenAI might not be returning structured data.")
        return None
    except Exception as e:
        st.error(f"Error calling OpenAI: {e}")
        return None

# Extract parameters when user submits
if st.button("Generate Offer"):
    with st.spinner("Extracting offer details..."):
        offer_params = extract_offer_parameters(user_prompt, openai_api_key)

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
                index=["cashback", "discount", "free shipping"].index(offer_params.get("offer_type", "cashback")),
            )
            st.number_input(
                "Percentage (%)" if "percentage" in offer_params else "Amount ($)",
                value=offer_params.get("percentage", offer_params.get("amount", 0)),
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
