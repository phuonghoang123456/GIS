from django.db import models


class Location(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    province = models.CharField(max_length=255)
    geometry = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "locations"
        managed = False


class RainfallData(models.Model):
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.DO_NOTHING, db_column="location_id")
    date = models.DateField()
    rainfall_mm = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "rainfall_data"
        managed = False


class TemperatureData(models.Model):
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.DO_NOTHING, db_column="location_id")
    date = models.DateField()
    temp_min = models.FloatField(null=True, blank=True)
    temp_max = models.FloatField(null=True, blank=True)
    temp_mean = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "temperature_data"
        managed = False


class SoilMoistureData(models.Model):
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.DO_NOTHING, db_column="location_id")
    date = models.DateField()
    sm_surface = models.FloatField(null=True, blank=True)
    sm_rootzone = models.FloatField(null=True, blank=True)
    sm_profile = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "soil_moisture_data"
        managed = False


class NdviData(models.Model):
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.DO_NOTHING, db_column="location_id")
    date = models.DateField()
    ndvi_mean = models.FloatField(null=True, blank=True)
    ndvi_min = models.FloatField(null=True, blank=True)
    ndvi_max = models.FloatField(null=True, blank=True)
    ndvi_stddev = models.FloatField(null=True, blank=True)
    vegetation_area_pct = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "ndvi_data"
        managed = False


class TvdiData(models.Model):
    id = models.BigAutoField(primary_key=True)
    location = models.ForeignKey(Location, on_delete=models.DO_NOTHING, db_column="location_id")
    date = models.DateField()
    tvdi_mean = models.FloatField(null=True, blank=True)
    tvdi_min = models.FloatField(null=True, blank=True)
    tvdi_max = models.FloatField(null=True, blank=True)
    lst_mean = models.FloatField(null=True, blank=True)
    drought_area_pct = models.FloatField(null=True, blank=True)
    drought_class = models.CharField(max_length=50, null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "tvdi_data"
        managed = False
