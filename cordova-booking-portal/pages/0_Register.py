# pages/0_Register.py
import streamlit as st
from utils.auth import register_public_user

st.title("Cordova Publications Online Booking Portal")
st.subheader("Register")

with st.form("reg_form"):
    name = st.text_input("Full Name *")
    email = st.text_input("Email *").strip().lower()
    phone = st.text_input("Phone *").strip()
    region = st.text_input("Region (optional)").strip()

    role_label = st.selectbox("Register As *", ["Salesperson", "Resource Person (RP)"])
    role = "salesperson" if role_label == "Salesperson" else "rp"

    password = st.text_input("Create Password *", type="password")
    confirm = st.text_input("Confirm Password *", type="password")

    submitted = st.form_submit_button("Create Account", use_container_width=True)

if submitted:
    if not name or not email or not phone or not password or not confirm:
        st.error("Please fill all required fields.")
        st.stop()

    if password != confirm:
        st.error("Passwords do not match.")
        st.stop()

    if len(password) < 8:
        st.error("Password must be at least 8 characters.")
        st.stop()

    try:
        register_public_user(
            name=name,
            email=email,
            phone=phone,
            region=region,
            role=role,
            password=password,
        )
        st.success("Registration successful! You can now login with your email and password.")
        st.page_link("pages/1_Login.py", label="Go to Login", icon="🔐")
    except Exception as e:
        st.error(str(e))

st.divider()
st.page_link("pages/1_Login.py", label="Already registered? Login here", icon="➡️")
