import yaml
import streamlit as st
from streamlit import session_state as ss
import streamlit_authenticator as stauth

CONFIG_FILENAME = 'web/config.yaml'
with open(CONFIG_FILENAME) as file:
    config = yaml.load(file, Loader=yaml.SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
    )

with open(CONFIG_FILENAME, 'w') as file:
    yaml.dump(config, file, default_flow_style=False)