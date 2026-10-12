import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from configdb import credentials
from sensors.sensors import sensors
from flask_jwt_extended import JWTManager
from sensor_logs.sensor_logs import sensor_logs
from authentication.authentication import authentication
from simulation.simulation_service import start_background_tasks

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
app.config["JWT_SECRET_KEY"] = SECRET_KEY
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config.from_object(credentials)
app.config['JWT_TOKEN_LOCATION'] = ["headers"]
jwt = JWTManager(app)

app.register_blueprint(sensors)
app.register_blueprint(sensor_logs)
app.register_blueprint(authentication)

@app.route('/')
def welcome():
    return '¡Bienvendido!'

if __name__ == '__main__':
    start_background_tasks()
    app.run(host='0.0.0.0', port=5000, debug=False)
