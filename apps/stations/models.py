from django.db import models


class FuelStation(models.Model):
    """Represents a clean, geocoded fuel station with retail pricing."""

    opis_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField()

    price = models.DecimalField(max_digits=6, decimal_places=4)
    price_min = models.DecimalField(max_digits=6, decimal_places=4)
    price_max = models.DecimalField(max_digits=6, decimal_places=4)
    n_price_rows = models.IntegerField()

    lat = models.FloatField()
    lng = models.FloatField()

    geocode_method = models.CharField(max_length=30)
    geocode_confidence = models.FloatField()
    price_outlier = models.BooleanField(default=False)

    class Meta:
        ordering = ["opis_id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.opis_id}) - {self.city}, {self.state} (${self.price})"
