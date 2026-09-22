from rest_framework import generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.pagination import PageNumberPagination

from .models import Notice
from .permissions import IsAdminOrReadOnly
from .serializers import NoticeSerializer


class NoticePagination(PageNumberPagination):
    # 페이지당 20개 고정
    page_size = 20


class NoticeListCreateView(generics.ListCreateAPIView):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = NoticePagination

    def perform_create(self, serializer):
        # 인증된 관리자를 작성자로 지정
        serializer.save(author=self.request.user)


class NoticeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminOrReadOnly]
