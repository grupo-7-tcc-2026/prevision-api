from repository.meteo_repository import MeteoRepository

class MeteoService:
    def __init__(self, lat, long, start_dt, end_dt):
        self.lat = lat
        self.long = long
        self.start_dt = start_dt,
        self.end_dt = end_dt
        self.meteo_rep = MeteoRepository(self.lat,self.long,self.start_dt, self.end_dt)

    def get(self):
            return self.meteo_rep.get()

    def get_current(self):
        return self.meteo_rep.get_current()