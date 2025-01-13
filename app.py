from dotenv import load_dotenv
import logging
from flask import Flask, render_template, request, jsonify, session, url_for, redirect
from authlib.integrations.flask_client import OAuth
import pickle   # To load the saved machine learning model and encoder.
import pandas as pd
import requests
# import json to load JSON data to a python dictionary 
import json 

# urllib.request to make a request to api 
import urllib.request 
import os

load_dotenv()       # Load environment variables from .env file

logging.basicConfig(level=logging.DEBUG)
  
  
app = Flask(__name__) 
app.secret_key = 'AgriTechSecureKey'  # Change this to a secret key
oauth = OAuth(app)


# Setup Google OAuth
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),  # Replace with your Google Client ID
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),  # Replace with your Google Client Secret
    access_token_url='https://oauth2.googleapis.com/token',
    #refresh_token_url=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    #authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'aud': 'GOOGLE_CLIENT_ID',
        
    }
)

# Load the trained model and crop encoder

with open('crop_1_model.pkl', 'rb') as f:
    model = pickle.load(f)

with open('crop_1_encoder.pkl', 'rb') as f:   # The label encoder (crop_1_encoder.pkl) to convert numeric predictions back to crop names.   
    crop_encoder = pickle.load(f)



@app.route('/')
def index():
    if 'user' in session:
        # If the user is logged in, display their profile info or a personalized message
        user_info = session['user']
        return render_template('index.html', user_info=user_info)
    else:
        # If the user is not logged in, show a prompt to log in
        return render_template('index.html')


@app.route('/signup')
def signup():
    # Redirect to the Google OAuth authorization URL
    return redirect(url_for('google_login'))

@app.route('/login')
def login():
   return redirect(url_for('google_login'))

@app.route('/google')
def google_login():
    session.clear()  
    redirect_uri = url_for('authorize', _external=True)   # 'authorize' is the callback route
    #app.logger.debug(f"Redirect URI: {redirect_uri}")  # Log redirect URL
    return google.authorize_redirect(redirect_uri)  # type: ignore

@app.route('/login/callback')
def authorize():
   
        token = google.authorize_access_token()  # type: ignore
        user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()  # type: ignore
        #app.logger.debug(f"Access Token: {token}")
        # user_info = google.get('userinfo').json()  # type: ignore
        #app.logger.debug(f"User Info: {user_info}")
        #user_info = google.parse_id_token(token)
        session['user'] = user_info
        return redirect('/')
   

@app.route('/logout')
def logout():
    session.pop('user', None)
    # Redirect to Google logout (Optional, for logging out from Google as well)
    google_logout_url = "https://accounts.google.com/Logout"
    return redirect(google_logout_url)  # Redirect to Google logout page

  
# Route to handle both POST and GET requests
@app.route('/weather', methods =['POST', 'GET']) 
def weather(): 
        if request.method == 'POST': 
            city = request.form['city']          # Get the city name from the form if the request is POST     
        else: 
            # Default city is 'mumbai' if no city is provided
            city = 'mumbai'
  
        # API key for OpenWeatherMap 
        api_key = 'bfded00eb9ee818074bc2745de187c87'   # Replace with your API Key api_key = 'YOUR_API_KEY'

        try:
    
            # source contain json data from api 
            source = urllib.request.urlopen(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}").read() 
        
            # converting JSON data to a Python dictionary 
            list_of_data = json.loads(source) 
        
            # data for variable list_of_data ( data to display on the webpage )
            data = { 
                "country_code": str(list_of_data['sys']['country']), 
                "coordinate": f"{ str(list_of_data['coord']['lon']) }° { 'E' if (list_of_data['coord']['lon']) >= 0 else 'W'},  { str(list_of_data['coord']['lat']) }° { 'N' if (list_of_data['coord']['lat']) >= 0 else 'S'}", 
                "temp": f"{ str(list_of_data['main']['temp']) } K ", 
                "pressure": f"{ str(list_of_data['main']['pressure'])}mbar ", 
                "humidity":f"{ str(list_of_data['main']['humidity']) }% ", 
                "cityname":str(list_of_data['name']),
                "temp_cel":f"{ str( round( (list_of_data['main']['temp']) - 273.15 , 2) ) } °C ",
            
            } 
            print(data) 
            return render_template('weather.html', data = data) 

        except Exception as e:
            return f"Error fetching weather data: {e}"
        



@app.route('/predict', methods=['POST','GET'])
def predict():

    if request.method == 'POST':

        try:
            # Get input data from the form
            temperature = float(request.form['temperature'])
            humidity = float(request.form['humidity'])
            state = request.form['state']  # Get the state from the dropdown

            # Log the received input for debugging purposes
            app.logger.info(f"Input Data - Temperature: {temperature}, Humidity: {humidity}")

            

            # Create a dataframe for prediction with all required features
            input_data = pd.DataFrame([[temperature, humidity]], columns=['temperature', 'humidity'])

            # Predict the crop index (numeric label) using the trained model
            crop_index = model.predict(input_data)[0]

            # Use the label encoder to convert the numeric index back to a crop name
            crop_name = crop_encoder.inverse_transform([crop_index])[0]

            # Return the result to be rendered on the page
            return render_template('crop_prediction.html', prediction=crop_name)

        except Exception as e:
            app.logger.error(f"Error in prediction: {str(e)}")
            return f"Error in prediction: {str(e)}"
    else:
        return render_template('crop_prediction.html', prediction=None)


 

@app.route('/predict_auto', methods=['POST'])
def predict_auto():
    try:
        # Get JSON data from the request
        data = request.json
        temperature = data['temperature'] # type: ignore # type: ignore
        humidity = data['humidity'] # type: ignore

        # Log received data for debugging
        app.logger.info(f"Auto Prediction Data - Temperature: {temperature}, Humidity: {humidity}")

        # Create input data for the model
        input_data = pd.DataFrame([[temperature, humidity]], columns=['temperature', 'humidity'])

        # Predict the crop index using the trained model
        crop_index = model.predict(input_data)[0]

        # Convert the numeric index to a crop name
        crop_name = crop_encoder.inverse_transform([crop_index])[0]

        # Return the prediction as JSON
        return jsonify({'prediction': crop_name})

    except Exception as e:
        app.logger.error(f"Error in auto prediction: {str(e)}")
        return jsonify({'error': f"Error in auto prediction: {str(e)}"}), 500





@app.route('/prompt', methods=['POST','GET'] )  
def prompt():

    prompt = request.form.get("prompt")

        
    template = {
        "model":"gemma:2b",
        "prompt": prompt,
        "stream":False
    }

    response = requests.post('http://127.0.0.1:11434/api/generate',json=template) 

    llm_response = response.json()
    

    return render_template('chatbot.html', response=llm_response.get('response','No response provided'))




if __name__ == '__main__': 
    app.run(debug = True) 
