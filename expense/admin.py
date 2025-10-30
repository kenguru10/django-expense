from django.contrib import admin
from .models import Family, Account, Record

# Register your models here.
admin.site.register(Family)
admin.site.register(Account)
admin.site.register(Record)