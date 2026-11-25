"""Models map onto tables created by database/schema.sql (managed=False),
so the Flask API and Django share one source of truth."""
from datetime import datetime

from django.db import models


class Field(models.Model):
    name = models.CharField(max_length=80)
    crop = models.CharField(max_length=60)
    location = models.CharField(max_length=120)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    boundary = models.TextField(null=True, blank=True)
    owner_id = models.IntegerField(null=True, blank=True)
    contact_phone = models.CharField(max_length=24, null=True, blank=True)
    language = models.CharField(max_length=2, default="en")
    planted_on = models.DateField(null=True, blank=True)
    valve_mode = models.CharField(max_length=4, default="auto")
    valve_state = models.CharField(max_length=6, default="closed")
    valve_until = models.DateTimeField(null=True, blank=True)
    max_run_min = models.IntegerField(default=180)
    area_ha = models.DecimalField(max_digits=6, decimal_places=2)
    root_depth_mm = models.IntegerField()
    flow_lph = models.IntegerField()
    moisture_low = models.DecimalField(max_digits=5, decimal_places=2)
    moisture_high = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = "fields"

    def __str__(self):
        return self.name


class SensorReading(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="readings")
    recorded_at = models.DateTimeField()
    soil_moisture = models.DecimalField(max_digits=5, decimal_places=2)
    soil_temp = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    air_temp = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    humidity = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    battery = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    predicted_6h = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = "sensor_readings"
        ordering = ["-recorded_at"]


class IrrigationSchedule(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="schedules")
    scheduled_for = models.DateTimeField()
    duration_min = models.IntegerField()
    volume_l = models.IntegerField()
    source = models.CharField(max_length=10, default="manual")
    status = models.CharField(max_length=10, default="pending")
    reason = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "irrigation_schedules"
        ordering = ["scheduled_for"]


class Alert(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="alerts")
    level = models.CharField(max_length=10)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=datetime.now)

    class Meta:
        managed = False
        db_table = "alerts"
        ordering = ["-created_at"]


class Sensor(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="sensors")
    device_code = models.CharField(max_length=40, unique=True)
    device_key = models.CharField(max_length=64, null=True, blank=True)
    cal_offset = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cal_scale = models.DecimalField(max_digits=6, decimal_places=3, default=1)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "sensors"


class ValveCommand(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="valve_commands")
    action = models.CharField(max_length=5)
    duration_min = models.IntegerField(null=True, blank=True)
    source = models.CharField(max_length=20, default="manual")
    status = models.CharField(max_length=7, default="pending")
    created_at = models.DateTimeField(default=datetime.now)

    class Meta:
        managed = False
        db_table = "valve_commands"


class Notification(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE, db_column="field_id", related_name="notifications")
    phone = models.CharField(max_length=24, null=True, blank=True)
    channel = models.CharField(max_length=12)
    message = models.CharField(max_length=500)
    status = models.CharField(max_length=12)
    created_at = models.DateTimeField(default=datetime.now)

    class Meta:
        managed = False
        db_table = "notifications"
        ordering = ["-created_at"]
