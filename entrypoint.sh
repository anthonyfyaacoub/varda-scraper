#!/bin/sh
# Entrypoint script for Railway/Render deployment
# Expands PORT environment variable properly

PORT=${PORT:-8080}
export STREAMLIT_SERVER_PORT=$PORT

exec streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
