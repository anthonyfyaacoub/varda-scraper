#!/bin/sh
# Entrypoint script for Railway/Render deployment
# Expands PORT environment variable properly

# Get PORT from Railway (defaults to 8080 if not set)
PORT=${PORT:-8080}

# Unset STREAMLIT_SERVER_PORT if it's set to the literal "$PORT" string
# This prevents Streamlit from reading the unexpanded variable
if [ "$STREAMLIT_SERVER_PORT" = "\$PORT" ] || [ "$STREAMLIT_SERVER_PORT" = '$PORT' ]; then
    unset STREAMLIT_SERVER_PORT
fi

# Export the actual port number
export STREAMLIT_SERVER_PORT=$PORT

# Run Streamlit with explicit port argument
exec streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
