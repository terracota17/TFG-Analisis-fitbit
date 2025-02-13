import os
import base64
import hashlib
import requests

from datetime import datetime, timezone


class FitBitAuth:

    def __init__(self, client_id, client_secret):
        
        self.client_id = client_id
        self.client_secret = client_secret

        self.code_verifier = None
        self.code_challenge = None
        self.state = None

     
    """
        Generated code verifier using base64 to encoded it.

        Returns:
            code_verifier (str) : Used for OAuth2.0 with FitBit API.
    """
    def generate_code_verifier(self, length=64):
        code_verifier = base64.urlsafe_b64encode(os.urandom(length)).rstrip(b'=').decode('utf-8')
        self.code_verifier = code_verifier
        return self.code_verifier

    """
        Generates Code challenge using sha256 and base 64.

        Returns:
            code_challenge (str) : Used for OAuth2.0 with FitBit API.
    """
    def generate_code_challenge(self):
        sha256_hash = hashlib.sha256(self.code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(sha256_hash).rstrip(b'=').decode('utf-8')
        self.code_challenge = code_challenge
        return self.code_challenge


    """
        Generates Authorization URL for user to accept terms.

        Returns:
            URL (str) : Generated URL.
    """
    def generate_authorization_url(self, redirect_uri='http://localhost:5000', scopes=None):
        if scopes is None:
            scopes = [
                'activity', 'cardio_fitness', 'electrocardiogram', 'heartrate', 'location',
                'nutrition', 'oxygen_saturation', 'profile', 'respiratory_rate', 'settings',
                'sleep', 'social', 'temperature', 'weight'
            ]
        self.code_verifier = self.generate_code_verifier()
        self.code_challenge = self.generate_code_challenge()
        
        self.state = os.urandom(16).hex()
        scope_string = '+'.join(scopes)
        

        return (f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={self.client_id}"
                f"&scope={scope_string}&code_challenge={self.code_challenge}&code_challenge_method=S256"
                f"&state={self.state}&redirect_uri={redirect_uri}")
                
    """
        Getter for user logged in access token and stores it on MongoDB user account.

        Parameters:
        -code (str) : Code generated by Fitbit API in response of succesful Authentification process.
        state (str) : State generated by Fitbit API in response of succesful Authentification process.

        Returns:
        -response_data["access_token"] (str) : Access token used for fetching data.
        -response_data["refresh_token"] (str) : Refresh Token in case of ReAuth needed.
        -response_data["user_id"] (str) : Fitbit User id that identifies it.

    """
    def get_access_token(self, code, state, redirect_uri="http://localhost:5000"):

        url = "https://api.fitbit.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": self.code_verifier,
        }

        response = requests.post(url, headers=headers, data=data, auth=(self.client_id, self.client_secret))

        if response.status_code == 200:
            response_data = response.json()
            self.storeFibitInfo(response_data["access_token"], 
                                        response_data["refresh_token"], response_data["expires_in"],response_data["user_id"])

            return response_data["access_token"], response_data["refresh_token"], response_data["user_id"]
        else:
            print(f"Error getting access token: {response.status_code}")
            print(response.text)
            return None

    """
        Refresh access token in case of ReAuth needed.

        Parameters:
        -refresh_token (str) : Refresh Token used to get new access_tokens and new refresh_tokens.

        Returns:
        -response_data["access_token"] (str) : Access_token for fetch data.
        -response_data["refresh_token"] (str) : Refresh Token for getting new access_tokens
        -response_data["expires_in"] (DateTime) : Expires in.
        -response_data["user_id"] (str) : FitBit User id 
        -boolean : Returns whether user needs to ReAuth Again because access_token expired.

    """
    def refresh_access_token(self, refresh_token):

        url = "https://api.fitbit.com/oauth2/token"
        
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}"
        }
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            response_data = response.json()

            return response_data["access_token"], response_data["refresh_token"], response_data["expires_in"], response_data["user_id"], False
        else:
            print(f"Error refreshing access token: {response.status_code}")
            return None, None, None, None,True 
    

    """
        Checks whether token is expirede and needed ReAuth from client

        Parameters:
        -access_token (str) : Contains the user last access token.
        -expires_in (datetime) : Contains in DateTime object when the access_token expires at.
        
        Returns:
        -(boolean) : if access token is expired or not.
    """
    def access_token_is_expired(self, access_token, expires_in):

        if access_token and expires_in is not None:
            expires_at_utc = expires_in if expires_in.tzinfo else expires_in.replace(tzinfo=timezone.utc)
          
            return datetime.now(timezone.utc) > expires_at_utc
        else:
            return True
