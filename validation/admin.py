from django.contrib import admin
from validation.models import Observation, Crossmatch, Field, ReferenceCatalog

admin.site.register(Observation)
admin.site.register(Field)
admin.site.register(Crossmatch)
admin.site.register(ReferenceCatalog)
