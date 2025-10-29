from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Family(models.Model):
    id = models.AutoField(primary_key=True)
    pid = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(User, related_name='families')
    level = models.IntegerField(default=1)
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