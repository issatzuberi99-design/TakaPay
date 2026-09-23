from django.db import models


class Reward(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    token_cost = models.PositiveIntegerField()
    available = models.BooleanField(default=True)
    inventory = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
