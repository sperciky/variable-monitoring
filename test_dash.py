import dash
from dash import html, dcc
import sys

print("Testing Dash installation...")

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Dash Test"),
    html.P("If you see this, Dash is working!")
])

if __name__ == '__main__':
    print("Starting test server on http://127.0.0.1:8050")
    try:
        app.run(debug=True, host='127.0.0.1', port=8050)
    except Exception as e:
        print(f"Error: {e}")
        print("\nTry running: pip install --upgrade dash")