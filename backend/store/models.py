from django.conf import settings
from django.db import models


class Store(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,

        # 사장님 계정 삭제 시 그 사장님 소유의 가게 정보도 같이 삭제됨
        on_delete=models.CASCADE,  

        related_name='stores'
    )

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # 사업자 등록 번호
    business_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name