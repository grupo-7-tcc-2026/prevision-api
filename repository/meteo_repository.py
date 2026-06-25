import openmeteo_requests

import pandas as pd
import requests_cache
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

class MeteoRepository(object):
    
    def __init__(self, lat, long, start_dt, end_dt):
        self.url = "https://api.open-meteo.com/v1/forecast"
        self.params = {
            "latitude": lat,
            "longitude": long,
            "hourly": ["rain", "precipitation", "precipitation_probability"],
            "current": ["temperature_2m", "relative_humidity_2m", "rain"],
            "start_date": start_dt,
            "end_date": end_dt,
        }
        self.responses = None

    def get(self):
        self.responses = openmeteo.weather_api(self.url, params = self.params)

        response = self.responses[0]

        # Process hourly data. The order of variables needs to be the same as requested.
        hourly = response.Hourly()
        hourly_rain = hourly.Variables(0).ValuesAsNumpy()
        hourly_precipitation = hourly.Variables(1).ValuesAsNumpy()
        hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()

        hourly_data = {
            "date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            ).astype(str).tolist()  # <-- Conversão para string e depois lista
        }

        # Conversão dos arrays do Numpy para listas nativas do Python
        hourly_data["rain"] = hourly_rain.tolist()
        hourly_data["precipitation"] = hourly_precipitation.tolist()
        hourly_data["precipitation_probability"] = hourly_precipitation_probability.tolist()

        return hourly_data

    def get_current(self):
        responses = openmeteo.weather_api(self.url, params=self.params)
        response = responses[0]
        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()
        current_relative_humidity_2m = current.Variables(1).Value()
        current_rain = current.Variables(2).Value()
        current_data = {
            "rain": current_rain,
            "relative_humidity": current_relative_humidity_2m,
            "temperature": current_temperature_2m,
        }

        return current_data