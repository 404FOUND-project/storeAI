from django.db import models
from store.models import Store

class AnalysisResult(models.Model):
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE, 
        related_name='analysis_results'
    )

    # 분석 종류
    analysis_type = models.CharField(
        max_length=100
    )

    # 분석 결과
    result = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store.name} - {self.analysis_type}"