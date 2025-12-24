from datetime import datetime, timedelta, timezone
from email.policy import default
from django.db import models
from django.contrib.auth.models import User

CATEGORIES = {
    "food": "Food",
    "transport": "Transport",
    "entertainment": "Entertainment",
    "shopping": "Shopping",
    "other": "Other",
    "rent": "Rent",
    "utilities": "Utilities",
    "insurance": "Insurance",
    "education": "Education",
    "health": "Health",
    "other": "Other",
}

class Account(models.Model):
    id = models.AutoField(primary_key=True)
    pid = models.CharField(max_length=50, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    expired_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.user.username
    
    def generate_pid(self):
        import uuid
        self.pid = str(uuid.uuid4())
    
    def save(self, *args, **kwargs):
        if not self.pid:
            self.generate_pid()
        super().save(*args, **kwargs)
        
# Create your models here.
class Family(models.Model):
    id = models.AutoField(primary_key=True)
    pid = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User, related_name='families')
    level = models.IntegerField(default=1)
    max_budget = models.FloatField(default=0)
    currency = models.CharField(max_length=10, default='HKD')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def generate_pid(self):
        import uuid
        self.pid = str(uuid.uuid4())
        
    def save(self, *args, **kwargs):
        if not self.pid:
            self.generate_pid()
        super().save(*args, **kwargs)
        
    def max_members(self):
        return 2 if self.level == 1 else 4

    def can_add_member(self):
        return self.members.count() < self.max_members()

    def add_member(self, user: User):
        # Returns (ok: bool, error: str|None)
        if self.members.filter(id=user.id).exists():
            return False, "User is already a member."
        if not self.can_add_member():
            return False, f"Cannot add more members. Level {self.level} allows only {self.max_members()} members."
        self.members.add(user)
        return True, None

    def remove_member(self, user: User):
        # Returns (ok: bool, error: str|None)
        if not self.members.filter(id=user.id).exists():
            return False, "User is not a member."
        self.members.remove(user)
        return True, None

class Record(models.Model):
    id = models.AutoField(primary_key=True)
    pid = models.CharField(max_length=50, unique=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)
    who = models.ForeignKey(User, on_delete=models.CASCADE, related_name='records', null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)
    amount = models.FloatField(default=0)
    category = models.CharField(max_length=100, choices=CATEGORIES.items(), blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def generate_pid(self):
        import uuid
        self.pid = str(uuid.uuid4())
    
    def save(self, *args, **kwargs):
        if not self.pid:
            self.generate_pid()
        super().save(*args, **kwargs)


class QRCode(models.Model):
    id = models.AutoField(primary_key=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="qrcodes")
    image = models.ImageField(upload_to="qrcodes/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR for {self.family.name} ({self.id})"
