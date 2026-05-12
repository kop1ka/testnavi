from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Flask test project root"})

@app.route('/api/hello')
def hello():
    return jsonify({"greeting": "Hello from Flask test project!"})

if __name__ == '__main__':
    app.run(debug=True)
