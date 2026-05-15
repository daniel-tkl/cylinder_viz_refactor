import base64
import streamlit as st

sidebar_img = "./assets/tkl_navbar.png"

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        
@st.cache_data()
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_bg(png_file):
    """Set background using PNG file."""
    bin_str = get_base64_of_bin_file(png_file)
    page_bg_img = '''
    <style>
    .stApp {
        background-image: url("data:image/png;base64,%s");
        background-size: cover;
    }
    </style>
    ''' % bin_str
    st.markdown(page_bg_img, unsafe_allow_html=True)
    return

def set_sidebar_img(sidebar_img= sidebar_img):
    with open(sidebar_img, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
        st.sidebar.markdown(
            f"""
            <div style="display:table;margin-top:-40%;margin-left:25%;">
                <img src="data:image/png;base64,{data}" width="100" height="150">
            </div>
            """,
            unsafe_allow_html=True,
        )
    return